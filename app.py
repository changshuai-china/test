import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_migrate import Migrate
from datetime import datetime, timedelta
from forms import CreateOrderForm, AssignOrderForm
from config import Config
from extensions import db, login_manager, bcrypt
from models import WorkOrder, OrderStage, Attachment, User, Department
from auth import auth_bp
from admin import admin_bp
from flask_login import login_required, current_user

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
login_manager.init_app(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)

# 注册蓝图
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 用户加载器
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 未授权处理器
@login_manager.unauthorized_handler
def unauthorized():
    flash('请先登录以访问此页面', 'warning')
    return redirect(url_for('auth.login'))

@app.route('/')
def index():
    return redirect(url_for('view_orders'))

@app.route('/create_order', methods=['GET', 'POST'])
@login_required
def create_order():
    form = CreateOrderForm()
    form.next_assignee_id.choices = [(u.id, u.realname) for u in User.query.order_by(User.realname).all()]
    if form.validate_on_submit():
        total_duration = (form.delivery_date.data - form.order_date.data).total_seconds()
        
        order = WorkOrder(
            order_number=form.order_number.data,
            order_date=form.order_date.data,
            quantity=form.quantity.data,
            delivery_date=form.delivery_date.data,
            salesperson_id=current_user.id,  # 当前用户作为业务员
            total_duration=int(total_duration)
        )
        
        # 创建初始环节
        initial_stage = OrderStage(
            stage_name='创建工单',
            start_time=datetime.utcnow(),
            assignee_id=current_user.id
        )
        order.stages.append(initial_stage)
         # 创建下一环节（如果指定了）
        if form.next_stage_name.data and form.next_assignee_id.data:
            next_stage = OrderStage(
                stage_name=form.next_stage_name.data,
                assignee_id=form.next_assignee_id.data
            )
            order.stages.append(next_stage)
            order.current_stage = next_stage.stage_name
        else:
            order.current_stage = initial_stage.stage_name

        db.session.add(order)
        db.session.commit()
        flash('工单创建成功!', 'success')
        return redirect(url_for('view_orders'))
    return render_template('create_order.html', form=form)

@app.route('/orders')
@login_required
def view_orders():
    # 管理员查看所有工单，普通用户只查看自己的工单
    if current_user.is_admin():
        orders = WorkOrder.query.all()
    else:
        orders = WorkOrder.query.filter_by(salesperson_id=current_user.id).all()
    return render_template('view_orders.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def view_order(order_id):
    order = WorkOrder.query.get_or_404(order_id)
    
    # 权限检查：非管理员只能查看自己的工单
    if not current_user.is_admin() and order.salesperson_id != current_user.id:
        flash('您没有权限查看此工单', 'danger')
        return redirect(url_for('view_orders'))
    
    return render_template('view_order.html', order=order)
#------------------------------------------------------------------------------------------------------
@app.route('/assign_order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def assign_order(order_id):
    order = WorkOrder.query.get_or_404(order_id)
    
    # 权限检查：管理员或当前环节负责人可以指派
    current_stage = OrderStage.query.filter_by(order_id=order.id, end_time=None).first()
    is_current_assignee = current_stage and current_stage.assignee_id == current_user.id
    
    if not current_user.is_admin() and not is_current_assignee:
        flash('您没有权限指派此工单', 'danger')
        return redirect(url_for('view_order', order_id=order.id))
    
    form = AssignOrderForm()
    form.assignee_id.choices = [(u.id, u.realname) for u in User.query.order_by(User.realname).all()]
    
    if form.validate_on_submit():
        # 结束当前环节（如果有）
        if current_stage:
            current_stage.end_time = datetime.utcnow()
            current_stage.duration = int((current_stage.end_time - current_stage.start_time).total_seconds())
        
        # 创建新环节
        new_stage = OrderStage(
            stage_name=form.stage_name.data,
            start_time=datetime.utcnow(),
            assignee_id=form.assignee_id.data,
            order_id=order.id
        )
        
        # 处理附件上传
        if form.attachment.data:
            file = form.attachment.data
            filename = f"{order_id}_{new_stage.stage_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            attachment = Attachment(
                filename=filename,
                stage_id=new_stage.id
            )
            new_stage.attachments.append(attachment)
        
        db.session.add(new_stage)
        order.current_stage = new_stage.stage_name
        db.session.commit()
        
        flash('工单已指派!', 'success')
        return redirect(url_for('view_order', order_id=order.id))
    
    return render_template('assign_order.html', form=form, order=order)
#------------------------------------------------------------------------------------------------------
@app.route('/download/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # 确保在应用上下文中操作
    with app.app_context():
        print("正在创建数据库表...")
        
        # 检查表是否存在
        print("检查表是否存在:")
        print(f"WorkOrder 表存在: {'work_order' in db.metadata.tables}")
        print(f"User 表存在: {'user' in db.metadata.tables}")
        
        # 创建所有数据库表
        try:
            db.drop_all()  # 删除所有表（确保从零开始）
            print("已删除所有表")
            
            db.create_all()  # 创建所有表
            print("已创建所有表")
            
            # 再次检查表是否存在
            print("创建后检查:")
            print(f"WorkOrder 表存在: {'work_order' in db.metadata.tables}")
            print(f"User 表存在: {'user' in db.metadata.tables}")
            
        except Exception as e:
            print(f"创建表时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 初始化数据 - 现在这个查询在应用上下文中
        if not User.query.first():
            print("初始化数据库和基础数据...")
            
            # 创建部门
            admin_dept = Department(name='管理部', description='系统管理部门')
            sales_dept = Department(name='销售部', description='销售部门')
            production_dept = Department(name='生产部', description='生产部门')
            db.session.add_all([admin_dept, sales_dept, production_dept])
            db.session.commit()
            
            # 创建管理员用户
            admin_user = User(
                username='admin',
                realname='系统管理员',
                email='admin@example.com',
                role='admin',
                department_id=admin_dept.id
            )
            admin_user.password = 'admin123'  # 设置密码
            db.session.add(admin_user)
            
            # 创建销售用户
            sales_user = User(
                username='sales1',
                realname='销售员1',
                email='sales1@example.com',
                role='user',
                department_id=sales_dept.id
            )
            sales_user.password = 'sales123'
            db.session.add(sales_user)
            
            # 创建生产用户
            prod_user = User(
                username='prod1',
                realname='生产员1',
                email='prod1@example.com',
                role='user',
                department_id=production_dept.id
            )
            prod_user.password = 'prod123'
            db.session.add(prod_user)
            
            db.session.commit()
            
            # 创建测试工单
            order = WorkOrder(
                order_number='ORD-001',
                order_date=datetime.utcnow(),
                quantity=10,
                delivery_date=datetime.utcnow() + timedelta(days=7),
                salesperson_id=sales_user.id,
                total_duration=604800  # 7天的秒数
            )
            
            # 创建并关联阶段
            stage = OrderStage(
                stage_name='创建工单',
                start_time=datetime.utcnow(),
                assignee_id=sales_user.id,
                work_order=order  # 使用关系连接
            )
            
            db.session.add(order)
            db.session.add(stage)
            db.session.commit()
            print("数据库初始化完成！管理员账号：admin/admin123")

    
    # 运行应用
    app.run(host='0.0.0.0', port=5000, debug=True)
def can_assign_order(order, user):
    """
    检查用户是否有权限指派工单
    - 管理员总是有权限
    - 当前环节的负责人有权限
    - 工单创建者有特殊权限（可选）
    """
    if user.is_admin():
        return True
    
    # 获取当前活跃环节
    current_stage = OrderStage.query.filter_by(order_id=order.id, end_time=None).first()
    
    # 如果是当前环节的负责人
    if current_stage and current_stage.assignee_id == user.id:
        return True
    
    # 如果是工单创建者（可选）
    # if order.salesperson_id == user.id:
    #     return True
    
    return False
@app.context_processor
def utility_processor():
    def can_assign_order(order, user):
        if user.is_admin():
            return True
        current_stage = OrderStage.query.filter_by(order_id=order.id, end_time=None).first()
        return current_stage and current_stage.assignee_id == user.id
    
    return dict(can_assign_order=can_assign_order)

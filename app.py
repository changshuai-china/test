import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_migrate import Migrate
from datetime import datetime, timedelta
from forms import CreateOrderForm, AssignOrderForm, ProcessOrderForm  # 确保导入 ProcessOrderForm
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
    # 检查用户是否有创建工单的权限
    if not (current_user.is_admin() or current_user.can_create_order):
        flash('您没有创建工单的权限', 'danger')
        return redirect(url_for('view_orders'))
    
    form = CreateOrderForm()
    form.next_assignee_id.choices = [(u.id, u.realname) for u in User.query.order_by(User.realname).all()]
    
    if form.validate_on_submit():
        # 自定义日期解析函数
        def parse_date(date_str):
            # 尝试多种日期格式
            formats = [
                '%Y%m%d',    # yyyymmdd (如20250629)
                '%Y/%m/%d',  # yyyy/mm/dd
                '%m/%d/%Y',  # mm/dd/yyyy
                '%Y-%m-%d',  # yyyy-mm-dd
                '%m-%d-%Y',  # mm-dd-yyyy
                '%d/%m/%Y',  # dd/mm/yyyy
                '%d-%m-%Y'   # dd-mm-yyyy
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # 如果所有格式都失败，尝试只解析数字
            try:
                # 尝试拆分数字
                if len(date_str) == 8 and date_str.isdigit():
                    # 处理yyyymmdd格式
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    return datetime(year, month, day)
            except:
                pass
            
            return None
        
        # 解析日期
        order_date = parse_date(form.order_date.data)
        delivery_date = parse_date(form.delivery_date.data)
        
        if not order_date:
            flash('下单日期格式无效，请使用 yyyy/mm/dd 或 yyyymmdd 等标准格式', 'danger')
            return render_template('create_order.html', form=form)
        
        if not delivery_date:
            flash('交货期格式无效，请使用 yyyy/mm/dd 或 yyyymmdd 等标准格式', 'danger')
            return render_template('create_order.html', form=form)
        
        total_duration = (delivery_date - order_date).total_seconds()
        
        try:
            order = WorkOrder(
                order_number=form.order_number.data,
                order_date=order_date,
                quantity=form.quantity.data,
                delivery_date=delivery_date,
                salesperson_id=current_user.id,
                current_assignee_id=form.next_assignee_id.data,  # 新增当前负责人字段
                total_duration=int(total_duration),
                current_stage='创建工单'
            )
            
            # 创建初始环节
            initial_stage = OrderStage(
                stage_name='创建工单',
                start_time=datetime.utcnow(),
                assignee_id=current_user.id,
                comments='由 ' + current_user.realname + ' 创建'
            )
            order.stages.append(initial_stage)
            
            # 创建下一环节
            if form.next_stage_name.data and form.next_assignee_id.data:
                next_stage = OrderStage(
                    stage_name=form.next_stage_name.data,
                    start_time=datetime.utcnow(),  # 修改为当前时间
                    assignee_id=form.next_assignee_id.data,
                    work_order=order
                )
                order.stages.append(next_stage)
                order.current_stage = next_stage.stage_name
                order.current_assignee_id = form.next_assignee_id.data  # 设置当前负责人

            db.session.add(order)
            db.session.commit()
            flash('工单创建成功!', 'success')
            return redirect(url_for('view_orders'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建工单失败: {str(e)}', 'danger')
            app.logger.error(f'创建工单失败: {str(e)}')
    
    # 设置默认日期值
    today = datetime.utcnow().strftime('%Y/%m/%d')
    # 交货期默认值为空
    form.order_date.data = today
    form.delivery_date.data = ''
    
    return render_template('create_order.html', form=form)


@app.route('/orders')
@login_required
def view_orders():
    # 管理员查看所有工单
    if current_user.is_admin():
        orders = WorkOrder.query.order_by(WorkOrder.order_date.desc()).all()
    else:
        # 获取用户创建或负责的工单
        created_orders_q = WorkOrder.query.filter_by(salesperson_id=current_user.id)
        
        # 获取用户作为负责人参与的工单ID
        assigned_order_ids = db.session.query(OrderStage.order_id).filter_by(assignee_id=current_user.id).distinct()
        
        assigned_orders_q = WorkOrder.query.filter(WorkOrder.id.in_(assigned_order_ids))
        
        # 合并两个查询并去重
        all_orders_q = created_orders_q.union(assigned_orders_q).order_by(WorkOrder.order_date.desc())
        orders = all_orders_q.all()
    
    # 计算统计数据
    total_orders = WorkOrder.query.count()
    ongoing_orders = WorkOrder.query.filter(WorkOrder.current_stage != '完成').count()
    completed_orders = WorkOrder.query.filter_by(current_stage='完成').count()
    user_count = User.query.count()
    on_time_rate = 98  # 这里应该是实际计算的值
    
    stats = {
        'ongoing': ongoing_orders,
        'completed': completed_orders,
        'users': user_count,
        'on_time_rate': on_time_rate
    }
    
    # 确保传递了 stats 变量
    return render_template('view_orders.html', orders=orders, stats=stats)


# =========== 新增的视图函数 ===========
# 用于查看单个工单的详细信息
@app.route('/order/<int:order_id>')
@login_required
def view_order(order_id):
    order = WorkOrder.query.get_or_404(order_id)
    # 这里可以添加权限检查，例如只允许相关人员查看
    # if not (current_user.is_admin() or current_user.id == order.salesperson_id or current_user.id in [s.assignee_id for s in order.stages]):
    #     flash('您没有权限查看此工单。', 'danger')
    #     return redirect(url_for('view_orders'))
    return render_template('view_order.html', order=order)
# ===================================


@app.route('/assign_order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def assign_order(order_id):
    order = WorkOrder.query.get_or_404(order_id)
    
    # 权限检查：管理员或当前负责人可以指派
    if not (current_user.is_admin() or current_user.id == order.current_assignee_id):
        flash('您没有权限指派此工单', 'danger')
        return redirect(url_for('view_order', order_id=order.id))
    
    form = AssignOrderForm()
    form.assignee_id.choices = [(u.id, u.realname) for u in User.query.order_by(User.realname).all()]
    
    if form.validate_on_submit():
        try:
            # 结束当前环节
            current_stage = OrderStage.query.filter_by(order_id=order.id, end_time=None).first()
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
            
            # 更新工单状态
            order.current_stage = new_stage.stage_name
            order.current_assignee_id = form.assignee_id.data
            
            # 处理附件上传
            if form.attachment.data:
                file = form.attachment.data
                filename = f"{order_id}_{new_stage.stage_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                attachment = Attachment(
                    filename=filename
                    # 注意：关联到 stage 需要在 stage 被添加到 session 之后
                )
                new_stage.attachments.append(attachment)
            
            db.session.add(new_stage)
            db.session.commit()
            
            flash('工单已指派!', 'success')
            return redirect(url_for('view_order', order_id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'指派工单失败: {str(e)}', 'danger')
            app.logger.error(f'指派工单失败: {str(e)}')
    
    return render_template('assign_order.html', form=form, order=order)


@app.route('/process_order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def process_order(order_id):
    order = WorkOrder.query.get_or_404(order_id)
    
    # 检查当前用户是否是当前负责人
    if order.current_assignee_id != current_user.id:
        flash('您不是当前环节负责人，无法处理此工单', 'danger')
        return redirect(url_for('view_order', order_id=order.id))
    
    # 获取当前活跃环节
    current_stage = OrderStage.query.filter_by(order_id=order.id, end_time=None).first()
    
    # 确保当前环节存在
    if not current_stage:
        flash('找不到当前环节，无法处理', 'danger')
        return redirect(url_for('view_order', order_id=order.id))
    
    form = ProcessOrderForm()
    # 动态加载用户列表
    form.next_assignee_id.choices = [(u.id, f"{u.department.name} - {u.realname}") for u in User.query.join(Department).order_by(Department.name, User.realname).all()]

    if form.validate_on_submit():
        try:
            # 1. 更新当前环节信息
            current_stage.end_time = datetime.utcnow()
            current_stage.duration = int((current_stage.end_time - current_stage.start_time).total_seconds())
            current_stage.comments = form.comments.data
            
            # 2. 创建新环节
            new_stage = OrderStage(
                stage_name=form.next_stage_name.data,
                start_time=datetime.utcnow(),
                assignee_id=form.next_assignee_id.data,
                order_id=order.id
            )
            
            # 3. 更新工单主状态
            order.current_stage = new_stage.stage_name
            order.current_assignee_id = form.next_assignee_id.data
            
            db.session.add(new_stage)
            # 在添加新阶段后，处理附件，这样 new_stage 就会有一个 id
            db.session.flush() # flush 以便 new_stage.id 可用

            # 4. 处理附件上传
            if form.attachment.data:
                file = form.attachment.data
                # 创建一个安全的文件名
                filename = f"{order_id}_{new_stage.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                attachment = Attachment(
                    filename=filename,
                    stage_id=new_stage.id
                )
                db.session.add(attachment)

            db.session.commit()
            
            flash('工单处理完成! 已指派给下一环节负责人', 'success')
            return redirect(url_for('view_order', order_id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'处理工单失败: {str(e)}', 'danger')
            app.logger.error(f'处理工单失败: {e}', exc_info=True)
            
    # GET 请求时，为表单设置默认值
    if not form.is_submitted():
        form.next_stage_name.data = current_stage.stage_name
        
    return render_template('process_order.html', form=form, order=order, current_stage=current_stage)


@app.route('/download/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def can_assign_order(order, user):
    """
    检查用户是否有权限指派工单
    - 管理员总是有权限
    - 当前环节的负责人有权限
    """
    if user.is_admin():
        return True
    
    # 获取当前活跃环节
    current_stage = OrderStage.query.filter_by(order_id=order.id, end_time=None).first()
    
    # 如果是当前环节的负责人
    if current_stage and current_stage.assignee_id == user.id:
        return True
    
    return False

@app.context_processor
def utility_processor():
    return dict(can_assign_order=can_assign_order)

if __name__ == '__main__':
    # 确保在应用上下文中操作
    with app.app_context():
        # # 下面的代码块用于初始化数据库，正常运行时可以注释掉
        # print("正在创建数据库表...")
        
        # # 检查表是否存在
        # print("检查表是否存在:")
        # from sqlalchemy import inspect
        # inspector = inspect(db.engine)
        # print(f"WorkOrder 表存在: {inspector.has_table('work_order')}")
        # print(f"User 表存在: {inspector.has_table('user')}")
        
        # # 创建所有数据库表
        # try:
        #     # db.drop_all()  # 危险操作：删除所有表（确保从零开始）
        #     # print("已删除所有表")
            
        #     db.create_all()  # 创建所有不存在的表
        #     print("已创建所有表")
            
        # except Exception as e:
        #     print(f"创建表时出错: {e}")
        #     import traceback
        #     traceback.print_exc()
        
        # # 初始化数据 (仅当用户表为空时执行)
        if not User.query.first():
            print("首次运行，初始化数据库和基础数据...")
            
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
                role='admin',
                department_id=admin_dept.id,
                can_create_order=True
            )
            admin_user.password = 'admin123'  # 设置密码
            db.session.add(admin_user)
            
            # 创建销售用户
            sales_user1 = User(
                username='wzl',
                realname='王正玲',
                role='user',
                department_id=sales_dept.id,
                can_create_order=True
            )
            sales_user1.password = 'qq'
            db.session.add(sales_user1)
            
            sales_user2 = User(
                username='cyl',
                realname='陈应林',
                role='user',
                department_id=sales_dept.id,
                can_create_order=False
            )
            sales_user2.password = 'qq'
            db.session.add(sales_user2)

            sales_user3 = User(
                username='yj',
                realname='杨军',
                role='user',
                department_id=sales_dept.id,
                can_create_order=False
            )
            sales_user3.password = 'qq'
            db.session.add(sales_user3)
           
            # 创建生产用户
            prod_user = User(
                username='aa',
                realname='生产员1',
                role='user',
                department_id=production_dept.id,
                can_create_order=False
            )
            prod_user.password = 'qq'
            db.session.add(prod_user)
            
            db.session.commit()
            
            # 创建测试工单
            order = WorkOrder(
                order_number='ORD-001',
                order_date=datetime.utcnow() - timedelta(days=1),
                quantity=10,
                delivery_date=datetime.utcnow() + timedelta(days=7),
                salesperson_id=sales_user1.id,
                current_assignee_id=prod_user.id,
                total_duration=691200,  # 8天的秒数
                current_stage='生产中'
            )
            
            # 创建并关联阶段
            stage1 = OrderStage(
                stage_name='创建工单',
                start_time=datetime.utcnow() - timedelta(days=1),
                end_time=datetime.utcnow() - timedelta(hours=23),
                duration=3600,
                assignee_id=sales_user1.id,
                work_order=order,
                comments='初始订单'
            )

            stage2 = OrderStage(
                stage_name='生产中',
                start_time=datetime.utcnow() - timedelta(hours=23),
                assignee_id=prod_user.id,
                work_order=order
            )
            
            db.session.add(order)
            db.session.add_all([stage1, stage2])
            db.session.commit()
            print("数据库初始化完成！管理员账号：admin/admin123, 销售员账号: wzl/qq")

    # 运行应用
    app.run(host='0.0.0.0', port=5000, debug=True)

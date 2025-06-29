from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import User, Department
from forms import EditUserForm, DepartmentForm, RegistrationForm
from extensions import db, bcrypt

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def check_admin():
    if not current_user.is_admin():
        flash('您没有访问此页面的权限', 'danger')
        return redirect(url_for('view_orders'))

@admin_bp.route('/users')
def manage_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    departments = Department.query.all()
    form.department_id.choices = [(d.id, d.name) for d in departments]
    
    if form.validate_on_submit():
        user.realname = form.realname.data
        user.role = form.role.data
        user.department_id = form.department_id.data
        # 更新创建工单权限
        user.can_create_order = form.can_create_order.data
        db.session.commit()
        flash('用户信息已更新', 'success')
        return redirect(url_for('admin.manage_users'))
    
    # 确保表单字段显示当前值
    form.can_create_order.data = user.can_create_order
    return render_template('admin/edit_user.html', form=form, user=user)

@admin_bp.route('/user/<int:user_id>/delete')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        flash('不能删除当前登录的用户', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    db.session.delete(user)
    db.session.commit()
    flash('用户已删除', 'success')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/departments')
def manage_departments():
    departments = Department.query.all()
    return render_template('admin/departments.html', departments=departments)

@admin_bp.route('/department/add', methods=['GET', 'POST'])
def add_department():
    form = DepartmentForm()
    if form.validate_on_submit():
        department = Department(name=form.name.data, description=form.description.data)
        db.session.add(department)
        db.session.commit()
        flash('部门已添加', 'success')
        return redirect(url_for('admin.manage_departments'))
    return render_template('admin/edit_department.html', form=form)

@admin_bp.route('/department/<int:dept_id>/edit', methods=['GET', 'POST'])
def edit_department(dept_id):
    department = Department.query.get_or_404(dept_id)
    form = DepartmentForm(obj=department)
    if form.validate_on_submit():
        department.name = form.name.data
        department.description = form.description.data
        db.session.commit()
        flash('部门信息已更新', 'success')
        return redirect(url_for('admin.manage_departments'))
    return render_template('admin/edit_department.html', form=form, department=department)

@admin_bp.route('/department/<int:dept_id>/delete')
def delete_department(dept_id):
    department = Department.query.get_or_404(dept_id)
    if department.users:
        flash('该部门下还有用户，不能删除', 'danger')
        return redirect(url_for('admin.manage_departments'))
    
    db.session.delete(department)
    db.session.commit()
    flash('部门已删除', 'success')
    return redirect(url_for('admin.manage_departments'))
#__________________________________________________________________________________________
@admin_bp.route('/user/add', methods=['GET', 'POST'])
def add_user():
    form = RegistrationForm()
    departments = Department.query.all()
    form.department_id.choices = [(d.id, d.name) for d in departments]
    
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(
            username=form.username.data,
            password_hash=hashed_password,
            realname=form.realname.data,
            role=form.role.data,
            department_id=form.department_id.data,
            # 设置创建工单权限
            can_create_order=form.can_create_order.data
        )
        db.session.add(user)
        db.session.commit()
        flash('用户添加成功!', 'success')
        return redirect(url_for('admin.manage_users'))
    
    return render_template('admin/add_user.html', form=form)

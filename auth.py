from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from forms import LoginForm, RegistrationForm
from models import User, Department
from extensions import db, bcrypt

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('view_orders'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('登录成功!', 'success')
            return redirect(url_for('view_orders'))
        else:
            flash('用户名或密码错误', 'danger')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已退出登录', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('view_orders'))
    
    form = RegistrationForm()
    departments = Department.query.all()
    form.department_id.choices = [(d.id, d.name) for d in departments]
    
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(
            username=form.username.data,
            password_hash=hashed_password,
            realname=form.realname.data,
            email=form.email.data,
            role=form.role.data,
            department_id=form.department_id.data
        )
        db.session.add(user)
        db.session.commit()
        flash('账户创建成功! 请登录', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)

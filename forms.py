from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, FileField, PasswordField, SelectField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, EqualTo, ValidationError
from datetime import datetime
from flask_wtf.file import FileAllowed
from models import User

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    realname = StringField('真实姓名', validators=[DataRequired()])
    role = SelectField('角色', choices=[('user', '普通用户'), ('admin', '管理员')], default='user')
    department_id = SelectField('部门', coerce=int)
    can_create_order = BooleanField('可创建工单')
    submit = SubmitField('注册')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('该用户名已被使用')

class EditUserForm(FlaskForm):
    realname = StringField('真实姓名', validators=[DataRequired()])
    role = SelectField('角色', choices=[('user', '普通用户'), ('admin', '管理员')])
    department_id = SelectField('部门', coerce=int)
    can_create_order = BooleanField('可创建工单')
    submit = SubmitField('更新')

class DepartmentForm(FlaskForm):
    name = StringField('部门名称', validators=[DataRequired()])
    description = StringField('描述')
    submit = SubmitField('保存')

class CreateOrderForm(FlaskForm):
    order_number = StringField('派工单号', validators=[DataRequired()])
    order_date = StringField('下单日期', validators=[DataRequired()])
    quantity = IntegerField('数量', validators=[DataRequired(), NumberRange(min=1)])
    delivery_date = StringField('交货期', validators=[DataRequired()])
    
    next_stage_name = SelectField('下一环节名称', choices=[
        ('计划', '计划'),
        ('技术部', '技术部'),
        ('采购部', '采购部'),
        ('宁泰公司', '宁泰公司'),
        ('鑫泽公司', '鑫泽公司'),
        ('鑫波公司', '鑫波公司')
    ], validators=[DataRequired()])
    
    next_assignee_id = SelectField('下一环节负责人', coerce=int)
    
    submit = SubmitField('创建工单')
    
    def __init__(self, *args, **kwargs):
        super(CreateOrderForm, self).__init__(*args, **kwargs)
        self.next_assignee_id.choices = [(u.id, u.realname) for u in User.query.order_by(User.realname).all()]
        
class AssignOrderForm(FlaskForm):
    stage_name = SelectField('环节名称', choices=[
        ('计划', '计划'),
        ('技术部', '技术部'),
        ('采购部', '采购部'),
        ('宁泰公司', '宁泰公司'),
        ('鑫泽公司', '鑫泽公司'),
        ('鑫波公司', '鑫波公司')
    ], validators=[DataRequired()])
    
    assignee_id = SelectField('负责人', coerce=int, choices=[])
    attachment = FileField('附件', validators=[FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'], '只允许特定文件类型')])
    submit = SubmitField('指派工单')

# 添加处理工单表单
class ProcessOrderForm(FlaskForm):
    comments = TextAreaField('进度备注', validators=[DataRequired()])
    
    # 下一环节信息
    next_stage_name = SelectField('下一环节名称', choices=[
        ('计划', '计划'),
        ('技术部', '技术部'),
        ('采购部', '采购部'),
        ('宁泰公司', '宁泰公司'),
        ('鑫泽公司', '鑫泽公司'),
        ('鑫波公司', '鑫波公司'),
        ('完成', '完成')  # 添加"完成"选项
    ], validators=[DataRequired()])
    
    next_assignee_id = SelectField('下一环节负责人', coerce=int)
    
    # 附件上传
    attachment = FileField('附件', validators=[FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'], '只允许特定文件类型')])
    
    submit = SubmitField('完成并指派')
    
    def __init__(self, *args, **kwargs):
        super(ProcessOrderForm, self).__init__(*args, **kwargs)
        self.next_assignee_id.choices = [(u.id, u.realname) for u in User.query.order_by(User.realname).all()]

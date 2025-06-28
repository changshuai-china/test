from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DateField, SubmitField, FileField, PasswordField, SelectField
from wtforms.validators import DataRequired, NumberRange, Email, EqualTo, ValidationError
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
    email = StringField('邮箱', validators=[DataRequired(), Email()])
    role = SelectField('角色', choices=[('user', '普通用户'), ('admin', '管理员')], default='user')
    department_id = SelectField('部门', coerce=int)
    submit = SubmitField('注册')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('该用户名已被使用')

class EditUserForm(FlaskForm):
    realname = StringField('真实姓名', validators=[DataRequired()])
    email = StringField('邮箱', validators=[DataRequired(), Email()])
    role = SelectField('角色', choices=[('user', '普通用户'), ('admin', '管理员')])
    department_id = SelectField('部门', coerce=int)
    submit = SubmitField('更新')

class DepartmentForm(FlaskForm):
    name = StringField('部门名称', validators=[DataRequired()])
    description = StringField('描述')
    submit = SubmitField('保存')

# forms.py

class CreateOrderForm(FlaskForm):
    order_number = StringField('派工单号', validators=[DataRequired()])
    order_date = DateField('下单日期', validators=[DataRequired()], default=datetime.utcnow)
    quantity = IntegerField('数量', validators=[DataRequired(), NumberRange(min=1)])
    delivery_date = DateField('交货期', validators=[DataRequired()])
    
    # 下一环节信息
    next_stage_name = StringField('下一环节名称', validators=[DataRequired()])
    next_assignee_id = SelectField('下一环节负责人', coerce=int)  # 选择用户
    
    submit = SubmitField('创建工单')
    
    def __init__(self, *args, **kwargs):
        super(CreateOrderForm, self).__init__(*args, **kwargs)
        # 动态加载负责人选项
        self.next_assignee_id.choices = [(u.id, u.realname) for u in User.query.order_by(User.realname).all()]
class AssignOrderForm(FlaskForm):
    stage_name = StringField('环节名称', validators=[DataRequired()])
    assignee_id = SelectField('负责人', coerce=int, choices=[])  # 初始为空，由视图函数填充
    attachment = FileField('附件', validators=[FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'], '只允许特定文件类型')])
    submit = SubmitField('指派工单')

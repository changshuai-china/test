from datetime import datetime
from extensions import db
from flask_login import UserMixin
from flask_bcrypt import generate_password_hash, check_password_hash

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship('User', backref='department', lazy=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    realname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    role = db.Column(db.String(20), default='user')  # admin, user
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 密码处理
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password).decode('utf-8')
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # 管理员检查
    def is_admin(self):
        return self.role == 'admin'

class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    quantity = db.Column(db.Integer, nullable=False)
    delivery_date = db.Column(db.DateTime, nullable=False)
    salesperson_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    salesperson = db.relationship('User', foreign_keys=[salesperson_id])
    total_duration = db.Column(db.Integer)  # 总历时(秒)
    current_stage = db.Column(db.String(50), default='created')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    stages = db.relationship('OrderStage', backref='work_order', lazy=True, cascade='all, delete-orphan')

class OrderStage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stage_name = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # 环节历时(秒)
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignee = db.relationship('User', foreign_keys=[assignee_id])
    order_id = db.Column(db.Integer, db.ForeignKey('work_order.id'), nullable=False)
    
    attachments = db.relationship('Attachment', backref='order_stage', lazy=True, cascade='all, delete-orphan')

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    stage_id = db.Column(db.Integer, db.ForeignKey('order_stage.id'), nullable=False)

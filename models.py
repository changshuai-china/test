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
    role = db.Column(db.String(20), default='user')
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    can_create_order = db.Column(db.Boolean, default=False)
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password).decode('utf-8')
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
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
    total_duration = db.Column(db.Integer)
    current_stage = db.Column(db.String(50), default='创建工单')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    current_assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 新增当前负责人字段
    current_assignee = db.relationship('User', foreign_keys=[current_assignee_id])  # 新增关系

    
    stages = db.relationship('OrderStage', 
                             backref='work_order', 
                             lazy=True, 
                             cascade='all, delete-orphan',
                             order_by='OrderStage.start_time')

class OrderStage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stage_name = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)
    comments = db.Column(db.Text)  # 新增进度备注字段
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignee = db.relationship('User', foreign_keys=[assignee_id])
    order_id = db.Column(db.Integer, db.ForeignKey('work_order.id'), nullable=False)
    
    attachments = db.relationship('Attachment', 
                                 backref='order_stage', 
                                 lazy=True, 
                                 cascade='all, delete-orphan')

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    stage_id = db.Column(db.Integer, db.ForeignKey('order_stage.id'), nullable=False)

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')

class InventoryItem(db.Model):
    __tablename__ = 'inventory_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_added_by_admin = db.Column(db.Boolean, default=False)
    is_hidden = db.Column(db.Boolean, default=False)
    assigned_username = db.Column(db.String(80), nullable=True)
    
    user = db.relationship('User', backref='inventory_items', foreign_keys=[assigned_to])

    def __repr__(self):
        return f'<InventoryItem {self.name}>'

class PurchasePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    supplier = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='активен')

class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='ожидает')  
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    
    item = db.relationship('InventoryItem', backref='requests')

class RepairRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), default='ожидает рассмотрения')
    
    
    user = db.relationship('User', backref='repair_requests')
    
    
    item = db.relationship('InventoryItem', backref='repair_requests')

class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    supplier = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='в обработке')  
    external_order_id = db.Column(db.String(100), nullable=True)  

class ReplacementRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='ожидание')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    quantity = db.Column(db.Integer, default=1)

    user = db.relationship('User', backref='replacement_requests')
    item = db.relationship('InventoryItem', backref='replacement_requests')

class AssignmentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('InventoryItem', backref='assignment_history')
    user = db.relationship('User', foreign_keys=[user_id], backref='assignments_received')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='assignments_made')

    def __repr__(self):
        return f'<AssignmentHistory {self.id}>'

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    report_type = db.Column(db.String(50), nullable=False)  
    status = db.Column(db.String(20), nullable=False, default='broken')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    
    user = db.relationship('User', backref='reports')
    inventory = db.relationship('InventoryItem', backref='reports')

    def __repr__(self):
        return f'<Report {self.id}>'
from fsspec.registry import default
from sqlalchemy import CheckConstraint
from home import db, login_manager, app
from datetime import datetime, timezone
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer

def utc_now():
    return datetime.now(timezone.utc)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    goals = db.relationship('Goal', backref='owner', lazy=True)
    savings = db.Column(db.Float, nullable=False, default=0.0)
    
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True)
    
    __table_args__ = (
        CheckConstraint('savings >= 0', name='check_savings_non_negative'),
    )
    
    def __repr__(self):
        return f"User('{self.username}','{self.email}','{self.image_file}')"
    
    def get_reset_token(self) -> str:
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})
    
    @staticmethod
    def verify_reset_token(token: str, max_age: int = 1800):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=max_age)
            user_id = data['user_id']
        except Exception:
            return None
        return User.query.get(user_id)

class SavingChanges(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date_time = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    user = db.relationship('User', backref='saving_changes')
    
    def __repr__(self):
        return f"SavingChange('{self.user.username}', '${self.amount}')"

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_time = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    description = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(100), nullable=True)
    target_amount = db.Column(db.Float, nullable=False)
    deadline = db.Column(db.DateTime, nullable=True)
    category = db.Column(db.String(50), nullable=True, default='savings')
    status = db.Column(db.String(20), nullable=False, default='active')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    __table_args__ = (
        CheckConstraint('target_amount > 0', name='check_target_amount_positive'),
    )
    
class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    theme = db.Column(db.String(20), nullable=False, default='light')  
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=True)
    email_notifications = db.Column(db.Boolean, nullable=False, default=True)
    default_currency = db.Column(db.String(10), nullable=False, default='USD')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    
    user = db.relationship('User', backref='preferences')
    
    def __repr__(self):
        return f"UserPreference('{self.user.username}', '{self.theme}')"

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    currency = db.Column(db.String(10), nullable=False, default='USD')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_open = db.Column(db.Boolean, nullable=False, default=True)
    balance = db.Column(db.Float, nullable=False, default=0.0)  
    
    members = db.relationship('GroupMember', backref='group', lazy=True, cascade='all, delete-orphan')
    goals = db.relationship('GroupGoal', backref='group', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('GroupTransaction', backref='group', lazy=True, cascade='all, delete-orphan')
    join_requests = db.relationship('GroupJoinRequest', backref='group', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"Group('{self.name}', '{self.currency}')"
    
    @property
    def admin_members(self):
        return [member for member in self.members if member.role == 'admin']
    
    @property
    def regular_members(self):
        return [member for member in self.members if member.role == 'member']
    
    @property
    def total_balance(self):
        return self.balance

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='member')  
    joined_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='unique_group_user'),
    )
    
    def __repr__(self):
        return f"GroupMember('{self.user.username}', '{self.group.name}', '{self.role}')"
    
    @property
    def is_admin(self):
        return self.role == 'admin'

class GroupGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    deadline = db.Column(db.DateTime, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='proposed')  
    proposer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    
    proposer = db.relationship('User', foreign_keys=[proposer_id], backref='proposed_goals')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_goals')
    
    __table_args__ = (
        CheckConstraint('target_amount > 0', name='check_group_goal_amount_positive'),
    )
    
    def __repr__(self):
        return f"GroupGoal('{self.title}', '{self.status}', '{self.group.name}')"

class GroupTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    status = db.Column(db.String(20), nullable=False, default='pending')  
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='group_transactions')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_transactions')
    
    __table_args__ = (
        CheckConstraint('amount != 0', name='check_transaction_amount_non_zero'),
    )
    
    def __repr__(self):
        return f"GroupTransaction('{self.user.username}', '${self.amount}', '{self.status}')"
    
    @property
    def is_contribution(self):
        return self.transaction_type == 'contribution'
    
    @property
    def is_withdrawal(self):
        return self.transaction_type == 'withdrawal'
    
    @property
    def is_expense(self):
        return self.transaction_type == 'expense'
    
    @property
    def is_adjustment(self):
        return self.transaction_type == 'adjustment'

class GroupJoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  
    message = db.Column(db.Text, nullable=True)  
    requested_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    responded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    responded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='join_requests')
    responded_by = db.relationship('User', foreign_keys=[responded_by_id], backref='responded_requests')
    
    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='unique_pending_join_request'),
    )
    
    def __repr__(self):
        return f"GroupJoinRequest('{self.user.username}', '{self.group.name}', '{self.status}')"



class GroupPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False, unique=True)
    is_open = db.Column(db.Boolean, nullable=False, default=True)
    default_currency = db.Column(db.String(10), nullable=False, default='USD')
    require_goal_approval = db.Column(db.Boolean, nullable=False, default=True)
    require_transaction_approval = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    
    group = db.relationship('Group', backref='preferences')
    
    def __repr__(self):
        return f"GroupPreference('{self.group.name}', 'open:{self.is_open}')"
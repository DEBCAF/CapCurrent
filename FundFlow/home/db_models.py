# imports
from sqlalchemy import CheckConstraint # Importing CheckConstraint for database constraints
from home import db # Importing the database instance, login manager, and Flask app instance
from datetime import datetime, timezone # Importing the datetime module 
from flask_login import UserMixin # Importing UserMixin for user session management

def utc_now():
    return datetime.now(timezone.utc)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    username = db.Column(db.String(20), unique=True, nullable=False) # limits username length to 20 characters
    email = db.Column(db.String(120), unique=True, nullable=False) # limits email length to 120 characters
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg') # default profile image file name
    password = db.Column(db.String(60), nullable=False) # stores hashed password
    savings = db.Column(db.Float, nullable=False, default=0.0) # stores user's current savings with a default value of 0.0
    
    __table_args__ = (
        CheckConstraint('savings >= 0', name='check_savings_non_negative'),
    ) # ensures savings cannot be negative
    
    def __repr__(self):
        return f"User('{self.username}','{self.email}','{self.image_file}')" # string representation of the User object
    
class SavingChanges(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    amount = db.Column(db.Float, nullable=False) # amount changed in savings
    date_time = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp of the change
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # foreign key linking to User table
    
    user = db.relationship('User', backref='saving_changes') # states relationship to User model
    
    def __repr__(self):
        return f"SavingChange('{self.user.username}', '${self.amount}')" # string representation of the SavingChanges object
    
class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    title = db.Column(db.String(100), nullable=False) # title of the goal
    date_time = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp of goal creation
    description = db.Column(db.Text, nullable=False) # description of the goal
    url = db.Column(db.String(100), nullable=True) # optional URL related to the goal
    target_amount = db.Column(db.Float, nullable=False) # target amount to achieve the goal
    deadline = db.Column(db.DateTime, nullable=True) # optional deadline for the goal
    status = db.Column(db.String(20), nullable=False, default='active') # status of the goal
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # foreign key linking to User table
    
    owner = db.relationship('User', backref='goals') # states relationship to User model
    
    __table_args__ = (
        CheckConstraint('target_amount > 0', name='check_target_amount_positive'),
    ) # ensures target amount is positive
    
    def __repr__(self):
        return f"Goal('{self.title}', '${self.target_amount}')" # string representation of the Goal object
    
class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True) # foreign key linking to User table
    theme = db.Column(db.String(20), nullable=False, default='light') # selecting the appearance of the app
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=True) # selecting choice of notifications
    default_currency = db.Column(db.String(10), nullable=False, default='USD') # selecting choice of currency
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now) # timestamp
    
    user = db.relationship('User', backref='preferences') # states relationship to User model
    
    def __repr__(self):
        return f"UserPreference('{self.user.username}', '{self.theme}')" # string representation of the UserPreference object
    
class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    name = db.Column(db.String(100), nullable=False) # name of the group
    description = db.Column(db.Text, nullable=True) # optional description of the group
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp of group creation
    currency = db.Column(db.String(10), nullable=False, default='USD') # currency used in the group
    is_active = db.Column(db.Boolean, nullable=False, default=True) # indicates if the group is active
    is_open = db.Column(db.Boolean, nullable=False, default=True) # indicates if the group is open for joining
    balance = db.Column(db.Float, nullable=False, default=0.0) # current balance of the group
    
    # relationships with other tables
    members = db.relationship('GroupMember', backref='group', lazy=True, cascade='all, delete-orphan')
    goals = db.relationship('GroupGoal', backref='group', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('GroupTransaction', backref='group', lazy=True, cascade='all, delete-orphan')
    join_requests = db.relationship('GroupJoinRequest', backref='group', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"Group('{self.name}', '{self.currency}')" # string representation of the Group object
    
    @property
    def admin_members(self): # property to get all admin members of the group
        return [member for member in self.members if member.role == 'admin' and member.is_active]
    
    @property
    def regular_members(self): # property to get all regular members of the group
        return [member for member in self.members if member.role == 'member']
    
    @property
    def total_balance(self): # property to get the total balance of the group
        return self.balance
    
class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False) # foreign key linking to Group table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # foreign key linking to User table
    role = db.Column(db.String(20), nullable=False, default='member') # role of the member in the group
    joined_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp of when the user joined the group
    is_active = db.Column(db.Boolean, nullable=False, default=True) # indicates if the member is active in the group
    
    user = db.relationship('User', backref='group_members') # states relationship to User model
    
    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='unique_group_user'),
    ) # make sure that a user can only be a member of a group once
    
    def __repr__(self):
        return f"GroupMember('{self.user.username}', '{self.group.name}', '{self.role}')" # string representation of the GroupMember object
    
    @property
    def is_admin(self): # property to check if the member is an admin
        return self.role == 'admin'
    
class GroupGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False) # foreign key linking to Group table
    title = db.Column(db.String(100), nullable=False) # title of the group goal
    description = db.Column(db.Text, nullable=False) # description of the group goal
    target_amount = db.Column(db.Float, nullable=False) # target amount for the group goal
    deadline = db.Column(db.DateTime, nullable=True) # optional deadline for the group goal
    status = db.Column(db.String(20), nullable=False, default='proposed') # status of the group goal
    proposer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # user who proposed the goal
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # user who approved the goal
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True) # timestamp of when the goal was approved
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp of goal creation
    
    # relationships with User table
    proposer = db.relationship('User', foreign_keys=[proposer_id], backref='proposed_goals')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_goals')
    
    __table_args__ = (
        CheckConstraint('target_amount > 0', name='check_group_goal_amount_positive'),
    ) # make sure target amount is positive
    
    def __repr__(self):
        return f"GroupGoal('{self.title}', '{self.status}', '{self.group.name}')" # string representation of the GroupGoal object

class GroupTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False) # foreign key linking to Group table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # user who made the transaction
    amount = db.Column(db.Float, nullable=False) # amount of the transaction
    description = db.Column(db.Text, nullable=True) # optional description of the transaction
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp of when the transaction occurred
    status = db.Column(db.String(20), nullable=False, default='pending')  # status of the transaction
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # user who approved the transaction
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True) # timestamp of when the transaction was approved
    
    # relationships with User table
    user = db.relationship('User', foreign_keys=[user_id], backref='group_transactions')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_transactions')
    
    __table_args__ = (
        CheckConstraint('amount != 0', name='check_transaction_amount_non_zero'),
    ) # make sure transaction amount is not zero
    
    def __repr__(self):
        return f"GroupTransaction('{self.user.username}', '${self.amount}', '{self.status}')"

class GroupJoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True) # unique identifier as primary key
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False) # foreign key linking to Group table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # user who made the join request
    status = db.Column(db.String(20), nullable=False, default='pending') # status of the join request
    message = db.Column(db.Text, nullable=True) # optional message from the user requesting to join
    requested_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now) # timestamp of when the user requested to join
    responded_at = db.Column(db.DateTime(timezone=True), nullable=True) # timestamp of when the join request was responded to
    responded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # user who responded to the join request
    
    # relationships with User table
    user = db.relationship('User', foreign_keys=[user_id], backref='join_requests')
    responded_by = db.relationship('User', foreign_keys=[responded_by_id], backref='responded_requests')
    
    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='unique_pending_join_request'),
    ) # ensure a user can only have one pending join request per group
    
    def __repr__(self):
        return f"GroupJoinRequest('{self.user.username}', '{self.group.name}', '{self.status}')" 

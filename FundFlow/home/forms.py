from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, FloatField, DateField, SelectField, IntegerField
from wtforms.validators import DataRequired, InputRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange
from flask_wtf.file import FileField, FileAllowed
from home.db_models import User
from flask_login import current_user
import re as re

class RegistrationForm(FlaskForm):
    username = StringField('Username',
                          validators=[DataRequired(), Length(min=2, max=20)]) # limits username length to between 2 and 20 characters
    email = StringField('Email',
                       validators=[DataRequired(), Email()]) # checks email matches email format
    password = PasswordField('Password',
                           validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                   validators=[DataRequired(), EqualTo('password')]) # ensures user enters the password they intended
    submit = SubmitField('Sign Up')

    def validate_username(self, username): # additional validation to check if username is already taken
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username has been taken, choose another.')
        
    def validate_email(self, email): # additional validation to check if email is already taken
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email has been taken, choose another.')
            
class LoginForm(FlaskForm):
    email = StringField('Email',
                       validators=[DataRequired(), Email()]) # checks email matches email format
    password = PasswordField('Password',
                           validators=[DataRequired()])
    remember = BooleanField('Remember Me') # allows user to stay logged in
    submit = SubmitField('Login')
    
class UpdateAccountForm(FlaskForm):
    username = StringField('Username',
                          validators=[DataRequired(), Length(min=2, max=20)]) # limits username length to between 2 and 20 characters
    email = StringField('Email',
                       validators=[DataRequired(), Email()]) # checks email matches email format
    picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg','png'])]) # limits to only jpg and png files for profile picture
    submit = SubmitField('Update')
    
    def validate_username(self, username): # additional validation to check if username is already taken
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Username has been taken, choose another.')
        
    def validate_email(self, email): # additional validation to check if email is already taken
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Email has been taken, choose another.')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()]) # requires the entering of current password for verification
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')]) # makes sure users type the intented new password correctly
    submit = SubmitField('Change Password')
    
class UpdateSavingsForm(FlaskForm):
    savings = FloatField('Savings Balance', validators=[InputRequired(), NumberRange(min=0, message='Savings cannot be negative')]) # make sure savings cannot be negative, InputRequired allows 0 as valid input
    submit = SubmitField('Update Savings')

class AdjustSavingsForm(FlaskForm):
    amount = FloatField('Amount', validators=[])  # All validations handled in custom validator
    operation = SelectField('Operation', choices=[
        ('add', 'Add to savings'),
        ('subtract', 'Subtract from savings') # Users can choose to either add or subtract from their savings
    ], validators=[DataRequired()])
    description = StringField('Description (Optional)', validators=[Optional(), Length(max=100)]) # optional description for users to describe the reason for adjustment
    submit = SubmitField('Adjust Savings')
    
    def validate_amount(self, amount): # additional validation to ensure amount is a valid positive number
        # Check the raw input first to handle invalid types
        raw_value = amount.raw_data[0] if amount.raw_data else ''
        
        # Check if field is empty
        if not raw_value or not raw_value.strip():
            raise ValidationError('This field is required.')
        
        # Check if the field data is None when conversion fails if user enters a string
        if amount.data is None:
            raise ValidationError('Amount must be a valid positive number.')
        
        # Check if amount is positive
        if amount.data <= 0:
            raise ValidationError('Amount must be greater than 0.')
    
class GoalForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=20)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=100)])
    url = StringField('URL (Optional)', validators=[Optional(), Length(max=100)])
    target_amount = FloatField('Target Amount', validators=[InputRequired()])
    deadline = DateField('Deadline (Optional)', validators=[Optional()])
    submit = SubmitField('Create Goal')

    def validate_target_amount(self, target_amount): # additional validation to ensure target amount is positive and reasonable
        # Check the raw input first to handle invalid types
        raw_value = target_amount.raw_data[0] if target_amount.raw_data else ''
        
        # Check if field is empty
        if not raw_value or not raw_value.strip():
            raise ValidationError('This field is required.')
        
        # Check if the field data is None when conversion fails
        if target_amount.data is None:
            raise ValidationError('Target amount must be a valid number.')
        if target_amount.data <= 0:
            raise ValidationError('Target amount must be greater than 0.')
        if target_amount.data > 1000000:
            raise ValidationError('Target amount cannot exceed $1,000,000.')
        
class UpdateGoalForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=20)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=100)])
    url = StringField('URL (Optional)', validators=[Optional(), Length(max=100)])
    target_amount = FloatField('Target Amount', validators=[InputRequired()])
    deadline = DateField('Deadline (Optional)', validators=[Optional()])
    submit = SubmitField('Update Goal')
        
    def validate_target_amount(self, target_amount): # additional validation to ensure target amount is positive and reasonable
        # Check the raw input first to handle invalid types
        raw_value = target_amount.raw_data[0] if target_amount.raw_data else ''
        
        # Check if field is empty
        if not raw_value or not raw_value.strip():
            raise ValidationError('This field is required.')
        
        # Check if the field data is None when conversion fails
        if target_amount.data is None:
            raise ValidationError('Target amount must be a valid number.')
        if target_amount.data <= 0:
            raise ValidationError('Target amount must be greater than 0.')
        if target_amount.data > 1000000:
            raise ValidationError('Target amount cannot exceed $1,000,000.')
        
class UserPreferencesForm(FlaskForm):
    theme = SelectField('Theme', choices=[
        ('light', 'Light Mode'),
        ('dark', 'Dark Mode')
    ], validators=[DataRequired()]) # selecting appearance
    notifications_enabled = BooleanField('Enable Notifications') 
    default_currency = SelectField('Currency', choices=[
        ('USD', 'USD ($)'),
        ('EUR', 'EUR (€)'),
        ('GBP', 'GBP (£)'),
        ('CAD', 'CAD ($)'),
        ('AUD', 'AUD ($)')
    ], validators=[DataRequired()]) # these currencies can be expanded later if needed
    submit = SubmitField('Save Preferences')
    
class CreateGroupForm(FlaskForm):
    name = StringField('Group Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=300)])
    currency = SelectField('Currency', choices=[
        ('USD', 'USD ($)'),
        ('EUR', 'EUR (€)'),
        ('GBP', 'GBP (£)'),
        ('CAD', 'CAD ($)'),
        ('AUD', 'AUD ($)')
    ], validators=[DataRequired()]) # these currencies can be expanded later if needed
    is_open = BooleanField('Open Group to Public', default=True) # by default, groups are open to public
    submit = SubmitField('Submit')
    
class JoinGroupForm(FlaskForm):
    group_id = IntegerField('Group ID', validators=[DataRequired()])
    message = TextAreaField('Message (Optional)', validators=[Optional(), Length(max=200)])
    submit = SubmitField('Join Group')
    
class GroupGoalForm(FlaskForm):
    title = StringField('Goal Title', validators=[DataRequired(), Length(min=1, max=20)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=100)])
    target_amount = FloatField('Target Amount', validators=[InputRequired()])
    deadline = DateField('Deadline (Optional)', validators=[Optional()])
    submit = SubmitField('Submit')
    
    def validate_target_amount(self, target_amount): # additional validation to ensure target amount is positive and reasonable
        # Check the raw input first to handle invalid types
        raw_value = target_amount.raw_data[0] if target_amount.raw_data else ''
        
        # Check if field is empty
        if not raw_value or not raw_value.strip():
            raise ValidationError('This field is required.')
        
        # Check if the field data is None when conversion fails
        if target_amount.data is None:
            raise ValidationError('Target amount must be a valid number.')
        if target_amount.data <= 0:
            raise ValidationError('Target amount must be greater than 0.')
        if target_amount.data > 1000000:
            raise ValidationError('Target amount cannot exceed $1,000,000.')
    
class GroupTransactionForm(FlaskForm):
    amount = FloatField('Amount', validators=[InputRequired()])
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Submit Transaction')

    def validate_amount(self, amount): # additional validation to ensure amount is positive and reasonable
        # Check the raw input first to handle invalid types
        raw_value = amount.raw_data[0] if amount.raw_data else ''
        
        # Check if field is empty
        if not raw_value or not raw_value.strip():
            raise ValidationError('This field is required.')
        
        # Check if the field data is None when conversion fails
        if amount.data is None:
            raise ValidationError('Target amount must be a valid number.')
        if amount.data <= 0:
            raise ValidationError('Amount must be greater than 0.')
        if amount.data > 1000000:
            raise ValidationError('Amount cannot exceed $1,000,000.')
        
        
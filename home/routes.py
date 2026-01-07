from flask import render_template, url_for, flash, redirect, request, abort, session, send_file, make_response, Response
from home import app, db, bcrypt, mail
from home.db_models import User, SavingChanges, Goal, Group, GroupMember, GroupGoal, GroupTransaction, GroupJoinRequest, UserPreference, GroupPreference
from home.forms import RegistrationForm, LoginForm, UpdateAccountForm, UpdateGoalForm, GoalForm, RequestResetForm, ResetPasswordForm, ChangePasswordForm, UpdateSavingsForm, CreateGroupForm, JoinGroupForm, GroupGoalForm, GroupTransactionForm, AdjustSavingsForm, UserPreferencesForm, GroupPreferencesForm
from home.analysis import analyse_group, rate_per_day, estimate_eta, rate_breakdown, required_rate, analyse_user, user_transactions_as_movements, group_transactions_as_movements
from PIL import Image 
import secrets
import os, io
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
from datetime import datetime, timezone
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, IntegerField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, NumberRange, Optional
import matplotlib 
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def utc_now():
    return datetime.now(timezone.utc)

@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    if timestamp is None:
        return "N/A"
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    except:
        return "Invalid date"

@app.route("/home")
@app.route("/")
def home():
    return render_template("home.html", title="FundFlow")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in!', 'success')
        return redirect(url_for('login'))
    return render_template("register.html", title="Register", form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('Login Successful','success')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template("login.html", title="Login", form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/account")
@login_required
def account():
    image_file = url_for('static', filename='profile_pics/'+current_user.image_file)
    return render_template("account.html", title="Account", image_file=image_file)

@app.route("/account/edit", methods=['GET', 'POST'])
@login_required
def update_account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated', 'success')
        return redirect(url_for('account'))
    
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    
    return render_template("update_account.html", title="Update Account", form=form)

@app.route("/change_password", methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not bcrypt.check_password_hash(current_user.password, form.current_password.data):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('change_password'))
        new_hashed = bcrypt.generate_password_hash(form.new_password.data).decode('utf-8')
        current_user.password = new_hashed
        db.session.commit()
        flash('Your password has been changed', 'success')
        return redirect(url_for('account'))
    return render_template('change_password.html', title='Change Password', form=form)

@app.route("/update_savings", methods=['POST'])
@login_required
def update_savings():
    form = UpdateSavingsForm()
    if form.validate_on_submit():
        new_savings = form.savings.data
        if new_savings < 0:
            flash('Savings cannot be negative!', 'danger')
            return redirect(url_for('dashboard'))
        try:
            current_savings = current_user.savings
            saving_change = SavingChanges(
                amount=new_savings - current_savings,
                user_id=current_user.id
            )
            db.session.add(saving_change)
            current_user.savings = new_savings
            db.session.commit()
            flash('Your savings balance has been updated!', 'success')
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating savings.', 'danger')
        return redirect(url_for('dashboard'))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
        return redirect(url_for('dashboard'))

@app.route("/adjust_savings", methods=['POST'])
@login_required
def adjust_savings():
    form = AdjustSavingsForm()
    if form.validate_on_submit():
        amount = form.amount.data
        operation = form.operation.data
        
        if operation == 'subtract' and current_user.savings < amount:
            flash('Insufficient funds to subtract this amount!', 'danger')
            return redirect(url_for('dashboard'))
        
        try:
            if operation == 'add':
                current_user.savings += amount
                saving_change = SavingChanges(
                    amount=amount,
                    user_id=current_user.id
                )
                db.session.add(saving_change)
                flash(f'Added ${amount:.2f} to your savings!', 'success')
            else:  
                current_user.savings -= amount
                saving_change = SavingChanges(
                    amount=-amount,
                    user_id=current_user.id
                )
                db.session.add(saving_change)
                flash(f'Subtracted ${amount:.2f} from your savings!', 'success')
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adjusting savings: {str(e)}', 'danger')
            print(f"Error in savings adjustment: {e}")
        
        return redirect(url_for('dashboard'))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
        return redirect(url_for('dashboard'))

@app.route("/goals")
@login_required
def goals():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'incomplete')  
    
    if status_filter == 'completed':
        goals = Goal.query.filter_by(user_id=current_user.id, status='completed')\
            .order_by(Goal.date_time.desc()).paginate(page=page, per_page=5)
        analytics = analyse_user(current_user, goals, current_user.savings or 0.0)
        active_tab = 'completed'
    else:
        goals = Goal.query.filter_by(user_id=current_user.id, status='active')\
            .order_by(Goal.date_time.desc()).paginate(page=page, per_page=5)
        analytics = analyse_user(current_user, goals, current_user.savings or 0.0)
        active_tab = 'incomplete'
    
    return render_template("goals.html", title="My Goals", goals=goals, active_tab=active_tab, analytics=analytics)

@app.route("/goal/new", methods=['GET', 'POST'])
@login_required
def new_goal():
    if current_user.savings is None:
        flash('Please set your savings balance first', 'danger')
        return redirect(url_for('account'))

    form = GoalForm()
    if form.validate_on_submit():
        if form.target_amount.data <= 0:
            flash('Target amount must be greater than 0!', 'danger')
            return render_template("create_goal.html", title="New Goal", form=form, legend='New Goal')
        goal = Goal(
            title=form.title.data, 
            description=form.description.data, 
            target_amount=form.target_amount.data,
            deadline=form.deadline.data,
            category=form.category.data,
            user_id=current_user.id
        )
        db.session.add(goal)
        db.session.commit()
        flash('Your goal has been created!', 'success')
        return redirect(url_for('goals'))
    return render_template("create_goal.html", title="New Goal", form=form, legend='New Goal')

@app.route("/goal/<int:goal_id>")
@login_required
def goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    analytics = analyse_user(current_user, [goal], current_user.savings or 0.0)
    # precompute small view flags to keep template simple
    is_ready = (current_user.savings or 0.0) >= float(goal.target_amount)
    goal_view = {
        'is_ready': is_ready,
        'current_savings': float(current_user.savings or 0.0)
    }
    return render_template('goal.html', title=goal.title, goal=goal, analytics=analytics, goal_view=goal_view)

@app.route("/goal/<int:goal_id>/update", methods=['GET', 'POST'])
@login_required
def update_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        abort(403)
    form = UpdateGoalForm()
    if form.validate_on_submit():
        if form.target_amount.data <= 0:
            flash('Target amount must be greater than 0!', 'danger')
            return render_template("create_goal.html", title="New Goal", form=form, legend='New Goal')
        goal.title = form.title.data
        goal.description = form.description.data
        goal.target_amount = form.target_amount.data
        goal.deadline = form.deadline.data
        goal.category = form.category.data
        db.session.commit()
        flash('Your goal has been updated!', 'success')
        return redirect(url_for('goal', goal_id=goal_id))
    elif request.method == 'GET':
        form.title.data = goal.title
        form.description.data = goal.description
        form.target_amount.data = goal.target_amount
        form.deadline.data = goal.deadline
        form.category.data = goal.category
    return render_template("create_goal.html", title="Update Goal", form=form, legend='Update Goal')

@app.route("/goal/<int:goal_id>/complete", methods=['POST'])
@login_required
def complete_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        abort(403)
    if current_user.savings < goal.target_amount:
        flash('You do not have enough savings to complete this goal', 'danger')
        return redirect(url_for('goal', goal_id=goal_id))
    current_user.savings -= goal.target_amount
    goal.status = 'completed'
    db.session.commit()
    flash('Your goal has been completed!', 'success')
    return redirect(url_for('goals'))

@app.route("/goal/<int:goal_id>/delete", methods=['POST'])
@login_required
def delete_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        abort(403)
    db.session.delete(goal)
    db.session.commit()
    flash('Your goal has been deleted!', 'success')
    return redirect(url_for('goals'))

@app.route("/dashboard")
@login_required
def dashboard():
    savings_form = UpdateSavingsForm()
    adjust_form = AdjustSavingsForm()
    
    if request.method == 'GET':
        savings_form.savings.data = current_user.savings or 0.0
    
    goal_analytics = get_user_goal_analytics(current_user.id)

    movements = user_transactions_as_movements(current_user)
    overall_rate = rate_per_day(movements)
    
    goals = Goal.query.filter_by(user_id=current_user.id, status='active').all()
    total_remaining = sum(max(0.0, float(g.target_amount) - float(current_user.savings or 0.0)) for g in goals)
    eta = estimate_eta(total_remaining, overall_rate)
    account_analytics = {
        'rate_per_day': overall_rate,
        'eta_ts': None if eta is None else int(datetime.combine(eta, datetime.min.time()).timestamp())
    }

    return render_template("dashboard.html", title="Dashboard", 
                         savings_form=savings_form, adjust_form=adjust_form,
                         goal_analytics=goal_analytics, goals=goals,
                         account_analytics=account_analytics)

def get_user_goal_analytics(user_id: int) -> dict:
    goals = Goal.query.filter_by(user_id=user_id, status='active').all()
    user = User.query.get(user_id)
    
    analytics = {}
    analytics = analyse_user(user, goals, user.savings or 0.0)
    
    return analytics

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender=os.environ.get('EMAIL_USER'),
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
    {url_for('reset_token', token=token, _external=True)}
    If you did not make this request then simply ignore this email and no changes will be made.
    '''
    mail.send(msg)

@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request')) 
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _,f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn

@app.route("/preferences", methods=['GET', 'POST'])
@login_required
def user_preferences():
    form = UserPreferencesForm()
    if request.method == 'GET':
        form.theme.data = session.get('theme', 'light')
        form.notifications.data = session.get('notifications', True)
    
    if form.validate_on_submit():
        session['theme'] = form.theme.data
        session['notifications'] = form.notifications.data
        flash('Your preferences have been updated!', 'success')
        return redirect(url_for('user_preferences'))
    
    return render_template("user_preferences.html", title="User Preferences", form=form)

"""
Group related below
"""

@app.route("/groups")
@login_required
def groups():
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    user_groups = Group.query.join(GroupMember).filter(
        GroupMember.user_id == current_user.id,
        GroupMember.is_active == True
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    admin_groups = Group.query.join(GroupMember).filter(
        GroupMember.user_id == current_user.id,
        GroupMember.role == 'admin',
        GroupMember.is_active == True
    ).all()
    
    return render_template("groups.html", title="My Groups", 
                         user_groups=user_groups, admin_groups=admin_groups)

@app.route("/groups/create", methods=['GET', 'POST'])
@login_required
def create_group():
    form = CreateGroupForm()
    if form.validate_on_submit():
        group = Group(
            name=form.name.data,
            description=form.description.data,
            currency=form.currency.data,
            is_open=form.is_open.data
        )
        db.session.add(group)
        db.session.flush()
        
        admin_member = GroupMember(
            group_id=group.id,
            user_id=current_user.id,
            role='admin'
        )
        db.session.add(admin_member)
        db.session.commit()
        
        flash('Group created successfully!', 'success')
        return redirect(url_for('group_detail', group_id=group.id))
    
    return render_template("create_group.html", title="Create Group", form=form)

@app.route("/groups/join", methods=['GET', 'POST'])
@login_required
def join_group():
    form = JoinGroupForm()
    if form.validate_on_submit():
        group = Group.query.filter_by(id=form.group_id.data, is_active=True).first()
        
        if not group:
            flash('Group not found or inactive.', 'danger')
            return redirect(url_for('join_group'))
        
        if not group.is_open:
            flash('This group is closed and not accepting any new members or rejoins.', 'danger')
            return redirect(url_for('join_group'))
        
        existing_member = GroupMember.query.filter_by(
            group_id=group.id, 
            user_id=current_user.id,
            is_active=True
        ).first()
        
        if existing_member:
            flash('You are already an active member of this group.', 'info')
            return redirect(url_for('group_detail', group_id=group.id))
        
        existing_request = GroupJoinRequest.query.filter_by(
            group_id=group.id,
            user_id=current_user.id,
            status='pending'
        ).first()
        
        if existing_request:
            flash('You already have a pending join request for this group.', 'info')
            return redirect(url_for('join_group'))
        
        join_request = GroupJoinRequest(
            group_id=group.id,
            user_id=current_user.id,
            message=form.message.data if form.message.data else None
        )
        db.session.add(join_request)
        db.session.commit()
        
        flash('Join request sent! Waiting for admin approval.', 'success')
        
        return redirect(url_for('groups'))
    
    return render_template("join_group.html", title="Join Group", form=form)

@app.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or not member.is_active:
        abort(403)
    
    recent_goals = GroupGoal.query.filter_by(group_id=group_id, status='proposed').order_by(GroupGoal.created_at.desc()).limit(5).all()
    
    transactions = GroupTransaction.query.filter_by(group_id=group_id).order_by(GroupTransaction.occurred_at.desc()).limit(5).all()
    
    pending_goals = []
    pending_transactions = []
    if member.role == 'admin':
        pending_goals = GroupGoal.query.filter_by(
            group_id=group_id, 
            status='proposed'
        ).all()
        pending_transactions = GroupTransaction.query.filter_by(
            group_id=group_id, 
            status='pending'
        ).all()
    
    group_analytics = analyse_group(group, recent_goals, group.balance)

    tx_movements = group_transactions_as_movements(group.id)
    overall_rate = rate_per_day(tx_movements)

    active_goals = GroupGoal.query.filter_by(group_id=group_id, status='approved').all()
    total_remaining = sum(max(0.0, float(g.target_amount) - float(group.balance or 0.0)) for g in active_goals)
    eta = estimate_eta(total_remaining, overall_rate)
    group_account_analytics = {
        'rate_per_day': overall_rate,
        'eta_ts': None if eta is None else int(datetime.combine(eta, datetime.min.time()).timestamp())
    }

    return render_template("group_detail.html", title=group.name, 
                         group=group, member=member, recent_goals=recent_goals, 
                         transactions=transactions, pending_goals=pending_goals,
                         pending_transactions=pending_transactions,
                         group_analytics=group_analytics,
                         group_account_analytics=group_account_analytics)

@app.route("/groups/<int:group_id>/leave", methods=['POST'])
@login_required
def leave_group(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member:
        flash('You are not a member of this group.', 'danger')
        return redirect(url_for('groups'))
    
    if member.role == 'admin' and len(group.admin_members) == 1:
        flash('Cannot leave group as the only admin. Transfer admin role first.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    member.is_active = False
    db.session.commit()
    
    flash('Successfully left the group.', 'success')
    return redirect(url_for('groups'))

@app.route("/groups/<int:group_id>/goals/new", methods=['GET', 'POST'])
@login_required
def new_group_goal(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or not member.is_active:
        abort(403)
    
    form = GroupGoalForm()
    if form.validate_on_submit():
        goal = GroupGoal(
            group_id=group_id,
            title=form.title.data,
            description=form.description.data,
            target_amount=form.target_amount.data,
            deadline=form.deadline.data,
            category=form.category.data,
            proposer_id=current_user.id
        )
        db.session.add(goal)
        db.session.commit()
        
        flash('Goal proposed successfully! Waiting for admin approval.', 'success')
        return redirect(url_for('group_detail', group_id=group_id))
    
    return render_template("new_group_goal.html", title="Propose Group Goal", 
                         form=form, group=group)


@app.route("/groups/<int:group_id>/goals/<int:goal_id>")
@login_required
def group_goal(group_id, goal_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first()

    if not member or not member.is_active:
        abort(403)

    goal = GroupGoal.query.get_or_404(goal_id)
    if goal.group_id != group_id:
        abort(404)

    analytics_map = analyse_group(group, [goal], group.balance)
    goal_analytics = analytics_map.get(goal.id, {})
    remaining = max(0.0, float(goal.target_amount) - float(group.balance or 0.0))
    is_ready = float(group.balance or 0.0) >= float(goal.target_amount)

    return render_template('group_goal.html', title=goal.title, group=group, goal=goal,
                           goal_analytics=goal_analytics, remaining=remaining, is_ready=is_ready)

@app.route("/groups/<int:group_id>/goals/<int:goal_id>/approve", methods=['POST'])
@login_required
def approve_group_goal(group_id, goal_id):
    try:
        group = Group.query.get_or_404(group_id)
        member = GroupMember.query.filter_by(
            group_id=group_id, 
            user_id=current_user.id
        ).first()
        
        if not member or member.role != 'admin':
            flash('You do not have permission to approve goals.', 'danger')
            return redirect(url_for('group_detail', group_id=group_id))
        
        goal = GroupGoal.query.get_or_404(goal_id)
        if goal.group_id != group_id:
            flash('Goal not found in this group.', 'danger')
            return redirect(url_for('group_detail', group_id=group_id))
        
        if goal.status != 'proposed':
            flash(f'This goal is already {goal.status} and cannot be approved.', 'warning')
            return redirect(url_for('group_detail', group_id=group_id))
        
        if group.balance < goal.target_amount:
            flash(f'Insufficient group funds. Current balance: ${group.balance:.2f}, Goal amount: ${goal.target_amount:.2f}', 'danger')
            return redirect(url_for('group_detail', group_id=group_id))

        transaction = GroupTransaction(
            group_id=group_id,
            user_id=current_user.id,
            amount=-goal.target_amount,
            description=f"Goal approved: {goal.title}",
            status='approved',
            approved_by_id=current_user.id,
            approved_at=utc_now()
        )
        db.session.add(transaction)
        
        goal.status = 'approved'
        goal.approved_by_id = current_user.id
        goal.approved_at = utc_now()
        
        group.balance -= goal.target_amount
        
        db.session.commit()
        flash(f'Goal "{goal.title}" approved successfully! ${goal.target_amount:.2f} deducted from group savings.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving goal: {str(e)}', 'danger')
        print(f"Error in goal approval: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('group_detail', group_id=group_id))

@app.route("/groups/<int:group_id>/goals/<int:goal_id>/deny", methods=['POST'])
@login_required
def deny_group_goal(group_id, goal_id):
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role != 'admin':
        abort(403)
    
    goal = GroupGoal.query.get_or_404(goal_id)
    if goal.group_id != group_id:
        abort(404)
    
    goal.status = 'denied'
    goal.approved_by_id = current_user.id
    goal.approved_at = utc_now()
    db.session.commit()
    
    flash('Goal denied.', 'info')
    return redirect(url_for('group_detail', group_id=group_id))

@app.route("/groups/<int:group_id>/goals", methods=['GET', 'POST'])
@login_required
def view_group_goals(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or not member.is_active:
        abort(403)

    status_filter = request.args.get('status', 'proposed')
    page = request.args.get('page', 1, type=int)
    per_page = 8

    goals = GroupGoal.query.filter_by(
        group_id=group_id,
        status=status_filter
    ).order_by(GroupGoal.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    active_tab = status_filter

    tx_movements = group_transactions_as_movements(group.id)
    overall_rate = rate_per_day(tx_movements)
    approved_goals = GroupGoal.query.filter_by(group_id=group_id, status='approved').all()
    total_remaining = sum(max(0.0, float(g.target_amount) - float(group.balance or 0.0)) for g in approved_goals)
    eta = estimate_eta(total_remaining, overall_rate)
    group_account_analytics = {
        'rate_per_day': overall_rate,
        'eta_ts': None if eta is None else int(datetime.combine(eta, datetime.min.time()).timestamp())
    }

    goals_analysis = {}
    for g in goals.items:
        remaining = max(0.0, float(g.target_amount) - float(group.balance or 0.0))
        is_ready = float(group.balance or 0.0) >= float(g.target_amount)
        progress_percent = (float(group.balance or 0.0) / float(g.target_amount) * 100) if g.target_amount and g.target_amount > 0 else 0.0
        days = 30
        try:
            if getattr(g, 'deadline', None):
                dl = g.deadline
                if isinstance(dl, datetime):
                    dl_date = dl.date()
                else:
                    dl_date = dl
                days_left = (dl_date - datetime.today().date()).days
                days = max(1, days_left) if days_left is not None else 30
        except Exception:
            days = 30
        required_daily_30 = remaining / float(days) if days > 0 else None
        goals_analysis[g.id] = {
            'remaining': remaining,
            'is_ready': is_ready,
            'progress_percent': progress_percent,
            'required_daily_30': required_daily_30,
        }

    return render_template("group_goals.html", title=f"{group.name} Goals",
                           group=group, goals=goals, active_tab=active_tab, group_id=group_id,
                           group_account_analytics=group_account_analytics,
                           goals_analysis=goals_analysis)

@app.route("/groups/<int:group_id>/transactions/new", methods=['GET', 'POST'])
@login_required
def new_group_transaction(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or not member.is_active:
        abort(403)
    
    form = GroupTransactionForm()
    if form.validate_on_submit():
        is_admin = member.role == 'admin'
        
        transaction = GroupTransaction(
            group_id=group_id,
            user_id=current_user.id,
            amount=form.amount.data,
            description=form.description.data,
            status='approved' if is_admin else 'pending' 
        )
        
        if is_admin:
            transaction.approved_by_id = current_user.id
            transaction.approved_at = utc_now()
            group.balance += form.amount.data
        
        db.session.add(transaction)
        db.session.commit()
        
        if is_admin:
            flash('Transaction added successfully!', 'success')
        else:
            flash('Transaction request submitted! Waiting for admin approval.', 'success')
        
        return redirect(url_for('group_detail', group_id=group_id))
    
    return render_template("new_group_transaction.html", title="New Group Transaction", 
                         form=form, group=group, member=member)  

@app.route("/groups/<int:group_id>/transactions/<int:transaction_id>/approve", methods=['POST'])
@login_required
def approve_group_transaction(group_id, transaction_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role != 'admin':
        abort(403)
    
    transaction = GroupTransaction.query.get_or_404(transaction_id)
    if transaction.group_id != group_id:
        abort(404)
    
    try:
        group.balance += transaction.amount
        
        transaction.status = 'approved'
        transaction.approved_by_id = current_user.id
        transaction.approved_at = utc_now()
        
        db.session.commit()
        flash('Transaction approved successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving transaction: {str(e)}', 'danger')
        print(f"Error in transaction approval: {e}")
    
    return redirect(url_for('group_detail', group_id=group_id))

@app.route("/groups/<int:group_id>/transactions/<int:transaction_id>/deny", methods=['POST'])
@login_required
def deny_group_transaction(group_id, transaction_id):
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role != 'admin':
        abort(403)
    
    transaction = GroupTransaction.query.get_or_404(transaction_id)
    if transaction.group_id != group_id:
        abort(404)
    
    transaction.status = 'denied'
    transaction.approved_by_id = current_user.id
    transaction.approved_at = utc_now()
    db.session.commit()
    
    flash('Transaction denied.', 'info')
    return redirect(url_for('group_detail', group_id=group_id))

@app.route("/groups/<int:group_id>/analytics")
@login_required
def group_analytics(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or not member.is_active:
        abort(403)
    
    total_balance = group.total_balance
    total_members = len([m for m in group.members if m.is_active])
    total_goals = len(group.goals)
    proposed_goals = len([g for g in group.goals if g.status == 'proposed'])
    approved_goals = len([g for g in group.goals if g.status == 'approved'])
    denied_goals = len([g for g in group.goals if g.status == 'denied'])
    
    recent_transactions = GroupTransaction.query.filter_by(
        group_id=group_id, 
        status='approved'
    ).order_by(GroupTransaction.occurred_at.desc()).limit(30).all()

    goals = GroupGoal.query.filter_by(group_id=group_id).all()
    group_analytics = analyse_group(group, goals, group.balance)

    tx_movements = group_transactions_as_movements(group.id)
    overall_rate = rate_per_day(tx_movements)
    approved_goals_list = [g for g in goals if g.status == 'approved']
    total_remaining = sum(max(0.0, float(g.target_amount) - float(group.balance or 0.0)) for g in approved_goals_list)
    eta = estimate_eta(total_remaining, overall_rate)
    group_account_analytics = {
        'rate_per_day': overall_rate,
        'eta_ts': None if eta is None else int(datetime.combine(eta, datetime.min.time()).timestamp())
    }
    
    monthly_data = {}
    for tx in recent_transactions:
        month = tx.occurred_at.strftime('%Y-%m')
        if month not in monthly_data:
            monthly_data[month] = {'contributions': 0, 'expenses': 0}
        
        if tx.amount > 0:
            monthly_data[month]['contributions'] += tx.amount
        else:
            monthly_data[month]['expenses'] += abs(tx.amount)
    
    return render_template("group_analytics.html", title=f"{group.name} Analytics", 
                         group=group, member=member, total_balance=total_balance,
                         total_members=total_members, total_goals=total_goals,
                         proposed_goals=proposed_goals, approved_goals=approved_goals, denied_goals=denied_goals,
                         monthly_data=monthly_data,
                         group_analytics=group_analytics,
                         group_account_analytics=group_account_analytics,
                         goals=goals)

@app.route("/groups/<int:group_id>/members")
@login_required
def group_members(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or not member.is_active:
        abort(403)
    
    return render_template("group_members.html", title=f"{group.name} Members", 
                         group=group, member=member, current_user_member=member)

@app.route("/groups/<int:group_id>/members/<int:member_id>/promote", methods=['POST'])
@login_required
def promote_member(group_id, member_id):
    group = Group.query.get_or_404(group_id)
    admin_member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not admin_member or admin_member.role != 'admin':
        abort(403)
    
    member_to_promote = GroupMember.query.get_or_404(member_id)
    if member_to_promote.group_id != group_id:
        abort(404)
    
    member_to_promote.role = 'admin'
    db.session.commit()
    
    flash('Member promoted to admin successfully!', 'success')
    return redirect(url_for('group_members', group_id=group_id))

@app.route("/groups/<int:group_id>/members/<int:member_id>/demote", methods=['POST'])
@login_required
def demote_member(group_id, member_id):
    group = Group.query.get_or_404(group_id)
    admin_member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not admin_member or admin_member.role != 'admin':
        abort(403)
    
    member_to_demote = GroupMember.query.get_or_404(member_id)
    if member_to_demote.group_id != group_id:
        abort(404)
    
    if member_to_demote.user_id == current_user.id:
        flash('You cannot demote yourself.', 'danger')
        return redirect(url_for('group_members', group_id=group_id))
    
    member_to_demote.role = 'member'
    db.session.commit()
    
    flash('Member demoted to regular member.', 'info')
    return redirect(url_for('group_members', group_id=group_id))

@app.route("/groups/<int:group_id>/members/<int:member_id>/remove", methods=['POST'])
@login_required
def remove_member(group_id, member_id):
    admin_member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not admin_member or admin_member.role != 'admin':
        abort(403)
    
    member_to_remove = GroupMember.query.get_or_404(member_id)
    if member_to_remove.group_id != group_id:
        abort(404)
    
    if member_to_remove.user_id == current_user.id:
        flash('You cannot remove yourself. Transfer admin role first.', 'danger')
        return redirect(url_for('group_members', group_id=group_id))
    
    member_to_remove.is_active = False
    db.session.commit()
    
    flash('Member removed from group.', 'info')
    return redirect(url_for('group_members', group_id=group_id))

@app.route("/groups/<int:group_id>/join-requests")
@login_required
def group_join_requests(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role != 'admin':
        abort(403)
    
    pending_requests = GroupJoinRequest.query.filter_by(
        group_id=group_id,
        status='pending'
    ).order_by(GroupJoinRequest.requested_at.desc()).all()
    
    return render_template("group_join_requests.html", title=f"{group.name} Join Requests", 
                         group=group, member=member, pending_requests=pending_requests)

@app.route("/groups/<int:group_id>/join-requests/<int:request_id>/approve", methods=['POST'])
@login_required
def approve_join_request(group_id, request_id):
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role != 'admin':
        abort(403)
    
    join_request = GroupJoinRequest.query.get_or_404(request_id)
    if join_request.group_id != group_id:
        abort(404)
    
    try:
        existing_member = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=join_request.user_id
        ).first()
        
        if existing_member:
            existing_member.is_active = True
            existing_member.joined_at = utc_now()
        else:
            new_member = GroupMember(
                group_id=group_id,
                user_id=join_request.user_id,
                role='member'
            )
            db.session.add(new_member)
        
        join_request.status = 'approved'
        join_request.responded_at = utc_now()
        join_request.responded_by_id = current_user.id
        db.session.commit()
        
        if existing_member:
            flash(f'{join_request.user.username} has been reactivated as a member!', 'success')
        else:
            flash(f'{join_request.user.username} has been approved to join the group!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving join request: {str(e)}', 'danger')
        print(f"Error in join request approval: {e}")
    
    return redirect(url_for('group_join_requests', group_id=group_id))

@app.route("/groups/<int:group_id>/join-requests/<int:request_id>/deny", methods=['POST'])
@login_required
def deny_join_request(group_id, request_id):
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role != 'admin':
        abort(404)
    
    join_request = GroupJoinRequest.query.get_or_404(request_id)
    if join_request.group_id != group_id:
        abort(404)
    
    join_request.status = 'denied'
    join_request.responded_at = utc_now()
    join_request.responded_by_id = current_user.id
    db.session.commit()
    
    flash(f'{join_request.user.username}\'s join request has been denied.', 'info')
    return redirect(url_for('group_join_requests', group_id=group_id))

@app.route("/groups/<int:group_id>/preferences", methods=['GET', 'POST'])
@login_required
def group_preferences(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role != 'admin':
        flash('Only group admins can access group preferences.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    preferences = GroupPreference.query.filter_by(group_id=group_id).first()
    if not preferences:
        preferences = GroupPreference(
            group_id=group_id,
            is_open=group.is_open,  
            default_currency=group.currency
        )
        db.session.add(preferences)
        db.session.commit()
    
    form = GroupPreferencesForm()
    
    if form.validate_on_submit():
        try:
            group.is_open = form.is_open.data
            group.currency = form.default_currency.data
            
            preferences.is_open = form.is_open.data
            preferences.default_currency = form.default_currency.data
            preferences.require_goal_approval = form.require_goal_approval.data
            preferences.require_transaction_approval = form.require_transaction_approval.data
            preferences.updated_at = utc_now()
            
            db.session.commit()
            flash('Group preferences have been updated!', 'success')
            return redirect(url_for('group_preferences', group_id=group_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating preferences: {str(e)}', 'danger')
            print(f"Error in group preferences update: {e}")
    
    elif request.method == 'GET':
        form.is_open.data = preferences.is_open
        form.default_currency.data = preferences.default_currency
        form.require_goal_approval.data = preferences.require_goal_approval
        form.require_transaction_approval.data = preferences.require_transaction_approval  
    
    return render_template("group_preferences.html", title=f"{group.name} Preferences", 
                         form=form, group=group, member=member)

"""
Data analysis below 
"""
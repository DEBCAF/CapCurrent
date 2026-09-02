# imports
import io
from home import app, db, bcrypt # Importing the Flask app instance defined in __init__.py
from flask import render_template, url_for, flash, redirect, request, abort, session, send_file # Importing flask libraries
from flask_login import login_user, current_user, logout_user, login_required # Importing flask login functions
from home.forms import RegistrationForm, LoginForm, UpdateAccountForm, ChangePasswordForm, UpdateSavingsForm, AdjustSavingsForm, GoalForm, UpdateGoalForm, UserPreferencesForm, CreateGroupForm, JoinGroupForm, GroupGoalForm, GroupTransactionForm # Importing the forms created in forms.py
from home.db_models import User, SavingChanges, Goal, UserPreference, Group, GroupMember, GroupGoal, GroupTransaction, GroupJoinRequest # Importing database models
from datetime import datetime, timezone # used for date and time operations
from home.analysis import analyse_group, rate_per_day, estimate_eta, rate_breakdown, required_rate, analyse_user, user_transactions_as_movements, group_transactions_as_movements, _to_dataframe # Importing analysis utilities
from home.plotting import plot_cumulative_savings, plot_daily_change # Importing plotting utilities

def utc_now(): # helper function to get current UTC time with timezone info
    return datetime.now(timezone.utc)

import secrets # generates random number better than random 
import os  # used for file system management 
from PIL import Image # immage processing library, can be used to open, resize, crop and save images

# Creating a route for the home page
@app.route('/')
def home():
    return render_template('home.html', title='FundFlow')

# Creating a route for the registration page
@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: # if user is already logged in, redirect to home page
        return redirect(url_for('dashboard'))
    form = RegistrationForm() # create an instance of the registration form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        # Saves user to the database
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8') # hash the password
        user = User(username=form.username.data, email=form.email.data, password=hashed_password) # create user instance
        db.session.add(user) # add user to the database session
        db.session.commit() # commit the session to save user
        flash('Your account has been created! Please login:', 'success') # flash success message if successful
        return redirect(url_for('login')) # redirect to login page to login after successful registration
    return render_template("register.html", title="Register", form=form) # redirect back to registration page if form is not valid

# Creating a route for the login page
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # if user is already logged in, redirect to home page
        return redirect(url_for('dashboard'))
    form = LoginForm() # create an instance of the login form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        user = User.query.filter_by(email=form.email.data).first() # search for user by email
        if user and bcrypt.check_password_hash(user.password, form.password.data): # verify password
            login_user(user, remember=form.remember.data) # log in the user
            session.pop('_flashes', None) # from later debugging since flashes please log in after successful login
            flash('Login Successful','success') # flash success message
            next_page = request.args.get('next') # get the next page if user was previously trying to access another page
            return redirect(next_page) if next_page else redirect(url_for('dashboard')) # redirect to next page or home
        else:
            # clearer error messages
            if not user:
                flash('No such email on the system, please sign up', 'danger')
            elif not bcrypt.check_password_hash(user.password, form.password.data):
                flash('Incorrect password, try again', 'danger')
            else:
                flash('Login Unsuccessful. Please check email and password', 'danger') 
    return render_template("login.html", title="Login", form=form) # redirect back to login page if form is not valid

# Creating a route for logging out
@app.route("/logout")
def logout():
    logout_user() # library function to log out the current user
    flash('You have logged out.', 'success') # flash success message
    return redirect(url_for('home')) # redirect to home page after logging 

# Creating a route for the account page
@app.route("/account")
@login_required # requires user to be logged in to access
def account():
    image_file = url_for('static', filename='profile_pics/'+current_user.image_file) # links to path of user's profile image
    return render_template("account.html", title="Account", image_file=image_file)

# Creating a route for updating account information
@app.route("/account/edit", methods=['GET', 'POST'])
@login_required 
def update_account():
    form = UpdateAccountForm() # create an instance of the update account form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        if form.picture.data: # run this only if user has entered new image file
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        # changes user information in current user record buffer
        current_user.username = form.username.data 
        current_user.email = form.email.data
        db.session.commit() # make changes to the database
        flash('Your account has been updated!', 'success') # flask success message 
        return redirect(url_for('account')) # redirect back to account page
    
    # the following will prefill the form when it first loads, reminding the user of their current information
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    
    return render_template("update_account.html", title="Update Account", form=form)

# more complex function dedicated to the saving of image files
def save_picture(form_picture):
    random_hex = secrets.token_hex(8) # generates new random number
    _,f_ext = os.path.splitext(form_picture.filename) # splits original user file name into base and extension and only retrieve extension
    picture_fn = random_hex + f_ext # creates new file name by concatenating the random hex and the file extension
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn) # creates a file system path that puts uploads into profile_pics
    output_size = (125, 125) # tuple indicating the max width and height 
    i = Image.open(form_picture) # uses Pillow to open the file the user uploaded 
    i.thumbnail(output_size) # resizes the dimensions of the file 
    i.save(picture_path) # saves the file to the path specified 
    return picture_fn # returns the filename to be stored in database

# Creating a route for changing passwords
@app.route("/change_password", methods=['GET', 'POST'])
@login_required
def change_password(): # only proceed if form is valid upon submission
    form = ChangePasswordForm() # create an instance of the change password form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        if not bcrypt.check_password_hash(current_user.password, form.current_password.data): # checks if the password the user has entered is correct
            flash('Current password is incorrect.', 'danger') # flash error nessage
            return redirect(url_for('change_password')) # reloads the page 
        new_hashed = bcrypt.generate_password_hash(form.new_password.data).decode('utf-8') # hashes the new password
        current_user.password = new_hashed # changes the user password to the new password
        db.session.commit() # save changes in the database 
        flash('Your password has been changed!', 'success') # flash success message 
        return redirect(url_for('account')) # redirects back to account page
    return render_template('change_password.html', title='Change Password', form=form)

# Creating a route for the dashboard page
@app.route("/dashboard")
@login_required
def dashboard():
    savings_form = UpdateSavingsForm() # create an instance of the update savings form
    adjust_form = AdjustSavingsForm() # create an instance of the adjust savings form
    
    # the following will prefill the form when it first loads, reminding the user of their current information
    if request.method == 'GET':
        savings_form.savings.data = current_user.savings or 0.0
    
    # get savings history
    page = request.args.get('page', 1, type=int) # pagination page number, default is 1
    savings_history = SavingChanges.query.filter_by(user_id=current_user.id)\
        .order_by(SavingChanges.date_time.desc()).paginate(page=page, per_page=10) # pagination for savings history, max 10 per page
    
    # manually getting movements
    movements = user_transactions_as_movements(current_user)
    # caluclating rate 
    rate = rate_per_day(movements)
    # getting all active goals
    goals = Goal.query.filter_by(user_id=current_user.id, status='active').all()
    # summing all target amounts of active goals 
    total_remaining = sum(max(0.0, float(g.target_amount) - float(current_user.savings or 0.0)) for g in goals)
    # calculating eta to complete all goals
    eta = estimate_eta(total_remaining, rate)
    
    # check if have enough data to generate graphs
    user_savings_graph = movements is not None and len(movements) > 0
    user_daily_graph = movements is not None and len(movements) > 0
    
    return render_template("dashboard.html", title="Dashboard", savings_form=savings_form, adjust_form=adjust_form, savings_history=savings_history, rate=rate or 0, eta=eta or 0, user_savings_graph=user_savings_graph, user_daily_graph=user_daily_graph) 

# Creating a route for updating savings balance
@app.route("/update_savings", methods=['POST'])
@login_required
def update_savings():
    form = UpdateSavingsForm() # create an instance of the update savings form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        new_savings = form.savings.data # get the new savings value from the form
        if new_savings < 0: # check if new savings is negative
            flash('Savings cannot be negative.', 'danger') # flash error message
            return redirect(url_for('dashboard')) # redirect back to dashboard page
        try: # try to catch potential errors, this also tries to save into table
            current_savings = current_user.savings # get the current savings value
            saving_change = SavingChanges(
                amount=new_savings - current_savings, # calculate the change in savings
                user_id=current_user.id
            ) # create a new SavingChanges record to be saved into table
            db.session.add(saving_change) # add the saving change record to the database session
            current_user.savings = new_savings # update the current user's savings
            db.session.commit() # save changes in the database 
            flash('Your savings balance has been updated!', 'success') # flash success message
        except ValueError as e: # catch value errors first
            db.session.rollback()
            flash(str(e), 'danger') # flash error message with error details
        except Exception as e: # catch all other exceptions
            db.session.rollback()
            flash('An error occurred while updating savings.', 'danger') # flash generic error message
        return redirect(url_for('dashboard')) # redirect back to dashboard page
    else: # if form is not valid
        # display all form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
        return redirect(url_for('dashboard')) # redirect back to dashboard page

# Creating a route for adjusting savings balance
@app.route("/adjust_savings", methods=['POST'])
@login_required
def adjust_savings():
    form = AdjustSavingsForm() # create an instance of the adjust savings form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        amount = form.amount.data # get the amount to adjust
        operation = form.operation.data # get the operation type 
        
        # check for insufficient funds when subtracting
        if operation == 'subtract' and current_user.savings < amount:
            flash('Insufficient funds to subtract this amount.', 'danger') # flash error message
            return redirect(url_for('dashboard')) # redirect back to dashboard page
        
        try: # try to catch potential errors, this also tries to save into table
            if operation == 'add':
                current_user.savings += amount # add amount to current savings
                saving_change = SavingChanges(
                    amount=amount,
                    user_id=current_user.id
                ) # create a new SavingChanges record to be saved into table
                db.session.add(saving_change) # add the saving change record to the database session
                flash(f'Added ${amount:.2f} to your savings!', 'success') # flash success message
            else:  
                current_user.savings -= amount # subtract amount from current savings
                saving_change = SavingChanges(
                    amount=-amount,
                    user_id=current_user.id
                ) # create a new SavingChanges record to be saved into table
                db.session.add(saving_change) # add the saving change record to the database session
                flash(f'Subtracted ${amount:.2f} from your savings!', 'success') # flash success message
            
            db.session.commit() # save changes in the database
            
        except Exception as e:
            db.session.rollback() # rollback in case of error
            # flash error message with error details
            flash(f'Error adjusting savings: {str(e)}', 'danger') 
            print(f"Error in savings adjustment: {e}")
        
        return redirect(url_for('dashboard')) # redirect back to dashboard page
    else: # if form is not valid
        # display all form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
        return redirect(url_for('dashboard'))

# Creating a route for the goals page
@app.route("/goals")
@login_required
def goals():
    page = request.args.get('page', 1, type=int) # pagination page number, default is 1
    status_filter = request.args.get('status', 'all') # filter for goal status, default is all
    
    # Query all goals for the user
    query = Goal.query.filter_by(user_id=current_user.id)
    
    # Apply status filter
    if status_filter == 'completed':
        query = query.filter_by(status='completed')
        active_tab = 'completed'
    elif status_filter == 'active':
        query = query.filter_by(status='active')
        active_tab = 'active'
    else:
        active_tab = 'all'
    
    goals = query.order_by(Goal.date_time.desc()).paginate(page=page, per_page=5) # pagination for goals, max 5 per page
    
    return render_template("goals.html", title="My Goals", goals=goals, active_tab=active_tab)

# Creating a route for creating a new goal
@app.route("/goal/new", methods=['GET', 'POST'])
@login_required
def new_goal():
    if current_user.savings is None: # make sure user has set savings before creating goals
        flash('Please set your savings balance first', 'danger') # flash error message
        return redirect(url_for('account'))

    form = GoalForm() # create an instance of the goal form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        if form.target_amount.data <= 0: # validate target amount
            flash('Target amount must be greater than 0!', 'danger') # flash error message
            return render_template("create_goal.html", title="New Goal", form=form, legend='New Goal')
        goal = Goal(
            title=form.title.data, 
            description=form.description.data, 
            target_amount=form.target_amount.data,
            deadline=form.deadline.data,
            user_id=current_user.id
        ) # create a new Goal record to be added into the database
        db.session.add(goal) # add the goal record to the database session
        db.session.commit() # commit the session to save goal
        flash('Your goal has been created!', 'success')
        return redirect(url_for('goals'))
    return render_template("create_goal.html", title="New Goal", form=form, legend='New Goal')

# Creating a route for viewing a specific goal
@app.route("/goal/<int:goal_id>")
@login_required
def goal(goal_id):
    goal = Goal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
    if goal.user_id != current_user.id: # check if the goal belongs to the current user
        abort(403)
    analytics = analyse_user(current_user, [goal], current_user.savings or 0.0)
    return render_template('goal.html', title=goal.title, goal=goal, analytics=analytics)

# Creating a route for updating a goal
@app.route("/goal/<int:goal_id>/update", methods=['GET', 'POST'])
@login_required
def update_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
    if goal.user_id != current_user.id: # check if the goal belongs to the current user
        abort(403)
    form = UpdateGoalForm() # create an instance of the update goal form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        if form.target_amount.data <= 0: # validate target amount
            flash('Target amount must be greater than 0!', 'danger')
            return render_template("create_goal.html", title="New Goal", form=form, legend='New Goal')
        # obtain new goal information
        goal.title = form.title.data
        goal.description = form.description.data
        goal.target_amount = form.target_amount.data
        goal.deadline = form.deadline.data
        db.session.commit() # save changes in the database
        flash('Your goal has been updated!', 'success')
        return redirect(url_for('goal', goal_id=goal_id))
    elif request.method == 'GET': # prefill form with existing goal data so that users dont have to reenter unchanged values
        form.title.data = goal.title
        form.description.data = goal.description
        form.target_amount.data = goal.target_amount
        form.deadline.data = goal.deadline
    return render_template("create_goal.html", title="Update Goal", form=form, legend='Update Goal')

# Creating a route for completing a goal
@app.route("/goal/<int:goal_id>/complete", methods=['POST'])
@login_required
def complete_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
    if goal.user_id != current_user.id: # check if the goal belongs to the current user
        abort(403)
    if current_user.savings < goal.target_amount: # checks if user has enough savings to complete the goal
        flash('You do not have enough savings to complete this goal', 'danger')
        return redirect(url_for('goal', goal_id=goal_id))
    current_user.savings -= goal.target_amount # deduct the target amount from user's savings
    goal.status = 'completed' # set goal status to completed
    saving_change = SavingChanges(
                    amount=-goal.target_amount,
                    user_id=current_user.id
                ) # create a new SavingChanges record to be saved into table
    db.session.add(saving_change) # add the saving change record to the database session
    db.session.commit() # save changes in the database
    flash('Your goal has been completed!', 'success')
    return redirect(url_for('goals'))

# Creating a route for deleting a goal
@app.route("/goal/<int:goal_id>/delete", methods=['POST'])
@login_required
def delete_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
    if goal.user_id != current_user.id: # check if the goal belongs to the current user
        abort(403)
    db.session.delete(goal) # delete the goal record from the database session
    db.session.commit() # save changes in the database
    flash('Your goal has been deleted!', 'success')
    return redirect(url_for('goals'))

# Creating a route for user preferences
@app.route("/preferences", methods=['GET', 'POST'])
@login_required
def user_preferences():
    preference = UserPreference.query.filter_by(user_id=current_user.id).first()
    form = UserPreferencesForm() # create an instance of the user preference form
    if preference is None:
        preference = UserPreference(
            user_id=current_user.id,
            theme="light",
            notifications_enabled=True,
            default_currency='USD'
        )
        db.session.add(preference)
    if request.method == 'GET': # prefill with existing information
        form.theme.data = preference.theme
        form.notifications_enabled.data = preference.notifications_enabled
        form.default_currency.data = preference.default_currency
    
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        preference.theme = form.theme.data
        preference.notifications_enabled = form.notifications_enabled.data
        preference.default_currency = form.default_currency.data
        
        db.session.commit()
        
        # set session theme
        session['theme'] = preference.theme
        flash('Your preferences have been updated!', 'success')
        return redirect(url_for('user_preferences'))
    
    return render_template("user_preferences.html", title="User Preferences", form=form)

# Group Related Routes from here

# Creating a route for viewing all groups
@app.route("/groups")
@login_required
def groups():
    page = request.args.get('page', 1, type=int) # pagination page number, default is 1
    per_page = 6
    
    # multi table select to get all groups the user is a member of
    user_groups = Group.query.join(GroupMember).filter(
        GroupMember.user_id == current_user.id,
        GroupMember.is_active == True
    ).paginate(page=page, per_page=per_page, error_out=False) # paginate user groups, max 6 per page
    
    # multi table select to get all groups the user is an admin of
    admin_groups = Group.query.join(GroupMember).filter(
        GroupMember.user_id == current_user.id,
        GroupMember.role == 'admin',
        GroupMember.is_active == True
    ).all()
    
    return render_template("groups.html", title="My Groups", 
                         user_groups=user_groups, admin_groups=admin_groups)

# Creating a route for creating a new group
@app.route("/groups/create", methods=['GET', 'POST'])
@login_required
def create_group():
    form = CreateGroupForm() # create an instance of the create group form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        group = Group(
            name=form.name.data,
            description=form.description.data,
            currency=form.currency.data,
            is_open=form.is_open.data
        ) # create a new Group record to be added into the database
        db.session.add(group) # add the group record to the database session
        db.session.flush() # flush to get group ID before commit
        
        admin_member = GroupMember(
            group_id=group.id,
            user_id=current_user.id,
            role='admin'
        ) # create a new GroupMember record to make the creator the admin of the group
        db.session.add(admin_member) # add the admin member record to the database session
        db.session.commit() # commit the session to save group and admin 
        
        flash('Group created successfully!', 'success')
        return redirect(url_for('groups', group_id=group.id))
    
    return render_template("create_group.html", title="Create Group", form=form)

# Creating a route for updating group information 
@app.route("/groups/<int:group_id>/update", methods=['GET', 'POST'])
@login_required
def update_group(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(
            group_id=group_id, 
            user_id=current_user.id
        ).first() # get member information of current user in the group
        
    if not member or member.role != 'admin': # only admins can update group information
        flash('You do not have permission to update group information.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    form = CreateGroupForm()
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        group.name = form.name.data
        group.description = form.description.data
        group.currency = form.currency.data
        group.is_open = form.is_open.data
        db.session.commit() # save changes in the database
        flash('Group information has been updated!', 'success')
        return redirect(url_for('group_detail', group_id=group_id))
    
    elif request.method == 'GET': # prefill form with existing goal data so that users dont have to reenter unchanged values
        form.name.data = group.name
        form.description.data = group.description
        form.currency.data = group.currency
        form.is_open.data = group.is_open
        db.session.commit() # commit the session to save group information
    return render_template("create_group.html", title="Update Group Information", form=form, group_id=group_id, group=group)

# Creating a route for joining a group
@app.route("/groups/join", methods=['GET', 'POST'])
@login_required
def join_group():
    form = JoinGroupForm() # create an instance of the join group form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        group = Group.query.filter_by(id=form.group_id.data, is_active=True).first() # find group by ID and ensure it is active
        
        if not group: # if group returns null, it does not exist or is inactive
            flash('Group not found or inactive.', 'danger')
            return redirect(url_for('join_group'))
        
        if not group.is_open: # if group is closed
            flash('This group is closed and not accepting any new members or rejoins.', 'danger')
            return redirect(url_for('join_group'))
        
        existing_member = GroupMember.query.filter_by(
            group_id=group.id, 
            user_id=current_user.id,
            is_active=True
        ).first() # check if user is already an active member of the group
        
        if existing_member: # if user is already an active member redirect to group details
            flash('You are already an active member of this group.', 'danger')
            return redirect(url_for('group_detail', group_id=group.id))
        
        # Check for any existing join request
        existing_request = GroupJoinRequest.query.filter_by(
            group_id=group.id,
            user_id=current_user.id
        ).first() # check if user already has any join request for the group
        
        if existing_request:
            if existing_request.status == 'pending': # if user already has a pending request, do not allow another
                flash('You already have a pending join request for this group.', 'danger')
                return redirect(url_for('join_group'))
            else:
                # User previously had a request that was approved/denied, update it to pending for rejoin
                existing_request.status = 'pending'
                existing_request.message = form.message.data if form.message.data else None
                existing_request.requested_at = utc_now()
                existing_request.responded_at = None
                existing_request.responded_by_id = None
                db.session.commit() # commit the session to update join request
                flash('Join request sent! Waiting for admin approval.', 'success')
                return redirect(url_for('groups'))
        
        join_request = GroupJoinRequest(
            group_id=group.id,
            user_id=current_user.id,
            message=form.message.data if form.message.data else None
        ) # create a new GroupJoinRequest record to be added into the database
        db.session.add(join_request) # add the join request record to the database session
        db.session.commit() # commit the session to save join request
        
        flash('Join request sent! Waiting for admin approval.', 'success')
        
        return redirect(url_for('groups'))
    
    return render_template("join_group.html", title="Join Group", form=form)

# Creating a route for viewing all join requests for a group
@app.route("/groups/<int:group_id>/join-requests")
@login_required
def group_join_requests(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or member.role != 'admin': # only admins can view join requests
        abort(403)
    
    # retrieve all pending join requests for this group
    pending_requests = GroupJoinRequest.query.filter_by(
        group_id=group_id,
        status='pending'
    ).order_by(GroupJoinRequest.requested_at.desc()).all()
    
    return render_template("group_join_requests.html", title=f"{group.name} - Join Requests",
                         group=group, pending_requests=pending_requests)

# Creating a route for approving a join request
@app.route("/groups/<int:group_id>/join-requests/<int:request_id>/approve", methods=['POST'])
@login_required
def approve_join_request(group_id, request_id):
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or member.role != 'admin': # only admins can approve join request
        abort(403)
    
    join_request = GroupJoinRequest.query.get_or_404(request_id) # get any join requests by ID or return 404 if not found 
    if join_request.group_id != group_id:
        abort(404)
    
    try:
        # check if user is already in the database and was previously a member
        existing_member = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=join_request.user_id
        ).first()
        
        if existing_member: # if user was previously a member, reactivate them
            existing_member.is_active = True
            existing_member.joined_at = utc_now()
        else:
            new_member = GroupMember(
                group_id=group_id,
                user_id=join_request.user_id,
                role='member'
            ) # create a new GroupMember record to be added into the database
            db.session.add(new_member) # add the new member record to the database session
        
        join_request.status = 'approved' # update join request status to approved
        join_request.responded_at = utc_now()
        join_request.responded_by_id = current_user.id
        db.session.commit()
        # flash different messages based on whether user was reactivated or newly approved
        if existing_member:
            flash(f'{join_request.user.username} has been reactivated as a member!', 'success')
        else:
            flash(f'{join_request.user.username} has been approved to join the group!', 'success')
        
    except Exception as e:
        # preserve database integrity in case of error
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
    ).first() # check if current user is a member of the group
    
    if not member or member.role != 'admin': # only admins can deny join request
        abort(404)
    
    join_request = GroupJoinRequest.query.get_or_404(request_id) # get any join requests by ID or return 404 if not found
    if join_request.group_id != group_id: # ensure the join request belongs to the correct group
        abort(404)
    
    join_request.status = 'denied' # set join request status to denied
    join_request.responded_at = utc_now()
    join_request.responded_by_id = current_user.id
    db.session.commit()
    
    flash(f'{join_request.user.username}\'s join request has been denied.', 'info')
    return redirect(url_for('group_join_requests', group_id=group_id))

# Creating a route for leaving a group
@app.route("/groups/<int:group_id>/leave", methods=['POST'])
@login_required
def leave_group(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member: # cannot leave a group not a member of 
        flash('You are not a member of this group.', 'danger')
        return redirect(url_for('groups'))
    
    if member.role == 'admin' and len(group.admin_members) == 1: # cannot leave if user is the only admin
        flash('Cannot leave group as the only admin. Transfer admin role first.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    member.is_active = False # set member as inactive to leave the group
    db.session.commit() # save changes in the database
    
    flash('Successfully left the group.', 'success')
    return redirect(url_for('groups'))

# Creating a route for viewing group details
@app.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by( 
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or not member.is_active: # if not a member or not active, deny access
        abort(403)
    
    # retrieve recent proposed goals
    recent_goals = GroupGoal.query.filter_by(group_id=group_id, status='proposed').order_by(GroupGoal.created_at.desc()).limit(5).all()
    # retrieve recent transactions
    transactions = GroupTransaction.query.filter_by(group_id=group_id).order_by(GroupTransaction.occurred_at.desc()).limit(5).all()
    
    pending_goals = []
    pending_transactions = []
    # if user is admin, retrieve pending goals and transactions for approval
    if member.role == 'admin':
        pending_goals = GroupGoal.query.filter_by(
            group_id=group_id, 
            status='proposed'
        ).all()
        pending_transactions = GroupTransaction.query.filter_by(
            group_id=group_id, 
            status='pending'
        ).all()
    
    # manually getting movements 
    movements = group_transactions_as_movements(group.id, approved_only=True)
    # calculating rate 
    rate = rate_per_day(movements) or 0
    # getting all active goals
    goals = GroupGoal.query.filter_by(group_id=group_id, status='proposed').order_by(GroupGoal.created_at.desc()).all()
    # summing all target amounts of active goals
    total_remaining = sum(max(0.0, float(g.target_amount) - float(group.balance or 0.0)) for g in goals)
    # calculating eta to complete all goals
    eta = estimate_eta(total_remaining, rate)
    
    # check if have enough data to generate graphs
    group_savings_graph = movements is not None and len(movements) > 0
    group_daily_graph = movements is not None and len(movements) > 0

    return render_template("group_detail.html", title=group.name, 
                         group=group, member=member, recent_goals=recent_goals, 
                         transactions=transactions, pending_goals=pending_goals,
                         pending_transactions=pending_transactions, rate=rate, eta=eta, group_savings_graph=group_savings_graph, group_daily_graph=group_daily_graph)
    
# Creating a route for viewing group members    
@app.route("/groups/<int:group_id>/members")
@login_required
def group_members(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    current_user_member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not current_user_member or not current_user_member.is_active: # if not a member or not active, deny access
        abort(403)
    
    return render_template("group_members.html", title=f"{group.name} Members", 
                         group=group, current_user_member=current_user_member)
    
# Creating a route for promoting a member to admin
@app.route("/groups/<int:group_id>/members/<int:member_id>/promote", methods=['POST'])
@login_required
def promote_member(group_id, member_id):
    admin_member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # obtaining current user's record in the group
    
    if not admin_member or admin_member.role != 'admin': # only admins can promote members
        abort(403)
    
    member_to_promote = GroupMember.query.get_or_404(member_id) # get the member to be promoted by ID
    if member_to_promote.group_id != group_id:
        abort(404)
    
    member_to_promote.role = 'admin' # set the user's role to admin
    db.session.commit() # save changes in the database
    
    # get promoted member object
    promoted_member = User.query.get_or_404(member_to_promote.user_id)
    
    flash(f'{promoted_member.username} promoted to admin successfully!', 'success')
    return redirect(url_for('group_members', group_id=group_id))

# Creating a route for demoting an admin to regular member
@app.route("/groups/<int:group_id>/members/<int:member_id>/demote", methods=['POST'])
@login_required
def demote_member(group_id, member_id):
    admin_member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # obtaining current user's record in the group
    
    if not admin_member or admin_member.role != 'admin': # only admins can demote members
        abort(403)
    
    member_to_demote = GroupMember.query.get_or_404(member_id) # get the member to be demoted by ID
    if member_to_demote.group_id != group_id:
        abort(404)
    
    # checks if the member to demote is the current user
    if member_to_demote.user_id == current_user.id: 
        flash('You cannot demote yourself.', 'danger')
        return redirect(url_for('group_members', group_id=group_id))
    
    member_to_demote.role = 'member' # set the user's role to member
    db.session.commit() # save changes in the database
    
    # get demoted user object
    demoted_member = User.query.get_or_404(member_to_demote.user_id)
    
    flash(f'{demoted_member.username} demoted to regular member.', 'success')
    return redirect(url_for('group_members', group_id=group_id))

# Creating a route for removing a member from the group
@app.route("/groups/<int:group_id>/members/<int:member_id>/remove", methods=['POST'])
@login_required
def remove_member(group_id, member_id):
    admin_member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # obtaining current user's record in the group
    
    if not admin_member or admin_member.role != 'admin': # only admins can remove members
        abort(403)
    
    member_to_remove = GroupMember.query.get_or_404(member_id) # get the member to be removed by ID
    if member_to_remove.group_id != group_id:
        abort(404)
    
    # checks if the member to remove is the current user
    if member_to_remove.user_id == current_user.id:
        flash('You cannot remove yourself. Transfer admin role first.', 'danger')
        return redirect(url_for('group_members', group_id=group_id))
    
    member_to_remove.is_active = False # set the member as inactive to remove from group
    db.session.commit() # save changes in the database
    
    # get removed user
    removed_member = User.query.get_or_404(member_to_remove.user_id)
    
    flash(f'{removed_member.username}  removed from group.', 'success')
    return redirect(url_for('group_members', group_id=group_id))

# Creating a route for proposing a new group goal
@app.route("/groups/<int:group_id>/goals/new", methods=['GET', 'POST'])
@login_required
def new_group_goal(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or not member.is_active: # if not a member or not active, deny access
        abort(403)
    
    form = GroupGoalForm() # create an instance of the group goal form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        goal = GroupGoal(
            group_id=group_id,
            title=form.title.data,
            description=form.description.data,
            target_amount=form.target_amount.data,
            deadline=form.deadline.data,
            proposer_id=current_user.id
        ) # create a new GroupGoal record to be added into the database
        db.session.add(goal) # add the group goal record to the database session
        db.session.commit() # commit the session to save group goal
        
        flash('Goal proposed successfully! Waiting for admin approval.', 'success')
        return redirect(url_for('view_group_goals', group_id=group_id))
    
    return render_template("new_group_goal.html", title="Propose Group Goal", 
                         form=form, group=group)

# Creating a route for updating a group goal
@app.route("/groups/<int:group_id>/goals/<int:goal_id>/update", methods=['GET', 'POST'])
@login_required
def update_group_goal(group_id, goal_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or not member.is_active: # if not a member or not active, deny access
        abort(403)
    
    goal = GroupGoal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
    if goal.group_id != group_id:
        abort(404)
    
    if goal.proposer_id != current_user.id: # only the proposer can update the goal
        flash('You do not have permission to update this goal.', 'danger')
        return redirect(url_for('group_goal', group_id=group_id, goal_id=goal_id))
    
    form = GroupGoalForm() # create an instance of the group goal form
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        goal.title = form.title.data
        goal.description = form.description.data
        goal.target_amount = form.target_amount.data
        goal.deadline = form.deadline.data
        db.session.commit() # save changes in the database
        
        flash('Group goal has been updated!', 'success')
        return redirect(url_for('group_goal', group_id=group_id, goal_id=goal_id))
    
    elif request.method == 'GET': # prefill form with existing goal data so that users dont have to reenter unchanged values
        form.title.data = goal.title
        form.description.data = goal.description
        form.target_amount.data = goal.target_amount
        form.deadline.data = goal.deadline
    
    return render_template("new_group_goal.html", title="Update Group Goal", 
                         form=form, group=group, legend='Update Group Goal')

# Creating a route for viewing a specific group goal
@app.route("/groups/<int:group_id>/goals/<int:goal_id>")
@login_required
def group_goal(group_id, goal_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first() # get member information of current user in the group

    if not member or not member.is_active: # if not a member or not active, deny access
        abort(403)

    goal = GroupGoal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
    if goal.group_id != group_id:
        abort(404)
        
    analytics = analyse_group(group, [goal], group.balance)

    return render_template('group_goal.html', title=goal.title, group=group, goal=goal, analytics=analytics, member=member)

@app.route("/groups/<int:group_id>/goals", methods=['GET', 'POST'])
@login_required
def view_group_goals(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or not member.is_active: # if not a member or not active, deny access
        abort(403)

    status_filter = request.args.get('status', 'all') # filter to get goal status, default is all
    page = request.args.get('page', 1, type=int) # pagination page number, default is 1
    per_page = 8
    
    # Query all goals for the group
    query = GroupGoal.query.filter_by(group_id=group_id)
    
    # Apply status filter
    if status_filter in ['proposed', 'approved', 'denied']:
        query = query.filter_by(status=status_filter)
        active_tab = status_filter
    else:
        active_tab = 'all'
    
    goals = query.order_by(GroupGoal.created_at.desc()).paginate(page=page, per_page=per_page)

    return render_template("group_goals.html", title=f"{group.name} Goals",
                           group=group, goals=goals, active_tab=active_tab, group_id=group_id, member=member, analyse_group=analyse_group) 

@app.route("/groups/<int:group_id>/goals/<int:goal_id>/approve", methods=['POST'])
@login_required
def approve_group_goal(group_id, goal_id):
    try:
        group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
        member = GroupMember.query.filter_by(
            group_id=group_id, 
            user_id=current_user.id
        ).first() # get member information of current user in the group
        
        if not member or member.role != 'admin': # only admins can approve goals
            flash('You do not have permission to approve goals.', 'danger')
            return redirect(url_for('group_detail', group_id=group_id))
        
        goal = GroupGoal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
        if goal.group_id != group_id: # ensure the goal belongs to the correct group
            flash('Goal not found in this group.', 'danger')
            return redirect(url_for('group_detail', group_id=group_id))
        
        if goal.status != 'proposed': # only proposed goals can be approved
            flash(f'This goal is already {goal.status} and cannot be approved.', 'warning')
            return redirect(url_for('group_detail', group_id=group_id))
        
        if group.balance < goal.target_amount: # check if group has sufficient funds to complete the goal
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
        ) # create a new GroupTransaction for goal completion so that all changes in group balance are tracked easily
        db.session.add(transaction)
        
        goal.status = 'approved' # set goal status to approved
        goal.approved_by_id = current_user.id # set the approver to current user
        goal.approved_at = utc_now() # set the approval time to current time
        
        group.balance -= goal.target_amount # deduct the goal amount from group balance
        
        db.session.commit() # save all changes in the database
        flash(f'Goal "{goal.title}" approved successfully! ${goal.target_amount:.2f} deducted from group savings.', 'success')
        
    except Exception as e:
        # preserve database integrity in case of error
        db.session.rollback()
        flash(f'Error approving goal: {str(e)}', 'danger')
        print(f"Error in goal approval: {e}")
    
    return redirect(url_for('group_detail', group_id=group_id))

@app.route("/groups/<int:group_id>/goals/<int:goal_id>/deny", methods=['POST'])
@login_required
def deny_group_goal(group_id, goal_id):
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # get member information of current user in the group
    
    if not member or member.role != 'admin': # only admins can deny goals
        abort(403)
    
    goal = GroupGoal.query.get_or_404(goal_id) # retrieve goal by ID or return 404 if not found
    if goal.group_id != group_id:
        abort(404)
    
    goal.status = 'denied' # set goal status to denied
    goal.approved_by_id = current_user.id # set the approver to current user
    goal.approved_at = utc_now() # set the (denying) time to current time
    db.session.commit() # save changes in the database
    
    flash('Goal denied.', 'success')
    return redirect(url_for('view_group_goals', group_id=group_id))

@app.route("/groups/<int:group_id>/transactions/new", methods=['GET', 'POST'])
@login_required
def new_group_transaction(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or not member.is_active: # if not a member or not active, deny access
        abort(403)
    
    form = GroupTransactionForm() # create an instance of the group transaction form 
    if form.validate_on_submit(): # only proceed if form is valid upon submission
        is_admin = member.role == 'admin' # check if current user is an admin of the group
        
        transaction = GroupTransaction(
            group_id=group_id,
            user_id=current_user.id,
            amount=form.amount.data,
            description=form.description.data,
            status='approved' if is_admin else 'pending' 
        ) # create a new GroupTransaction record to be added into the database
        
        if is_admin: # if user is admin, auto approve and update group balance
            transaction.approved_by_id = current_user.id
            transaction.approved_at = utc_now()
            group.balance += form.amount.data
        
        db.session.add(transaction) # add the group transaction record to the database session
        db.session.commit() # commit the session to save group transaction
        
        if is_admin: # different flash message depending on the user role
            flash('Transaction added successfully!', 'success')
        else:
            flash('Transaction request submitted! Waiting for admin approval.', 'success')
        
        return redirect(url_for('view_group_transactions', group_id=group_id))
    
    return render_template("new_group_transaction.html", title="New Group Transaction", 
                         form=form, group=group, member=member)  
    
@app.route("/groups/<int:group_id>/transactions", methods=['GET'])
@login_required
def view_group_transactions(group_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    
    if not member or not member.is_active: # if not a member or not active, deny access
        abort(403)

    status_filter = request.args.get('status', 'all') # filter to get transaction status
    page = request.args.get('page', 1, type=int) # pagination page number
    per_page = 8

    # Query all transactions for the group
    query = GroupTransaction.query.filter_by(group_id=group_id) 
    
    # Apply status filter
    if status_filter in ['pending', 'approved', 'denied']:
        query = query.filter_by(status=status_filter)
        active_tab = status_filter 
    else:
        active_tab = 'all'

    transactions = query.order_by(GroupTransaction.occurred_at.desc()).paginate(page=page, per_page=per_page)

    return render_template('group_transactions.html', title=f"{group.name} Transactions", group=group, transactions=transactions, active_tab=active_tab, group_id=group_id, member=member)

@app.route("/groups/<int:group_id>/transactions/<int:transaction_id>")
@login_required
def group_transaction(group_id, transaction_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first() # check if current user is a member of the group
    if not member or not member.is_active:
        abort(403)

    transaction = GroupTransaction.query.get_or_404(transaction_id)
    # check if transaction belongs to the correct group
    if transaction.group_id != group_id:
        abort(404)

    return render_template('group_transaction.html', title=f"Transaction {transaction.id}", group=group, transaction=transaction, member=member)

# Creating a route for approving a group transaction
@app.route("/groups/<int:group_id>/transactions/<int:transaction_id>/approve", methods=['POST'])
@login_required
def approve_group_transaction(group_id, transaction_id):
    group = Group.query.get_or_404(group_id) # retrieve group by ID or return 404 if not found
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # get member information of current user in the group
    
    if not member or member.role != 'admin': # only admins can approve transactions
        abort(403)
    
    transaction = GroupTransaction.query.get_or_404(transaction_id) # retrieve transaction by ID or return 404 if not found
    if transaction.group_id != group_id:
        abort(404)
    
    try:
        group.balance += transaction.amount # set group balance based on transaction amount
        
        transaction.status = 'approved' # set transaction status to approved
        transaction.approved_by_id = current_user.id # set the approver to current user
        transaction.approved_at = utc_now() # set the approval time to current time
        
        db.session.commit() # save all changes in the database
        flash('Transaction approved successfully!', 'success')
        
    except Exception as e:
        # preserve database integrity in case of error
        db.session.rollback()
        flash(f'Error approving transaction: {str(e)}', 'danger')
        print(f"Error in transaction approval: {e}")
    
    return redirect(url_for('group_detail', group_id=group_id))

# Creating a route for denying a group transaction
@app.route("/groups/<int:group_id>/transactions/<int:transaction_id>/deny", methods=['POST'])
@login_required
def deny_group_transaction(group_id, transaction_id):
    member = GroupMember.query.filter_by(
        group_id=group_id, 
        user_id=current_user.id
    ).first() # get member information of current user in the group
    
    if not member or member.role != 'admin': # only admins can deny transactions
        abort(403)
    
    transaction = GroupTransaction.query.get_or_404(transaction_id) # retrieve transaction by ID or return 404 if not found
    if transaction.group_id != group_id:
        abort(404)
    
    transaction.status = 'denied' # set transaction status to denied 
    transaction.approved_by_id = current_user.id # set the approver to current user
    transaction.approved_at = utc_now() # set the denying time to current time
    db.session.commit() # save changes in the database
    
    flash('Transaction denied.', 'success')
    return redirect(url_for('view_group_transactions', group_id=group_id))

# Graph routes 
# User graph routes

# creating a route to generate savings graph
@app.route('/user/graphs/savings')
@login_required
def user_savings_graph():
    # get user transactions as movements
    movements = user_transactions_as_movements(current_user)
    # convert into pandas dataframe
    daily_series = _to_dataframe(movements)
    
    # get graph data 
    png_data = plot_cumulative_savings(daily_series, title='Your Cumulative Savings')
    # only run if there is data 
    if png_data:
        # output the graph as png
        return send_file(io.BytesIO(png_data), mimetype='image/png', as_attachment=False, download_name='user_savings.png')
    # if no data, return 404
    return abort(404)

# creating a route to generate daily change graph
@app.route('/user/graphs/daily')
@login_required
def user_daily_graph():
    # get user transactions as movements
    movements = user_transactions_as_movements(current_user)
    # convert into pandas dataframe
    daily_series = _to_dataframe(movements)
    
    # get graph data
    png_data = plot_daily_change(daily_series, title='Your Daily Changes')
    # only run if there is data
    if png_data:
        # output the graph as png
        return send_file(io.BytesIO(png_data), mimetype='image/png', as_attachment=False, download_name='user_daily.png')
    # if no data, return 404
    return abort(404)

# Group graph routes

# creating a route to generate group savings graph
@app.route('/groups/<int:group_id>/graphs/savings')
@login_required
def group_savings_graph(group_id):
    # get group information
    group = Group.query.get_or_404(group_id)
    # find member information
    member = GroupMember.query.filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first()
    
    # checks if user is a member 
    if not member or not member.is_active:
        abort(403)
    
    # get group transactions as movements
    movements = group_transactions_as_movements(group_id, approved_only=True)
    # convert into pandas dataframe
    daily_series = _to_dataframe(movements)
    
    # get graph data
    png_data = plot_cumulative_savings(daily_series, title=f'{group.name} Cumulative Savings')
    # only run if there is data
    if png_data:
        # output the graph as png
        return send_file(io.BytesIO(png_data), mimetype='image/png', as_attachment=False, download_name=f'group_{group_id}_savings.png')
    # if no data, return 404
    return abort(404)

# creating a route to generate group daily change graph
@app.route('/groups/<int:group_id>/graphs/daily')
@login_required
def group_daily_graph(group_id):
    # get group information
    group = Group.query.get_or_404(group_id)
    # find member information
    member = GroupMember.query.filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first()
    
    # checks if user is a member
    if not member or not member.is_active:
        abort(403)
    
    # get group transactions as movements
    movements = group_transactions_as_movements(group_id, approved_only=True)
    # convert into pandas dataframe
    daily_series = _to_dataframe(movements)
    
    # get graph data
    png_data = plot_daily_change(daily_series, title=f'{group.name} Daily Changes')
    # only run if there is data
    if png_data:
        # output the graph as png
        return send_file(io.BytesIO(png_data), mimetype='image/png', as_attachment=False, download_name=f'group_{group_id}_daily.png')
    # if no data, return 404
    return abort(404)
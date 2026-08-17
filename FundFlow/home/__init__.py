from flask import Flask # importing the flask class
import sys # importing sys module
from pathlib import Path # importing Path from pathlib module
from flask_login import LoginManager # importing LoginManager from the flask login module
from flask_sqlalchemy import SQLAlchemy # importing SQLAlchemy from the flask sql alchemy module
from flask_bcrypt import Bcrypt # importing Bcrypt for password hashing
from dotenv import load_dotenv # importing load_dotenv to manage environment variables
from flask_migrate import Migrate # importing Migrate for database migrations
load_dotenv()

# Adding the project root directory to sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    # sys.path.append was incorrect when used with two args; insert project root
    sys.path.insert(0, project_root)
    
# Creating a flask application instance
app = Flask(__name__)

# Configuring the secret keys for the application
app.config['SECRET_KEY'] = '5773526bb0b13ce0c676dfde280ba345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

# Creating a database instance
db = SQLAlchemy(app)

# Creating a Bcrypt instance for password hashing
bcrypt = Bcrypt(app)

# Creating a login manager instance
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'danger'


@login_manager.user_loader
def load_user(user_id):
    from home.db_models import User
    try: 
        return User.query.get(int(user_id))
    except Exception:
        return None

# Context processor to make user groups available in all templates
@app.context_processor
def inject_user_groups():
    from home.db_models import Group, GroupMember
    from flask_login import current_user
    from flask import request
    import re
    
    if current_user.is_authenticated:
        # Get all groups the user is a member of
        user_groups = Group.query.join(GroupMember).filter(
            GroupMember.user_id == current_user.id,
            GroupMember.is_active == True
        ).all()
        # Determine whether to show the group sidebar, any path that starts with /groups/ and is not exactly /groups
        path = request.path or ''
        show_sidebar = False
        current_group_id = None
        if path.startswith('/groups/'):
            # exclude the top level groups listing which is exactly '/groups'
            if not re.fullmatch(r"/groups/?", path):
                show_sidebar = True
                # parse the group id from the path segments
                parts = path.strip('/').split('/')
                # checking for /groups/<group_id>/...
                if len(parts) >= 2 and parts[1].isdigit():
                    current_group_id = int(parts[1])

        return {'user_groups': user_groups, 'show_group_sidebar': show_sidebar, 'current_group_id': current_group_id}
    return {'user_groups': []}

# Registering routes with the flask app
from home import routes

# Creating a Flask Migrate instance
migrate = Migrate(app, db)



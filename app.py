import os
import logging
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the base class
db = SQLAlchemy(model_class=Base)

# Create Flask app instance
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-development")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///facebook_bot.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the extension
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Make sure all models are imported so their tables are created
from models import User, FacebookToken, NotificationRule, FilteredNotification

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Import fb_api module after initializing db to avoid circular imports
from fb_api import get_fb_auth_url, get_access_token, get_user_info, get_notifications
from notification_filter import filter_notifications
from scheduler import start_scheduler, stop_scheduler

# Create tables if they don't exist
with app.app_context():
    db.create_all()
    logger.debug("Database tables created")

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('login'))
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('login.html', register=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/connect-facebook')
@login_required
def connect_facebook():
    # Generate Facebook authorization URL
    auth_url = get_fb_auth_url()
    return redirect(auth_url)

@app.route('/facebook-callback')
@login_required
def facebook_callback():
    code = request.args.get('code')
    
    if not code:
        flash('Facebook authorization failed.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Exchange code for access token
    access_token_data = get_access_token(code)
    
    if not access_token_data or 'access_token' not in access_token_data:
        flash('Failed to get Facebook access token.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get user info to verify Facebook connection
    fb_user_info = get_user_info(access_token_data['access_token'])
    
    if not fb_user_info or 'id' not in fb_user_info:
        flash('Failed to get Facebook user info.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Save or update the token in database
    existing_token = FacebookToken.query.filter_by(user_id=current_user.id).first()
    
    if existing_token:
        existing_token.access_token = access_token_data['access_token']
        existing_token.expires_at = datetime.now().timestamp() + access_token_data.get('expires_in', 3600)
        existing_token.fb_user_id = fb_user_info['id']
    else:
        new_token = FacebookToken(
            user_id=current_user.id,
            access_token=access_token_data['access_token'],
            expires_at=datetime.now().timestamp() + access_token_data.get('expires_in', 3600),
            fb_user_id=fb_user_info['id']
        )
        db.session.add(new_token)
    
    db.session.commit()
    
    flash('Facebook connected successfully!', 'success')
    
    # Start the notification scheduler
    start_scheduler(app)
    
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Check if user has connected to Facebook
    fb_token = FacebookToken.query.filter_by(user_id=current_user.id).first()
    
    if not fb_token:
        return render_template('dashboard.html', connected=False)
    
    # Get filtered notifications
    important_notifications = FilteredNotification.query.filter_by(
        user_id=current_user.id, 
        importance='important'
    ).order_by(FilteredNotification.created_time.desc()).limit(10).all()
    
    other_notifications = FilteredNotification.query.filter_by(
        user_id=current_user.id, 
        importance='normal'
    ).order_by(FilteredNotification.created_time.desc()).limit(10).all()
    
    return render_template(
        'dashboard.html', 
        connected=True,
        important_notifications=important_notifications,
        other_notifications=other_notifications
    )

@app.route('/rules', methods=['GET', 'POST'])
@login_required
def rules():
    if request.method == 'POST':
        rule_type = request.form.get('rule_type')
        content_filter = request.form.get('content_filter', '')
        importance = request.form.get('importance')
        
        # Create new rule
        new_rule = NotificationRule(
            user_id=current_user.id,
            notification_type=rule_type,
            content_filter=content_filter,
            importance=importance
        )
        
        db.session.add(new_rule)
        db.session.commit()
        
        flash('Rule added successfully!', 'success')
        
    # Get all user's rules
    user_rules = NotificationRule.query.filter_by(user_id=current_user.id).all()
    
    return render_template('rules.html', rules=user_rules)

@app.route('/delete-rule/<int:rule_id>', methods=['POST'])
@login_required
def delete_rule(rule_id):
    rule = NotificationRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    
    if not rule:
        flash('Rule not found.', 'danger')
        return redirect(url_for('rules'))
    
    db.session.delete(rule)
    db.session.commit()
    
    flash('Rule deleted successfully.', 'success')
    return redirect(url_for('rules'))

@app.route('/reports')
@login_required
def reports():
    # Get notification statistics
    important_count = FilteredNotification.query.filter_by(
        user_id=current_user.id, 
        importance='important'
    ).count()
    
    normal_count = FilteredNotification.query.filter_by(
        user_id=current_user.id, 
        importance='normal'
    ).count()
    
    # Get notification type breakdown
    notification_types = db.session.query(
        FilteredNotification.notification_type, 
        db.func.count(FilteredNotification.id)
    ).filter_by(user_id=current_user.id).group_by(
        FilteredNotification.notification_type
    ).all()
    
    type_data = {ntype: count for ntype, count in notification_types}
    
    return render_template(
        'reports.html', 
        important_count=important_count,
        normal_count=normal_count,
        type_data=type_data
    )

@app.route('/refresh-notifications', methods=['POST'])
@login_required
def refresh_notifications():
    fb_token = FacebookToken.query.filter_by(user_id=current_user.id).first()
    
    if not fb_token:
        flash('Facebook not connected.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Fetch notifications from Facebook
    raw_notifications = get_notifications(fb_token.access_token)
    
    if not raw_notifications:
        flash('Failed to fetch notifications from Facebook.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get user's rules
    user_rules = NotificationRule.query.filter_by(user_id=current_user.id).all()
    
    # Apply rules to filter notifications
    filtered_notifications = filter_notifications(raw_notifications, user_rules, current_user.id)
    
    # Save filtered notifications to database
    for notification in filtered_notifications:
        existing = FilteredNotification.query.filter_by(
            user_id=current_user.id,
            notification_id=notification['id']
        ).first()
        
        if not existing:
            new_notification = FilteredNotification(
                user_id=current_user.id,
                notification_id=notification['id'],
                notification_type=notification['type'],
                title=notification.get('title', ''),
                message=notification.get('message', ''),
                link=notification.get('link', ''),
                created_time=notification.get('created_time', datetime.now()),
                importance=notification['importance']
            )
            db.session.add(new_notification)
    
    db.session.commit()
    
    flash('Notifications refreshed successfully!', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

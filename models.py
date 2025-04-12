from datetime import datetime
from app import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    fb_token = db.relationship('FacebookToken', backref='user', lazy=True, uselist=False)
    rules = db.relationship('NotificationRule', backref='user', lazy=True)
    notifications = db.relationship('FilteredNotification', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class FacebookToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    access_token = db.Column(db.String(512), nullable=False)
    expires_at = db.Column(db.Float, nullable=False)  # Unix timestamp
    fb_user_id = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_valid(self):
        """Check if the token is still valid"""
        return datetime.now().timestamp() < self.expires_at
    
    def __repr__(self):
        return f'<FacebookToken user_id={self.user_id}>'

class NotificationRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notification_type = db.Column(db.String(64), nullable=False)  # e.g., 'message', 'group_mention', 'like'
    content_filter = db.Column(db.String(256), default='')  # Optional keyword filter
    importance = db.Column(db.String(20), nullable=False, default='normal')  # 'important' or 'normal'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<NotificationRule {self.notification_type}>'

class FilteredNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notification_id = db.Column(db.String(256), nullable=False)  # Facebook notification ID
    notification_type = db.Column(db.String(64), nullable=False)  # Detected type
    title = db.Column(db.String(256))  # Title/summary of the notification
    message = db.Column(db.Text)  # Full notification text
    link = db.Column(db.String(512))  # Link to the Facebook content
    created_time = db.Column(db.DateTime, default=datetime.utcnow)  # When the notification was created on Facebook
    processed_time = db.Column(db.DateTime, default=datetime.utcnow)  # When our system processed it
    importance = db.Column(db.String(20), nullable=False, default='normal')  # 'important' or 'normal'
    is_read = db.Column(db.Boolean, default=False)  # Whether the user has marked it as read
    
    def __repr__(self):
        return f'<FilteredNotification {self.notification_type}>'

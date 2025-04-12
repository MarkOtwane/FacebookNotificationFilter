import threading
import time
import logging
import atexit
from datetime import datetime, timedelta
from flask import current_app

logger = logging.getLogger(__name__)

# Global variable to hold the scheduler thread
scheduler_thread = None
stop_scheduler = False

def check_notifications():
    """
    Periodic task to check for new notifications
    """
    try:
        # Use application context for database operations
        with current_app.app_context():
            from app import db
            from models import User, FacebookToken
            from fb_api import get_notifications
            from notification_filter import filter_notifications
            from models import NotificationRule, FilteredNotification
            
            # Get all users with valid Facebook tokens
            users_with_tokens = db.session.query(User, FacebookToken).join(
                FacebookToken, User.id == FacebookToken.user_id
            ).all()
            
            for user, token in users_with_tokens:
                # Skip if token is expired
                if not token.is_valid():
                    logger.info(f"Skipping user {user.id} - token expired")
                    continue
                
                try:
                    # Fetch notifications from Facebook
                    notifications = get_notifications(token.access_token)
                    
                    if not notifications:
                        logger.warning(f"No notifications fetched for user {user.id}")
                        continue
                    
                    # Get user's notification rules
                    rules = NotificationRule.query.filter_by(user_id=user.id).all()
                    
                    # Apply rules to filter notifications
                    filtered = filter_notifications(notifications, rules, user.id)
                    
                    # Save new notifications to database
                    new_count = 0
                    for notification in filtered:
                        # Check if notification already exists
                        existing = FilteredNotification.query.filter_by(
                            user_id=user.id,
                            notification_id=notification['id']
                        ).first()
                        
                        if not existing:
                            # Create new notification record
                            new_notification = FilteredNotification(
                                user_id=user.id,
                                notification_id=notification['id'],
                                notification_type=notification['type'],
                                title=notification.get('title', ''),
                                message=notification.get('message', ''),
                                link=notification.get('link', ''),
                                created_time=notification.get('created_time', datetime.now()),
                                importance=notification['importance']
                            )
                            db.session.add(new_notification)
                            new_count += 1
                    
                    # Commit changes
                    if new_count > 0:
                        db.session.commit()
                        logger.info(f"Added {new_count} new notifications for user {user.id}")
                
                except Exception as e:
                    logger.error(f"Error processing notifications for user {user.id}: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in check_notifications task: {str(e)}")

def scheduler_loop():
    """
    Main scheduler loop that runs in a separate thread
    """
    logger.info("Notification scheduler started")
    
    while not stop_scheduler:
        try:
            check_notifications()
        except Exception as e:
            logger.error(f"Error in scheduler loop: {str(e)}")
        
        # Sleep for 15 minutes before checking again
        # We'll check every 5 seconds if we need to stop to allow for clean shutdown
        remaining_seconds = 15 * 60  # 15 minutes in seconds
        while remaining_seconds > 0 and not stop_scheduler:
            time.sleep(min(5, remaining_seconds))
            remaining_seconds -= 5
    
    logger.info("Notification scheduler stopped")

def start_scheduler(app):
    """
    Start the notification scheduler in a separate thread
    
    Args:
        app: Flask application instance
    """
    global scheduler_thread, stop_scheduler
    
    # Don't start if already running
    if scheduler_thread and scheduler_thread.is_alive():
        return
    
    # Reset stop flag
    stop_scheduler = False
    
    # Create and start the scheduler thread
    scheduler_thread = threading.Thread(target=scheduler_loop)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Register cleanup function
    atexit.register(stop_scheduler_fn)

def stop_scheduler_fn():
    """
    Stop the scheduler thread
    """
    global stop_scheduler
    
    logger.info("Stopping notification scheduler...")
    stop_scheduler = True
    
    # Wait for scheduler thread to finish (max 10 seconds)
    if scheduler_thread:
        scheduler_thread.join(timeout=10)

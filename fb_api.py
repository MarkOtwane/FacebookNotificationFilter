import os
import logging
import requests
from urllib.parse import urlencode
from datetime import datetime
from flask import url_for, request

logger = logging.getLogger(__name__)

# Facebook API configuration
FB_APP_ID = os.environ.get("FB_APP_ID")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET")
FB_API_VERSION = 'v16.0'  # Update to the latest stable version
FB_GRAPH_URL = f'https://graph.facebook.com/{FB_API_VERSION}'

# Required permissions for the app
FB_PERMISSIONS = [
    'user_notifications',  # Access to user notifications
    'email',              # Basic profile information
]

def get_fb_auth_url():
    """
    Generate the Facebook OAuth URL for authentication
    """
    if not FB_APP_ID:
        logger.error("Facebook App ID is not set in environment variables")
        return None
    
    # Build redirect URI (must match what's configured in Facebook Developer Console)
    redirect_uri = url_for('facebook_callback', _external=True)
    
    # Generate state parameter for CSRF protection
    state = os.urandom(16).hex()
    
    # Build the authorization URL
    params = {
        'client_id': FB_APP_ID,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': ','.join(FB_PERMISSIONS),
        'response_type': 'code'
    }
    
    auth_url = f'https://www.facebook.com/{FB_API_VERSION}/dialog/oauth?' + urlencode(params)
    return auth_url

def get_access_token(code):
    """
    Exchange authorization code for an access token
    """
    if not FB_APP_ID or not FB_APP_SECRET:
        logger.error("Facebook App ID or Secret is not set in environment variables")
        return None
    
    # Build redirect URI (must match what was used in the authorization request)
    redirect_uri = url_for('facebook_callback', _external=True)
    
    # Make the API request to exchange code for token
    params = {
        'client_id': FB_APP_ID,
        'client_secret': FB_APP_SECRET,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    
    response = requests.get(f'{FB_GRAPH_URL}/oauth/access_token', params=params)
    
    if response.status_code != 200:
        logger.error(f"Failed to get access token: {response.text}")
        return None
    
    return response.json()

def get_user_info(access_token):
    """
    Get basic user information from Facebook
    """
    params = {
        'fields': 'id,name,email',
        'access_token': access_token
    }
    
    response = requests.get(f'{FB_GRAPH_URL}/me', params=params)
    
    if response.status_code != 200:
        logger.error(f"Failed to get user info: {response.text}")
        return None
    
    return response.json()

def get_notifications(access_token):
    """
    Fetch notifications from Facebook
    """
    params = {
        'fields': 'application,created_time,from,link,message,object,title,to,unread',
        'access_token': access_token,
        'limit': 50  # Fetch up to 50 notifications at a time
    }
    
    response = requests.get(f'{FB_GRAPH_URL}/me/notifications', params=params)
    
    if response.status_code != 200:
        logger.error(f"Failed to get notifications: {response.text}")
        return None
    
    data = response.json()
    
    if 'data' not in data:
        logger.warning("No notification data returned from Facebook")
        return []
    
    # Process notifications to standardize format
    processed_notifications = []
    for notification in data['data']:
        # Parse notification to extract type and other relevant fields
        n_type = detect_notification_type(notification)
        
        # Convert Facebook timestamp to datetime
        created_time = notification.get('created_time')
        if created_time:
            created_time = datetime.strptime(created_time, '%Y-%m-%dT%H:%M:%S%z')
        
        processed_notifications.append({
            'id': notification.get('id', ''),
            'type': n_type,
            'title': notification.get('title', ''),
            'message': notification.get('message', ''),
            'link': notification.get('link', ''),
            'from': notification.get('from', {}),
            'created_time': created_time,
            'unread': notification.get('unread', True),
            'raw': notification  # Keep raw data for reference
        })
    
    return processed_notifications

def detect_notification_type(notification):
    """
    Detect the type of notification based on its contents
    
    This is a heuristic approach since Facebook's API doesn't explicitly
    categorize notifications by type.
    """
    message = notification.get('message', '').lower()
    title = notification.get('title', '').lower()
    
    # Check for common notification patterns
    if 'messag' in message or 'messag' in title:
        return 'message'
    elif 'mention' in message or 'mentioned you' in message:
        return 'mention'
    elif 'comment' in message:
        return 'comment'
    elif 'tag' in message or 'tagged you' in message:
        return 'tag'
    elif 'like' in message or 'reacted to' in message:
        return 'like'
    elif 'friend request' in message or 'friend request' in title:
        return 'friend_request'
    elif 'group' in message:
        if 'invite' in message:
            return 'group_invite'
        return 'group_activity'
    elif 'event' in message:
        if 'invite' in message:
            return 'event_invite'
        return 'event_update'
    elif 'birthday' in message:
        return 'birthday'
    elif 'anniversary' in message:
        return 'anniversary'
    elif 'memory' in message or 'on this day' in message:
        return 'memory'
    
    # Default type if we can't determine
    return 'other'

import logging
from models import FilteredNotification

logger = logging.getLogger(__name__)

def filter_notifications(notifications, rules, user_id):
    """
    Apply filtering rules to notifications
    
    Args:
        notifications (list): List of notification dictionaries from Facebook
        rules (list): List of NotificationRule objects from the database
        user_id (int): The ID of the current user
        
    Returns:
        list: List of notifications with importance classification added
    """
    if not notifications:
        return []
    
    filtered_notifications = []
    default_importance = 'normal'  # Default importance level
    
    # Create a mapping of rule types to importance for quick lookup
    rule_map = {}
    for rule in rules:
        # Skip invalid rules
        if not rule.notification_type:
            continue
        
        # Create a dict of content filters for each notification type
        if rule.notification_type not in rule_map:
            rule_map[rule.notification_type] = []
        
        rule_map[rule.notification_type].append({
            'content_filter': rule.content_filter.lower() if rule.content_filter else '',
            'importance': rule.importance
        })
    
    # Process each notification through the rules
    for notification in notifications:
        n_type = notification['type']
        importance = default_importance
        
        # Check if we have rules for this notification type
        if n_type in rule_map:
            # Check content filters for this type
            message = notification.get('message', '').lower()
            title = notification.get('title', '').lower()
            
            # Apply matching rules
            for rule_info in rule_map[n_type]:
                content_filter = rule_info['content_filter']
                
                # If there's no content filter, apply the rule
                if not content_filter:
                    importance = rule_info['importance']
                # Otherwise, check if the content filter matches the notification
                elif content_filter in message or content_filter in title:
                    importance = rule_info['importance']
                    # Once we find a match, no need to check more rules
                    break
        
        # Add importance to the notification
        notification['importance'] = importance
        filtered_notifications.append(notification)
    
    return filtered_notifications

def apply_default_rules(user_id):
    """
    Apply default filtering rules for new users
    
    Args:
        user_id (int): The ID of the user to create default rules for
        
    Returns:
        list: List of created NotificationRule objects
    """
    from app import db
    from models import NotificationRule
    
    # Default ruleset for new users
    default_rules = [
        # Important notifications
        {'type': 'message', 'content_filter': '', 'importance': 'important'},
        {'type': 'mention', 'content_filter': '', 'importance': 'important'},
        {'type': 'tag', 'content_filter': '', 'importance': 'important'},
        {'type': 'comment', 'content_filter': '', 'importance': 'important'},
        
        # Normal notifications
        {'type': 'like', 'content_filter': '', 'importance': 'normal'},
        {'type': 'friend_request', 'content_filter': '', 'importance': 'normal'},
        {'type': 'group_invite', 'content_filter': '', 'importance': 'normal'},
        {'type': 'event_invite', 'content_filter': '', 'importance': 'normal'},
        {'type': 'birthday', 'content_filter': '', 'importance': 'normal'},
        {'type': 'memory', 'content_filter': '', 'importance': 'normal'},
    ]
    
    created_rules = []
    
    # Create each default rule
    for rule_info in default_rules:
        new_rule = NotificationRule(
            user_id=user_id,
            notification_type=rule_info['type'],
            content_filter=rule_info['content_filter'],
            importance=rule_info['importance']
        )
        db.session.add(new_rule)
        created_rules.append(new_rule)
    
    # Commit the changes
    db.session.commit()
    
    return created_rules

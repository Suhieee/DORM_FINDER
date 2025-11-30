from .models import Notification
from django.core.cache import cache

def notifications(request):
    """Context processor to add notifications to all templates."""
    if not request.user.is_authenticated:
        return {
            'notifications': [],
            'notification_count': 0,
        }
    
    # Cache notification count for 30 seconds to reduce database queries
    cache_key = f'notification_count_{request.user.id}'
    notification_count = cache.get(cache_key)
    
    if notification_count is None:
        notification_count = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).count()
        cache.set(cache_key, notification_count, 30)  # Cache for 30 seconds
    
    # Only fetch notifications if count > 0 (lazy loading)
    if notification_count > 0:
        notifications_list = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).order_by('-created_at')[:10]  # Limit to 10 most recent
    else:
        notifications_list = []
    
    return {
        'notifications': notifications_list,
        'notification_count': notification_count,
    } 
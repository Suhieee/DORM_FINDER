from .models import Notification

def notifications(request):
    """Context processor to add notifications to all templates."""
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        return {
            'notifications': notifications,
            'notification_count': notifications.count(),
        }
    return {
        'notifications': [],
        'notification_count': 0,
    } 
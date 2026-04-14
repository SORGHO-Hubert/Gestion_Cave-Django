from .models import Notification

def notifications_count(request):
    if request.user.is_authenticated:
        # On compte uniquement les notifications qui ont 'lu=False'
        count = Notification.objects.filter(lu=False).count()
    else:
        count = 0
    return {'notif_count': count}
"""Контекст-процессоры приложения users."""


def notifications(request):
    """Счётчик непрочитанных уведомлений для колокольчика в шапке.

    Уведомления создавались с самого начала, но нигде не отображались
    (problems.md, П-29).
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'unread_notifications_count': 0}

    from users.models import Notification
    return {
        'unread_notifications_count': Notification.objects.filter(
            user=user, is_read=False).count(),
    }

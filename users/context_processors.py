"""Контекст-процессоры приложения users."""


def notifications(request):
    """Непрочитанные сообщения и чаты для счётчиков в шапке."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'unread_messages_count': 0,
        }

    from chat.utils.notifications import unread_summary
    return unread_summary(user)

from ..models import Notification


def create_notification(user, notification_type, title, message, url='', related_message=None):
    """Создать уведомление для пользователя"""

    Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url,
        related_message=related_message
    )

def create_notification(user, notification_type, title, message, url='', related_message=None):
    from users.models import Notification
    from django.db import transaction
    transaction.on_commit(lambda: Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url,
        related_message=related_message
    ))

from django.db import transaction
from django.urls import reverse
from django.utils import timezone


def create_notification(
    user,
    notification_type,
    title,
    message,
    url='',
    related_message=None,
    conversation_key='',
):
    from users.models import Notification

    transaction.on_commit(lambda: Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url,
        related_message=related_message,
        conversation_key=conversation_key,
    ))


def conversation_key_for_message(message, user):
    """Ключ чата с точки зрения конкретного пользователя."""
    if message.group_id is not None:
        return f'group:{message.group_id}'
    if message.channel_id is not None:
        return f'channel:{message.channel_id}'
    if message.sender_id and message.receiver_id:
        peer_id = (
            message.receiver_id
            if message.sender_id == user.id
            else message.sender_id
        )
        return f'direct:{peer_id}'
    return ''


def _message_payload(message):
    """Заголовок/ссылка/ключ уведомления о сообщении."""
    if message.group_id is not None:
        return (
            f'group:{message.group_id}',
            f'Новое сообщение в группе «{message.group.name}»',
            reverse('group_chat', args=[message.group_id]),
        )
    if message.channel_id is not None:
        return (
            f'channel:{message.channel_id}',
            f'Новый пост в канале «{message.channel.name}»',
            reverse('channel_view', args=[message.channel_id]),
        )
    return (
        f'direct:{message.sender_id}',
        'Новое сообщение',
        f'/?user_id={message.sender_id}',
    )


def _notification_text(message):
    preview = message.preview_text or 'вложение'
    return f'{message.sender.username}: {preview}'


def notify_message_recipients(message, recipient_ids):
    """Создаёт/обновляет по одной непрочитанной записи на чат."""
    from users.models import Notification

    recipient_ids = {
        int(recipient_id)
        for recipient_id in recipient_ids
        if recipient_id and int(recipient_id) != message.sender_id
    }
    if not recipient_ids:
        return

    def _run():
        now = timezone.now()
        key, title, url = _message_payload(message)
        payloads = {
            recipient_id: (key, title, url)
            for recipient_id in recipient_ids
        }

        keys = {payload[0] for payload in payloads.values()}
        existing = Notification.objects.filter(
            user_id__in=recipient_ids,
            notification_type='message',
            is_read=False,
            conversation_key__in=keys,
        )
        existing_by_key = {
            (note.user_id, note.conversation_key): note
            for note in existing
        }

        to_create = []
        to_update = []
        text = _notification_text(message)
        for recipient_id, (key, title, url) in payloads.items():
            note = existing_by_key.get((recipient_id, key))
            if note is None:
                to_create.append(Notification(
                    user_id=recipient_id,
                    notification_type='message',
                    title=title,
                    message=text,
                    url=url,
                    related_message=message,
                    conversation_key=key,
                    unread_count=1,
                    created_at=now,
                    updated_at=now,
                ))
                continue

            note.unread_count += 1
            note.title = title
            note.message = text
            note.url = url
            note.related_message = message
            note.updated_at = now
            to_update.append(note)

        if to_create:
            Notification.objects.bulk_create(to_create)
        if to_update:
            Notification.objects.bulk_update(to_update, [
                'unread_count', 'title', 'message', 'url',
                'related_message', 'updated_at',
            ])

    transaction.on_commit(_run)


def mark_conversation_read(user, conversation_key):
    """Убирает непрочитанные уведомления открытого чата."""
    if not conversation_key:
        return 0

    from chat.models import Message
    from users.models import Notification

    updated = Notification.objects.filter(
        user=user,
        conversation_key=conversation_key,
        is_read=False,
    ).update(is_read=True)

    if conversation_key.startswith('direct:'):
        try:
            peer_id = int(conversation_key.split(':', 1)[1])
        except (TypeError, ValueError):
            return updated
        Message.objects.filter(
            sender_id=peer_id,
            receiver=user,
            is_read=False,
            is_deleted=False,
        ).update(is_read=True)

    return updated


def message_unread_counts(user):
    """Счётчики непрочитанных сообщений по ключам чатов."""
    from django.db.models import Sum
    from users.models import Notification

    rows = Notification.objects.filter(
        user=user,
        notification_type='message',
        is_read=False,
    ).values('conversation_key').annotate(
        total=Sum('unread_count'),
    )
    return {
        row['conversation_key']: row['total'] or 0
        for row in rows
        if row['conversation_key']
    }


def unread_summary(user):
    from django.db.models import Sum
    from users.models import Notification

    unread = Notification.objects.filter(user=user, is_read=False)
    message_total = unread.filter(
        notification_type='message',
    ).aggregate(total=Sum('unread_count'))['total'] or 0

    keys = set()
    individual = 0
    for key, _notification_type in unread.values_list(
            'conversation_key', 'notification_type'):
        if key:
            keys.add(key)
        else:
            individual += 1

    return {
        'unread_messages_count': message_total,
        'unread_notifications_count': len(keys) + individual,
    }


def adjust_notifications_after_message_delete(message):
    """Убирает удалённое сообщение из счётчиков непрочитанного."""
    from chat.models import Message
    from users.models import Notification

    if message.group_id is not None:
        notifications = Notification.objects.filter(
            notification_type='message',
            is_read=False,
            conversation_key=f'group:{message.group_id}',
        )
    elif message.channel_id is not None:
        notifications = Notification.objects.filter(
            notification_type='message',
            is_read=False,
            conversation_key=f'channel:{message.channel_id}',
        )
    elif message.receiver_id is not None:
        notifications = Notification.objects.filter(
            notification_type='message',
            is_read=False,
            user_id=message.receiver_id,
            conversation_key=f'direct:{message.sender_id}',
        )
    else:
        return

    to_update = []
    for note in notifications:
        if note.unread_count > 1:
            note.unread_count -= 1
        else:
            note.unread_count = 0
            note.is_read = True

        if note.related_message_id == message.id:
            previous = Message.objects.filter(
                **(
                    {'group_id': message.group_id}
                    if message.group_id is not None
                    else {'channel_id': message.channel_id}
                    if message.channel_id is not None
                    else {
                        'sender_id': message.sender_id,
                        'receiver_id': message.receiver_id,
                    }
                ),
                is_deleted=False,
            ).exclude(pk=message.pk).order_by('-created_at').first()
            if previous is not None:
                note.related_message = previous
                note.message = _notification_text(previous)
                note.updated_at = timezone.now()
            else:
                note.is_read = True
                note.unread_count = 0

        to_update.append(note)

    if to_update:
        Notification.objects.bulk_update(to_update, [
            'unread_count', 'is_read', 'related_message',
            'message', 'updated_at',
        ])

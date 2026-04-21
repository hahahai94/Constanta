from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from chat.models import User, Group, Message, GroupMember
from chat.utils import parse_mentions, create_notification
import json, hashlib, os
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage


@login_required
def send_message(request):
    """API: отправка сообщения (личного или группового)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'failed'}, status=400)

    friend_id = request.POST.get('friend_id')
    group_id = request.POST.get('group_id')
    content = request.POST.get('content', '').strip()
    reply_to_id = request.POST.get('reply_to_id')

    # Инициализация переменных
    parsed_content = content
    mentions_json = '[]'
    mentioned_ids = []

    # Обработка вложений
    attachment = request.FILES.get('attachment')
    attachment_type = 'none'
    attachment_size = 0
    attachment_hash = ''
    attachment_original_name = ''
    upload_path = None

    if attachment:
        if attachment.size > 50 * 1024 * 1024:
            return JsonResponse({'status': 'failed', 'error': 'Файл > 50 МБ'}, status=400)

        timestamp = datetime.now().isoformat()
        file_content = attachment.read()
        hash_input = f"{file_content.hex()}{request.user.id}{timestamp}".encode('utf-8')
        attachment_hash = hashlib.sha256(hash_input).hexdigest()
        attachment.seek(0)

        if attachment.content_type.startswith('image/'):
            attachment_type = 'image'
        elif attachment.content_type.startswith('audio/'):
            attachment_type = 'voice'
        else:
            attachment_type = 'file'

        attachment_size = attachment.size
        attachment_original_name = attachment.name

        subdir = attachment_hash[:2]
        ext = os.path.splitext(attachment.name)[1].lower()
        upload_path = os.path.join('attachments', subdir, f"{attachment_hash}{ext}")

        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'attachments', subdir), exist_ok=True)
        default_storage.save(upload_path, attachment)

    # Парсинг упоминаний
    if content:
        try:
            if group_id:
                group = get_object_or_404(Group, id=group_id)
                parsed_content, mentioned_ids = parse_mentions(content, group=group)
            elif friend_id:
                parsed_content, mentioned_ids = parse_mentions(content, receiver=None)
            mentions_json = json.dumps(mentioned_ids)
        except Exception:
            parsed_content = content

    # Ответ на сообщение
    reply_msg = None
    if reply_to_id:
        reply_msg = Message.objects.filter(id=reply_to_id).first()

    # Создание сообщения
    msg = None
    if friend_id:
        receiver = get_object_or_404(User, id=friend_id)
        msg = Message.objects.create(
            sender=request.user, receiver=receiver, group=None,
            content=parsed_content, attachment=upload_path if upload_path else None,
            attachment_hash=attachment_hash, attachment_original_name=attachment_original_name,
            attachment_type=attachment_type, attachment_size=attachment_size,
            mentions=mentions_json, reply_to=reply_msg
        )
        if receiver != request.user:
            create_notification(
                user=receiver, notification_type='message',
                title=f'Новое сообщение от {request.user.get_display_name()}',
                message=content[:100] if content else '📎 Вложение',
                url=f'/?friend_id={request.user.id}', related_message=msg
            )

    elif group_id:
        group = get_object_or_404(Group, id=group_id)
        if GroupMember.objects.filter(group=group, user=request.user).exists():
            msg = Message.objects.create(
                sender=request.user, receiver=None, group=group,
                content=parsed_content, attachment=upload_path if upload_path else None,
                attachment_hash=attachment_hash, attachment_original_name=attachment_original_name,
                attachment_type=attachment_type, attachment_size=attachment_size,
                mentions=mentions_json, reply_to=reply_msg
            )
            if mentioned_ids:
                for uid in mentioned_ids:
                    if uid != request.user.id:
                        try:
                            u = User.objects.get(id=uid)
                            create_notification(
                                user=u, notification_type='mention',
                                title=f'Вас упомянули в {group.name}',
                                message=f'{request.user.get_display_name()} упомянул вас',
                                url=f'/groups/{group.id}/', related_message=msg
                            )
                        except User.DoesNotExist:
                            pass

    return JsonResponse({'status': 'ok'})


@login_required
def api_heartbeat(request):
    """API: обновление last_seen"""
    if request.method == 'POST' and request.user.is_authenticated:
        from django.utils import timezone
        request.user.last_seen = timezone.now()
        request.user.save(update_fields=['last_seen'])
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'failed'}, status=400)
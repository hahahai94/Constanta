import os
import json
import logging
import re
from urllib.parse import quote
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from chat.models import Group, Message, GroupMember, Channel, ChannelMember
from chat.utils import parse_mentions, create_notification

logger = logging.getLogger(__name__)
User = get_user_model()

IMAGE_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',
    b'\x42\x4d': 'image/bmp',
}


def _detect_image_type(data):
    for magic, mime in IMAGE_MAGIC_BYTES.items():
        if data.startswith(magic):
            return mime
    return None


def _safe_filename(name):
    name = name or 'file'
    name = re.sub(r'[\r\n"]', '', name)
    name = re.sub(r'[^\x20-\x7E\u0080-\uFFFF]', '', name)
    name = name.strip().strip('.')
    return name or 'file'


def _content_disposition_header(filename):
    safe = _safe_filename(filename)
    ascii_part = safe.encode('ascii', errors='replace').decode('ascii')
    if ascii_part == safe:
        return f'attachment; filename="{safe}"'
    return f'attachment; filename="{ascii_part}"; filename*=UTF-8\'\'{quote(safe)}'


@login_required
def send_message(request):
    """API: отправка сообщения с поддержкой ответов"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    friend_id = request.POST.get('friend_id')
    group_id = request.POST.get('group_id')
    content = request.POST.get('content', '').strip()
    attachment = request.FILES.get('attachment')
    reply_to_id = request.POST.get('reply_to_id')

    if not friend_id and not group_id:
        return JsonResponse({'status': 'error', 'message': 'Нет получателя'}, status=400)

    max_chars = settings.MAX_MESSAGE_LENGTH
    if len(content) > max_chars:
        return JsonResponse({'status': 'error', 'message': f'Слишком длинное (макс. {max_chars})'}, status=400)

    if not content and not attachment:
        return JsonResponse({'status': 'error', 'message': 'Пустое сообщение'}, status=400)

    attachment_type = 'none'
    if attachment:
        if attachment.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            return JsonResponse({'status': 'error', 'message': 'Файл слишком большой'}, status=400)
        head = attachment.read(32)
        attachment.seek(0)
        detected = _detect_image_type(head)
        ct = attachment.content_type or ''
        if detected:
            attachment_type = 'image'
        elif ct.startswith('audio/'):
            attachment_type = 'voice'
        elif ct.startswith('image/'):
            attachment_type = 'image'
        else:
            attachment_type = 'file'

    reply_msg = None
    if reply_to_id:
        reply_msg = Message.objects.filter(id=reply_to_id).first()
        if reply_msg:
            if friend_id:
                ids = {request.user.id, int(friend_id)}
                if reply_msg.sender.id not in ids or (reply_msg.receiver_id not in ids and reply_msg.receiver_id is not None):
                    reply_msg = None
            elif group_id and reply_msg.group_id is not None and str(reply_msg.group_id) != group_id:
                reply_msg = None

    try:
        if friend_id:
            receiver = get_object_or_404(User, id=friend_id)
            msg = Message.objects.create(
                sender=request.user, receiver=receiver, group=None,
                content=content, attachment=attachment,
                attachment_type=attachment_type, reply_to=reply_msg
            )
        elif group_id:
            group_obj = get_object_or_404(Group, id=group_id)
            if not GroupMember.objects.filter(group=group_obj, user=request.user).exists():
                return JsonResponse({'status': 'error', 'message': 'Не в группе'}, status=403)
            msg = Message.objects.create(
                sender=request.user, receiver=None, group=group_obj,
                content=content, attachment=attachment,
                attachment_type=attachment_type, reply_to=reply_msg
            )
        else:
            return JsonResponse({'status': 'error', 'message': 'Нет получателя'}, status=400)

        if content:
            try:
                parsed_content, mentioned_users = parse_mentions(content, group=msg.group)
                if mentioned_users:
                    msg.mentions = json.dumps(mentioned_users)
                    msg.save(update_fields=['mentions'])
                    for mentioned_user in mentioned_users:
                        create_notification(
                            user=mentioned_user,
                            notification_type='mention',
                            title='Упоминание',
                            message=f'{request.user.username} упомянул вас: {content[:50]}',
                            url=f'/{msg.id}/',
                            related_message=msg,
                        )
            except Exception:
                logger.exception('Failed to process mentions for message %s', msg.id)

        return JsonResponse({'status': 'ok'})

    except Exception:
        logger.exception('Failed to create message')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=500)


@login_required
def api_update_group(request, group_id):
    """Обновление настроек группы (название, описание, аватарка)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    group = get_object_or_404(Group, id=group_id)

    if group.owner != request.user:
        return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

    try:
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Название обязательно'}, status=400)

        group.name = name
        group.description = description

        if 'avatar' in request.FILES:
            if group.avatar:
                group.avatar.delete()
            group.avatar = request.FILES['avatar']
        elif request.POST.get('remove_avatar') == 'true' and group.avatar:
            group.avatar.delete()
            group.avatar = None

        group.save()
        return JsonResponse({'status': 'ok'})

    except Exception:
        logger.exception('Failed to update group %s', group_id)
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=500)


@login_required
def api_add_member(request):
    """Добавление участника в группу"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        username = data.get('username', '').strip()

        group = get_object_or_404(Group, id=group_id)
        membership = GroupMember.objects.filter(group=group, user=request.user).first()

        if not membership or membership.role not in ['owner', 'admin']:
            return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

        user = get_object_or_404(User, username=username)

        if GroupMember.objects.filter(group=group, user=user).exists():
            return JsonResponse({'status': 'error', 'message': 'Пользователь уже в группе'}, status=400)

        GroupMember.objects.create(group=group, user=user, role='member')
        return JsonResponse({'status': 'ok'})

    except Exception:
        logger.exception('Failed to add member')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=400)


@login_required
def api_set_role(request):
    """Смена роли участника (владелец -> админ)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        new_role = data.get('role')

        group = get_object_or_404(Group, id=group_id)
        target_user = get_object_or_404(User, id=user_id)

        if group.owner != request.user:
            return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

        if target_user == group.owner:
            return JsonResponse({'status': 'error', 'message': 'Нельзя менять роль владельца'}, status=400)

        membership = GroupMember.objects.get(group=group, user=target_user)
        membership.role = new_role
        membership.save()

        return JsonResponse({'status': 'ok'})

    except GroupMember.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Участник не найден в группе'}, status=404)
    except Exception:
        logger.exception('Failed to set role')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=400)


@login_required
def api_remove_member(request):
    """Удаление участника из группы"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        user_id = data.get('user_id')

        group = get_object_or_404(Group, id=group_id)
        target_user = get_object_or_404(User, id=user_id)
        membership = GroupMember.objects.filter(group=group, user=request.user).first()

        if not membership or membership.role not in ['owner', 'admin']:
            return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

        if target_user == group.owner:
            return JsonResponse({'status': 'error', 'message': 'Нельзя удалить владельца'}, status=400)

        GroupMember.objects.filter(group=group, user=target_user).delete()
        return JsonResponse({'status': 'ok'})

    except Exception:
        logger.exception('Failed to remove member')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=400)


@login_required
def download_attachment(request, message_id):
    """Скачивание файла с оригинальным именем"""
    msg = get_object_or_404(Message, id=message_id)
    if not msg.attachment:
        return redirect('main')

    if msg.sender != request.user and msg.receiver != request.user:
        if msg.group:
            if not GroupMember.objects.filter(group=msg.group, user=request.user).exists():
                return redirect('main')
        else:
            return redirect('main')

    file_path = msg.attachment.path if hasattr(msg.attachment, 'path') else msg.attachment.name
    original_name = msg.attachment_original_name or os.path.basename(file_path)

    try:
        response = FileResponse(open(file_path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = _content_disposition_header(original_name)
        return response
    except FileNotFoundError:
        return JsonResponse({'status': 'error', 'message': 'Файл не найден'}, status=404)


@login_required
def api_heartbeat(request):
    """Обновление статуса онлайн"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    from django.utils import timezone
    request.user.last_seen = timezone.now()
    request.user.save(update_fields=['last_seen'])
    return JsonResponse({'status': 'ok'})


@login_required
def api_channel_post(request, channel_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)
    channel = get_object_or_404(Channel, id=channel_id)
    membership = ChannelMember.objects.filter(channel=channel, user=request.user).first()
    if not membership or membership.role not in ['owner', 'admin']:
        return JsonResponse({'status': 'error', 'message': 'Нет прав на публикацию'}, status=403)
    content = request.POST.get('content', '').strip()
    attachment = request.FILES.get('attachment')
    if not content and not attachment:
        return JsonResponse({'status': 'error', 'message': 'Пустой пост'}, status=400)
    if len(content) > settings.MAX_MESSAGE_LENGTH:
        return JsonResponse({'status': 'error', 'message': 'Слишком длинное'}, status=400)
    try:
        attachment_type = 'none'
        if attachment:
            head = attachment.read(32)
            attachment.seek(0)
            detected = _detect_image_type(head)
            ct = attachment.content_type or ''
            if detected:
                attachment_type = 'image'
            elif ct.startswith('audio/'):
                attachment_type = 'voice'
            elif ct.startswith('image/'):
                attachment_type = 'image'
            else:
                attachment_type = 'file'
        msg = Message.objects.create(
            sender=request.user, channel=channel, receiver=None, group=None,
            content=content, attachment=attachment, attachment_type=attachment_type,
        )
        if content:
            try:
                parsed_content, mentioned_users = parse_mentions(content, group=None)
                if mentioned_users:
                    msg.mentions = json.dumps(mentioned_users)
                    msg.save(update_fields=['mentions'])
                    for uid in mentioned_users:
                        mentioned_user = User.objects.filter(id=uid).first()
                        if mentioned_user:
                            create_notification(
                                user=mentioned_user,
                                notification_type='mention',
                                title='Упоминание в канале',
                                message=f'{request.user.username} упомянул вас в канале: {content[:50]}',
                                url=f'/channel/{channel_id}/',
                                related_message=msg,
                            )
            except Exception:
                logger.exception('Failed to process mentions for channel post')
        return JsonResponse({'status': 'ok'})
    except Exception:
        logger.exception('Failed to create channel post')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=500)

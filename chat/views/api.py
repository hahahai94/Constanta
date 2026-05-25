import os
import json
import hashlib
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import JsonResponse, FileResponse
from django.shortcuts import get_object_or_404, redirect

from chat.models import User, Group, Message, GroupMember
from chat.utils import parse_mentions, create_notification


@login_required
def send_message(request):
    """API: отправка сообщения (личного или группового). Всегда возвращает JSON."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST запросы'}, status=405)

    friend_id = request.POST.get('friend_id')
    group_id = request.POST.get('group_id')
    content = request.POST.get('content', '').strip()
    reply_to_id = request.POST.get('reply_to_id')
    attachment = request.FILES.get('attachment')

    if not content and not attachment:
        return JsonResponse({'status': 'error', 'message': 'Сообщение пустое'}, status=400)

    # 🔹 Обработка вложений
    upload_path = None
    attachment_type = 'none'
    attachment_hash = ''
    attachment_original_name = ''
    attachment_size = 0

    if attachment:
        try:
            if attachment.size > 50 * 1024 * 1024:
                return JsonResponse({'status': 'error', 'message': 'Файл слишком большой (>50МБ)'}, status=400)

            hash_obj = hashlib.sha256()
            for chunk in attachment.chunks():
                hash_obj.update(chunk)
            attachment_hash = hash_obj.hexdigest()
            attachment.seek(0)

            ext = os.path.splitext(attachment.name)[1].lower()
            subdir = attachment_hash[:2]
            filename = f"{attachment_hash}{ext}"
            upload_path = os.path.join('attachments', subdir, filename)

            if attachment.content_type.startswith('image/'):
                attachment_type = 'image'
            elif attachment.content_type.startswith('audio/'):
                attachment_type = 'voice'
            else:
                attachment_type = 'file'

            attachment_size = attachment.size
            attachment_original_name = attachment.name

            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'attachments', subdir), exist_ok=True)
            default_storage.save(upload_path, attachment)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Ошибка файла: {str(e)}'}, status=500)

    # 🔹 Парсинг упоминаний
    parsed_content = content
    mentions_json = '[]'
    mentioned_ids = []
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

    # 🔹 Ответ на сообщение
    reply_msg = None
    if reply_to_id:
        reply_msg = Message.objects.filter(id=reply_to_id).first()

    # 🔹 Создание сообщения
    try:
        if friend_id:
            receiver = get_object_or_404(User, id=friend_id)
            msg = Message.objects.create(
                sender=request.user, receiver=receiver, group=None,
                content=parsed_content,
                attachment=upload_path if upload_path else None,
                attachment_hash=attachment_hash,
                attachment_original_name=attachment_original_name,
                attachment_type=attachment_type,
                attachment_size=attachment_size,
                mentions=mentions_json,
                reply_to=reply_msg
            )
            if receiver != request.user:
                try:
                    create_notification(
                        user=receiver, notification_type='message',
                        title=f'Новое сообщение от {request.user.username}',
                        message=content[:100] if content else '📎 Вложение',
                        url=f'/?friend_id={request.user.id}', related_message=msg
                    )
                except Exception:
                    pass

        elif group_id:
            group = get_object_or_404(Group, id=group_id)
            if GroupMember.objects.filter(group=group, user=request.user).exists():
                msg = Message.objects.create(
                    sender=request.user, receiver=None, group=group,
                    content=parsed_content,
                    attachment=upload_path if upload_path else None,
                    attachment_hash=attachment_hash,
                    attachment_original_name=attachment_original_name,
                    attachment_type=attachment_type,
                    attachment_size=attachment_size,
                    mentions=mentions_json,
                    reply_to=reply_msg
                )
                if mentioned_ids:
                    for uid in mentioned_ids:
                        if uid != request.user.id:
                            try:
                                u = User.objects.get(id=uid)
                                create_notification(
                                    user=u, notification_type='mention',
                                    title=f'Вас упомянули в {group.name}',
                                    message=f'{request.user.username} упомянул вас',
                                    url=f'/groups/{group.id}/', related_message=msg
                                )
                            except User.DoesNotExist:
                                pass
            else:
                return JsonResponse({'status': 'error', 'message': 'Вы не участник группы'}, status=403)
        else:
            return JsonResponse({'status': 'error', 'message': 'Не указан получатель'}, status=400)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Ошибка БД: {str(e)}'}, status=500)


@login_required
def api_heartbeat(request):
    """API: обновление last_seen"""
    if request.method == 'POST' and request.user.is_authenticated:
        from django.utils import timezone
        request.user.last_seen = timezone.now()
        request.user.save(update_fields=['last_seen'])
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'failed'}, status=400)


@login_required
def download_attachment(request, message_id):
    """Скачивание файла с оригинальным именем (ID — UUID)"""
    msg = get_object_or_404(Message, id=message_id)

    if not msg.attachment:
        return redirect('main')

    # 🔒 Проверка прав доступа
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
        response['Content-Disposition'] = f'attachment; filename="{original_name}"'
        return response
    except FileNotFoundError:
        return JsonResponse({'status': 'error', 'message': 'Файл не найден'}, status=404)


@login_required
def api_set_role(request):
    """API: смена роли участника группы (только для владельца)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        new_role = data.get('role')
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Неверный JSON'}, status=400)

    if new_role not in ('member', 'admin'):
        return JsonResponse({'status': 'error', 'message': 'Недопустимая роль'}, status=400)

    group = get_object_or_404(Group, id=group_id)
    target_user = get_object_or_404(User, id=user_id)

    # 🔒 Только владелец может менять роли
    if group.owner != request.user:
        return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

    # Нельзя менять роль самому владельцу
    if target_user == group.owner:
        return JsonResponse({'status': 'error', 'message': 'Нельзя менять роль владельца'}, status=400)

    membership, created = GroupMember.objects.get_or_create(
        group=group, user=target_user,
        defaults={'role': new_role}
    )
    if not created:
        membership.role = new_role
        membership.save(update_fields=['role'])

    return JsonResponse({'status': 'ok'})


@login_required
def api_remove_member(request):
    """API: удаление участника из группы (владелец или админ, но не сам владелец)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        user_id = data.get('user_id')
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Неверный JSON'}, status=400)

    group = get_object_or_404(Group, id=group_id)
    target_user = get_object_or_404(User, id=user_id)

    # 🔒 Права: владелец или админ группы
    if group.owner != request.user:
        requester_member = GroupMember.objects.filter(group=group, user=request.user, role='admin').first()
        if not requester_member:
            return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

    # Нельзя удалить владельца группы
    if target_user == group.owner:
        return JsonResponse({'status': 'error', 'message': 'Нельзя удалить владельца'}, status=400)

    # Админ не может удалить другого админа (только владелец может)
    if group.owner != request.user:
        target_member = GroupMember.objects.filter(group=group, user=target_user, role='admin').first()
        if target_member:
            return JsonResponse({'status': 'error', 'message': 'Только владелец может удалять админов'}, status=403)

    GroupMember.objects.filter(group=group, user=target_user).delete()
    return JsonResponse({'status': 'ok'})


@login_required
def api_add_member(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)

    data = json.loads(request.body)
    group = get_object_or_404(Group, id=data['group_id'])

    if group.owner != request.user:
        return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

    try:
        user = User.objects.get(username=data['username'])
        GroupMember.objects.get_or_create(group=group, user=user)
        return JsonResponse({'status': 'ok'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Пользователь не найден'})


@login_required
def api_update_group(request, group_id):
    """API: обновление настроек группы (название, описание, аватарка)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    group = get_object_or_404(Group, id=group_id)

    # 🔒 Только владелец может менять настройки
    if group.owner != request.user:
        return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

    try:
        # Текстовые поля
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Название обязательно'}, status=400)

        group.name = name
        group.description = description

        # Загрузка новой аватарки
        if 'avatar' in request.FILES:
            # Удаляем старую аватарку если есть
            if group.avatar:
                group.avatar.delete()
            group.avatar = request.FILES['avatar']

        group.save()

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
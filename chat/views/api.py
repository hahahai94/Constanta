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
from django.http import FileResponse
from django.shortcuts import get_object_or_404
import os


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
            attachment.seek(0)  # Сброс указателя для сохранения

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

    #  Парсинг упоминаний
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
            parsed_content = content  # Фолбэк, если парсер упадёт

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
            # Уведомление получателю
            if receiver != request.user:
                try:
                    create_notification(
                        user=receiver, notification_type='message',
                        title=f'Новое сообщение от {request.user.username}',
                        message=content[:100] if content else ' Вложение',
                        url=f'/?friend_id={request.user.id}', related_message=msg
                    )
                except Exception:
                    pass  # Не ломать отправку из-за уведомлений

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
                # Уведомления для упомянутых
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

        # ✅ УСПЕХ: возвращаем только JSON
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
    """Скачивание файла с оригинальным именем"""
    msg = get_object_or_404(Message, id=message_id)

    if not msg.attachment:
        return redirect('main')

    # Проверка прав доступа (только участники диалога/группы)
    if msg.sender != request.user and msg.receiver != request.user:
        if msg.group:
            if not GroupMember.objects.filter(group=msg.group, user=request.user).exists():
                return redirect('main')
        else:
            return redirect('main')

    # Открываем файл
    file_path = msg.attachment.path if hasattr(msg.attachment, 'path') else msg.attachment.name
    original_name = msg.attachment_original_name or os.path.basename(file_path)

    # Отдаём файл с правильным заголовком
    response = FileResponse(open(file_path, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{original_name}"'
    return response
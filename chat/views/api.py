import os
import json
import hashlib
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import JsonResponse, FileResponse
from django.shortcuts import get_object_or_404

from chat.models import User, Group, Message, GroupMember

# Безопасный импорт утилит (если файла utils нет, код не упадет)
try:
    from chat.utils import parse_mentions, create_notification
except ImportError:
    def parse_mentions(text, **kwargs):
        return text, []


    def create_notification(**kwargs):
        pass


@login_required
def send_message(request):
    """Отправка сообщения (личного или группового) с лимитом символов"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    friend_id = request.POST.get('friend_id')
    group_id = request.POST.get('group_id')
    content = request.POST.get('content', '').strip()
    attachment = request.FILES.get('attachment')

    # 🔒 ОГРАНИЧЕНИЕ ПО СИМВОЛАМ (500 символов)
    MAX_CHARS = 500
    if len(content) > MAX_CHARS:
        return JsonResponse({'status': 'error', 'message': f'Сообщение слишком длинное (макс. {MAX_CHARS} символов)'},
                            status=400)

    if not content and not attachment:
        return JsonResponse({'status': 'error', 'message': 'Сообщение пустое'}, status=400)

    # 🔹 Обработка файлов
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

    # 🔹 Сохранение в БД
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
                mentions=mentions_json
            )
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
                    mentions=mentions_json
                )
            else:
                return JsonResponse({'status': 'error', 'message': 'Вы не участник группы'}, status=403)
        else:
            return JsonResponse({'status': 'error', 'message': 'Не указан получатель'}, status=400)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Ошибка БД: {str(e)}'}, status=500)


@login_required
def api_update_group(request, group_id):
    """Обновление настроек группы (название, описание, аватарка)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    group = get_object_or_404(Group, id=group_id)

    # 🔒 Только владелец
    if group.owner != request.user:
        return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

    try:
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Название обязательно'}, status=400)

        group.name = name
        group.description = description

        # Загрузка новой аватарки
        if 'avatar' in request.FILES:
            if group.avatar:
                group.avatar.delete()
            group.avatar = request.FILES['avatar']

        group.save()

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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

        if group.owner != request.user:
            return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

        user = get_object_or_404(User, username=username)

        if GroupMember.objects.filter(group=group, user=user).exists():
            return JsonResponse({'status': 'error', 'message': 'Пользователь уже в группе'}, status=400)

        GroupMember.objects.create(group=group, user=user, role='member')
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


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

        membership, created = GroupMember.objects.get_or_create(group=group, user=target_user)
        membership.role = new_role
        membership.save()

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


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

        if group.owner != request.user:
            return JsonResponse({'status': 'error', 'message': 'Нет прав'}, status=403)

        if target_user == group.owner:
            return JsonResponse({'status': 'error', 'message': 'Нельзя удалить владельца'}, status=400)

        GroupMember.objects.filter(group=group, user=target_user).delete()
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def download_attachment(request, message_id):
    """Скачивание файла с оригинальным именем"""
    msg = get_object_or_404(Message, id=message_id)
    if not msg.attachment:
        return redirect('main')  # Или редирект на главную

    # Проверка прав
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
def api_heartbeat(request):
    """Обновление статуса онлайн"""
    if request.method == 'POST':
        from django.utils import timezone
        request.user.last_seen = timezone.now()
        request.user.save(update_fields=['last_seen'])
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'failed'}, status=400)
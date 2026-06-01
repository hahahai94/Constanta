import os
import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from chat.models import Group, Message, GroupMember

User = get_user_model()

# Безопасный импорт утилит
try:
    from chat.utils import parse_mentions, create_notification
except ImportError:
    def parse_mentions(text, **kwargs): return text, []
    def create_notification(**kwargs): pass


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

    # 🔒 Лимит символов
    MAX_CHARS = 500
    if len(content) > MAX_CHARS:
        return JsonResponse({'status': 'error', 'message': f'Слишком длинное (макс. {MAX_CHARS})'}, status=400)

    if not content and not attachment:
        return JsonResponse({'status': 'error', 'message': 'Пустое сообщение'}, status=400)

    # 🔹 Определение типа вложения
    attachment_type = 'none'
    if attachment:
        if attachment.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            return JsonResponse({'status': 'error', 'message': 'Файл слишком большой'}, status=400)
        content_type = attachment.content_type or ''
        if content_type.startswith('image/'):
            attachment_type = 'image'
        elif content_type.startswith('audio/'):
            attachment_type = 'voice'
        else:
            attachment_type = 'file'

    # 🔹 Привязка к ответу
    reply_msg = None
    if reply_to_id:
        reply_msg = Message.objects.filter(id=reply_to_id).first()

    # 🔹 Создание сообщения
    try:
        if friend_id:
            receiver = get_object_or_404(User, id=friend_id)
            msg = Message.objects.create(
                sender=request.user, receiver=receiver, group=None,
                content=content,
                attachment=attachment,
                attachment_type=attachment_type,
                reply_to=reply_msg
            )
        elif group_id:
            group = get_object_or_404(Group, id=group_id)
            if GroupMember.objects.filter(group=group, user=request.user).exists():
                msg = Message.objects.create(
                    sender=request.user, receiver=None, group=group,
                    content=content,
                    attachment=attachment,
                    attachment_type=attachment_type,
                    reply_to=reply_msg
                )
            else:
                return JsonResponse({'status': 'error', 'message': 'Не в группе'}, status=403)
        else:
            return JsonResponse({'status': 'error', 'message': 'Нет получателя'}, status=400)

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
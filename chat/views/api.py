import mimetypes
import os
import json
import logging
import re
from urllib.parse import quote
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from chat.models import Group, Message, GroupMember, Channel, ChannelMember
from chat.utils import parse_mentions, create_notification, rate_limit
from chat.utils.uploads import detect_attachment_type, normalize_avatar, normalize_upload

logger = logging.getLogger(__name__)
User = get_user_model()

# Сколько новых сообщений отдавать за один опрос. Без ограничения запрос без
# курсора выгружал все сообщения группы или канала (problems.md, П-6).
POLL_MAX_MESSAGES = 200

# Логика определения типа переехала в chat/utils/uploads.py; алиас сохранён,
# потому что на него опираются тесты.
_detect_attachment_type = detect_attachment_type


def _validate_attachment(attachment):
    """Проверяет вложение и нормализует его расширение.

    Изображения проверяются целиком через Pillow, а расширение сохранённого
    файла всегда выводится из содержимого, а не из имени, присланного
    клиентом (problems.md, П-3).

    Возвращает ``(attachment_type, original_name, None)`` при успехе или
    ``(None, None, JsonResponse)`` при ошибке.
    """
    original_name = attachment.name
    try:
        attachment_type, extension = normalize_upload(attachment)
    except ValidationError as exc:
        message = exc.messages[0] if exc.messages else 'Недопустимый файл'
        return None, None, JsonResponse(
            {'status': 'error', 'message': message}, status=400
        )

    # Имя-заглушка: реальный путь строит `_attachment_upload_to` из хеша, здесь
    # важно только безопасное расширение.
    attachment.name = f"upload{extension}"
    return attachment_type, original_name, None


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
@rate_limit('api_send', limit=20, period=60)
def send_message(request):
    """API: отправка сообщения с поддержкой ответов"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    user_id = request.POST.get('user_id')
    group_id = request.POST.get('group_id')
    content = request.POST.get('content', '').strip()
    attachment = request.FILES.get('attachment')
    reply_to_id = request.POST.get('reply_to_id')

    if not user_id and not group_id:
        return JsonResponse({'status': 'error', 'message': 'Нет получателя'}, status=400)

    if user_id:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'Неверный user_id'}, status=400)

    max_chars = settings.MAX_MESSAGE_LENGTH
    if len(content) > max_chars:
        return JsonResponse({'status': 'error', 'message': f'Слишком длинное (макс. {max_chars})'}, status=400)

    if not content and not attachment:
        return JsonResponse({'status': 'error', 'message': 'Пустое сообщение'}, status=400)

    attachment_type = 'none'
    attachment_original_name = ''
    if attachment:
        attachment_type, attachment_original_name, error = _validate_attachment(attachment)
        if error:
            return error

    reply_msg = None
    if reply_to_id:
        reply_msg = Message.objects.filter(id=reply_to_id, is_deleted=False).first()
        if reply_msg:
            if user_id:
                ids = {request.user.id, user_id}
                if (
                    reply_msg.group_id is not None
                    or reply_msg.channel_id is not None
                    or reply_msg.sender_id not in ids
                    or reply_msg.receiver_id not in ids
                ):
                    reply_msg = None
            elif group_id:
                if (
                    reply_msg.group_id is None
                    or str(reply_msg.group_id) != str(group_id)
                    or reply_msg.channel_id is not None
                ):
                    reply_msg = None

    receiver = None
    try:
        if user_id:
            receiver = get_object_or_404(User, id=user_id)
            msg = Message.objects.create(
                sender=request.user, receiver=receiver, group=None,
                content=content, attachment=attachment,
                attachment_type=attachment_type, reply_to=reply_msg,
                attachment_original_name=attachment_original_name,
            )
            template_name = 'parts/message_list.html'
        elif group_id:
            group_obj = get_object_or_404(Group, id=group_id)
            membership = GroupMember.objects.filter(group=group_obj, user=request.user).first()
            if membership is None:
                return JsonResponse({'status': 'error', 'message': 'Не в группе'}, status=403)
            if membership.role == 'muted':
                # Роль «Заблокирован» объявлена в модели, но раньше проверялось
                # только наличие членства (problems.md, П-12).
                return JsonResponse(
                    {'status': 'error', 'message': 'Вы заблокированы в этой группе'},
                    status=403,
                )
            msg = Message.objects.create(
                sender=request.user, receiver=None, group=group_obj,
                content=content, attachment=attachment,
                attachment_type=attachment_type, reply_to=reply_msg,
                attachment_original_name=attachment_original_name,
            )
            template_name = 'parts/group_message_list.html'
        else:
            return JsonResponse({'status': 'error', 'message': 'Нет получателя'}, status=400)

        if content:
            try:
                mentioned_ids = parse_mentions(content, group=msg.group)
                if mentioned_ids:
                    msg.mentions = json.dumps(mentioned_ids)
                    msg.save(update_fields=['mentions'])
                    # один запрос вместо обращения к базе на каждое упоминание
                    recipients = User.objects.filter(
                        id__in=mentioned_ids).exclude(pk=request.user.pk)
                    for mentioned_user in recipients:
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

        if receiver is not None:
            # уведомления о личных сообщениях не создавались вообще (П-29)
            create_notification(
                user=receiver,
                notification_type='message',
                title='Новое сообщение',
                message=f'{request.user.username}: {content[:50] or "вложение"}',
                url=f'/?user_id={request.user.id}',
                related_message=msg,
            )

        from django.template.loader import render_to_string
        html = render_to_string(template_name, {
            'messages': [msg],
            'request': request,
            'user': request.user,
        })
        return JsonResponse({
            'status': 'ok',
            'html': html,
            'message_id': msg.id,
            'cursor': msg.created_at.isoformat(),
            # Превью для списка чатов: обновляется без перезагрузки страницы.
            'preview': msg.preview_text,
            'peer_id': receiver.id if receiver is not None else None,
        })

    except Http404:
        raise
    except Exception:
        logger.exception('Failed to create message')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=500)


@login_required
@rate_limit('api_update_group', limit=10, period=60)
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
            # Сначала проверяем новый файл: иначе при ошибке уже потеряли бы
            # старый аватар (problems.md, П-3).
            try:
                normalize_avatar(request.FILES['avatar'])
            except ValidationError as exc:
                message = exc.messages[0] if exc.messages else 'Недопустимый файл'
                return JsonResponse({'status': 'error', 'message': message}, status=400)
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
@rate_limit('api_add_member', limit=10, period=60)
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

    except Http404:
        raise
    except Exception:
        logger.exception('Failed to add member')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=400)


@login_required
@rate_limit('api_set_role', limit=10, period=60)
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

        # Роль проверяется по модели: `choices` — валидация формы, а не
        # ограничение БД, поэтому раньше можно было записать что угодно,
        # включая 'owner' (problems.md, П-13).
        allowed_roles = [
            value for value, _ in GroupMember.ROLE_CHOICES if value != 'owner'
        ]
        if new_role not in allowed_roles:
            return JsonResponse({'status': 'error', 'message': 'Недопустимая роль'}, status=400)

        if target_user == group.owner:
            return JsonResponse({'status': 'error', 'message': 'Нельзя менять роль владельца'}, status=400)

        membership = GroupMember.objects.get(group=group, user=target_user)
        membership.role = new_role
        membership.save()

        return JsonResponse({'status': 'ok'})

    except GroupMember.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Участник не найден в группе'}, status=404)
    except Http404:
        raise
    except Exception:
        logger.exception('Failed to set role')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=400)


@login_required
@rate_limit('api_remove_member', limit=10, period=60)
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

    except Http404:
        raise
    except Exception:
        logger.exception('Failed to remove member')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=400)


def _user_can_access_message(msg, user):
    """Доступ к вложению: отправитель/получатель, участник группы или подписчик канала.

    Удалённое сообщение недоступно никому, включая отправителя (П-20).
    """
    if msg.is_deleted:
        return False
    if msg.sender_id == user.id or msg.receiver_id == user.id:
        return True
    if msg.group_id and GroupMember.objects.filter(group_id=msg.group_id, user=user).exists():
        return True
    if msg.channel_id and ChannelMember.objects.filter(channel_id=msg.channel_id, user=user).exists():
        return True
    return False


@login_required
@rate_limit('api_delete_message', limit=30, period=60)
def delete_message(request, message_id):
    """Мягкое удаление сообщения его отправителем.

    Поле `is_deleted` существовало с самого начала, но не выставлялось нигде,
    а в выборках уже стояли фильтры — то есть удаление сообщений отсутствовало
    как функция (problems.md, П-20).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    msg = get_object_or_404(Message, id=message_id, is_deleted=False)
    if msg.sender_id != request.user.id:
        return JsonResponse(
            {'status': 'error', 'message': 'Можно удалять только свои сообщения'},
            status=403,
        )

    msg.is_deleted = True
    msg.save(update_fields=['is_deleted', 'updated_at'])
    return JsonResponse({'status': 'ok'})


@login_required
def download_attachment(request, message_id):
    """Скачивание файла с оригинальным именем"""
    msg = get_object_or_404(Message, id=message_id)
    if not msg.attachment:
        return redirect('main')

    if not _user_can_access_message(msg, request.user):
        return redirect('main')

    file_path = msg.attachment.path if hasattr(msg.attachment, 'path') else msg.attachment.name
    original_name = msg.attachment_original_name or os.path.basename(file_path)

    inline = (
        request.GET.get('inline') == '1'
        and msg.attachment_type in {'image', 'voice'}
    )
    content_type = None
    if inline:
        content_type, _ = mimetypes.guess_type(original_name)
        if not (content_type or '').startswith(('image/', 'audio/', 'video/')):
            inline = False
            content_type = None

    try:
        response = FileResponse(
            open(file_path, 'rb'),
            as_attachment=not inline,
            content_type=content_type,
        )
        if inline:
            response['Content-Disposition'] = (
                f'inline; filename="{_safe_filename(original_name)}"')
        else:
            response['Content-Disposition'] = _content_disposition_header(original_name)
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except FileNotFoundError:
        return JsonResponse({'status': 'error', 'message': 'Файл не найден'}, status=404)


@login_required
@rate_limit('api_heartbeat', limit=60, period=60)
def api_heartbeat(request):
    """Обновление статуса онлайн"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Только POST'}, status=405)

    from django.utils import timezone
    request.user.last_seen = timezone.now()
    request.user.save(update_fields=['last_seen'])
    return JsonResponse({'status': 'ok'})


@login_required
@rate_limit('api_channel_post', limit=10, period=60)
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
        attachment_original_name = ''
        if attachment:
            attachment_type, attachment_original_name, error = _validate_attachment(attachment)
            if error:
                return error
        msg = Message.objects.create(
            sender=request.user, channel=channel, receiver=None, group=None,
            content=content, attachment=attachment, attachment_type=attachment_type,
            attachment_original_name=attachment_original_name,
        )
        if content:
            try:
                mentioned_ids = parse_mentions(content, group=None, channel=channel)
                if mentioned_ids:
                    msg.mentions = json.dumps(mentioned_ids)
                    msg.save(update_fields=['mentions'])
                    recipients = User.objects.filter(
                        id__in=mentioned_ids).exclude(pk=request.user.pk)
                    for mentioned_user in recipients:
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
        return JsonResponse({'status': 'ok', 'cursor': msg.created_at.isoformat()})
    except Exception:
        logger.exception('Failed to create channel post')
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=500)


@login_required
@rate_limit('api_poll', limit=180, period=60)
def api_poll(request):
    """Получение новых сообщений (созданных после курсора `after`) — для автообновления.

    Курсор — ISO-8601 метка времени `created_at` последнего известного сообщения.
    Так как `Message.id` — UUID, а не автоинкремент, сравнение по времени корректно
    упорядочивает сообщения и не зависит от порядка создания UUID.

    Лимит поднят до 180/мин: клиент опрашивает эндпоинт раз в 2 секунды, то
    есть ~30 запросов в минуту на вкладку, и прежние 30/60 заблокировали бы
    обычную работу теперь, когда лимит действительно применяется (П-6).
    Ответ ограничен `POLL_MAX_MESSAGES`, чтобы запрос без курсора не выгружал
    весь канал целиком (П-6).
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Только GET'}, status=405)

    after_raw = request.GET.get('after')
    after_dt = None
    if after_raw:
        after_dt = parse_datetime(after_raw)
        if after_dt is None:
            return JsonResponse({'status': 'error', 'message': 'Неверный after'}, status=400)
        if timezone.is_naive(after_dt):
            after_dt = timezone.make_aware(after_dt)

    user = request.user
    user_id = request.GET.get('user_id')
    group_id = request.GET.get('group_id')
    channel_id = request.GET.get('channel_id')

    messages_qs = None

    if user_id:
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Неверный user_id'}, status=400)
        peer = get_object_or_404(User, id=user_id)
        messages_qs = Message.objects.filter(
            Q(sender=user, receiver=peer) | Q(sender=peer, receiver=user),
            is_deleted=False,
        ).order_by('created_at')
        template_name = 'parts/message_list.html'

    elif group_id:
        group = get_object_or_404(Group, id=group_id)
        if not GroupMember.objects.filter(group=group, user=user).exists():
            return JsonResponse({'status': 'error', 'message': 'Нет доступа'}, status=403)
        messages_qs = Message.objects.filter(
            group=group, is_deleted=False
        ).order_by('created_at')
        template_name = 'parts/group_message_list.html'

    elif channel_id:
        channel = get_object_or_404(Channel, id=channel_id)
        if not ChannelMember.objects.filter(channel=channel, user=user).exists():
            return JsonResponse({'status': 'error', 'message': 'Нет доступа'}, status=403)
        messages_qs = Message.objects.filter(
            channel=channel, is_deleted=False
        ).order_by('created_at')
        template_name = 'parts/channel_post_list.html'

    else:
        return JsonResponse({'status': 'error', 'message': 'Укажите user_id, group_id или channel_id'}, status=400)

    if after_dt is not None:
        messages_qs = messages_qs.filter(created_at__gt=after_dt)

    # Все выборки упорядочены по возрастанию `created_at`, поэтому ограничение
    # отдаёт самые старые из новых, а курсор указывает на последнее отданное
    # сообщение — клиент продолжит с него и ничего не потеряет.
    messages = list(messages_qs[:POLL_MAX_MESSAGES])

    from django.template.loader import render_to_string
    html = render_to_string(template_name, {
        'messages': messages,
        'posts': messages,
        'request': request,
        'user': request.user,
    })

    newest = max((m.created_at for m in messages), default=None)

    # Превью последнего сообщения для списка чатов: обновляется без
    # перезагрузки страницы, чтобы под ником не оставался старый текст.
    last_message = messages[-1] if messages else None

    return JsonResponse({
        'html': html,
        'preview': last_message.preview_text if last_message else '',
        'peer_id': peer.id if user_id else None,
        'count': len(messages),
        'cursor': newest.isoformat() if newest else (after_raw or ''),
    })

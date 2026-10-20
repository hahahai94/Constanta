"""Просмотр уведомлений и фоновый опрос (problems.md, П-29)."""

from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from chat.utils.notifications import mark_conversation_read, unread_summary
from users.models import Notification
from users.ratelimit import rate_limit

NOTIFICATIONS_PER_PAGE = 20
NOTIFICATION_SCAN_LIMIT = 500


def _notification_groups(notifications):
    """Одна запись на чат; счётчик — непрочитанные сообщения/события."""
    groups = OrderedDict()
    for note in notifications:
        key = note.conversation_key or f'note:{note.id}'
        group = groups.get(key)
        if group is None:
            group = {
                'id': note.id,
                'conversation_key': note.conversation_key,
                'title': note.title,
                'message': note.message,
                'url': note.url,
                'icon': note.get_icon(),
                'latest_at': note.updated_at or note.created_at,
                'message_unread': 0,
                'event_count': 0,
                'is_unread': False,
            }
            groups[key] = group

        latest_at = note.updated_at or note.created_at
        if latest_at >= group['latest_at']:
            group.update({
                'id': note.id,
                'title': note.title,
                'message': note.message,
                'url': note.url,
                'icon': note.get_icon(),
                'latest_at': latest_at,
            })

        if not note.is_read:
            group['is_unread'] = True
            if note.notification_type == 'message':
                group['message_unread'] += note.unread_count or 1
            else:
                group['event_count'] += 1

    for group in groups.values():
        group['unread_count'] = max(
            group['message_unread'], group['event_count'],
            1 if group['is_unread'] else 0,
        )
    return list(groups.values())


@login_required
def notification_list(request):
    show_all = request.GET.get('all') == '1'
    queryset = Notification.objects.filter(user=request.user)
    queryset = queryset.order_by('-updated_at', '-created_at')
    if show_all:
        notifications = list(queryset[:NOTIFICATION_SCAN_LIMIT])
    else:
        notifications = list(queryset.filter(is_read=False))
    grouped = _notification_groups(notifications)
    page = Paginator(grouped, NOTIFICATIONS_PER_PAGE).get_page(
        request.GET.get('page', 1))
    return render(request, 'notifications.html', {
        'notifications': page,
        'page_obj': page,
        'show_all': show_all,
        'unread_summary': unread_summary(request.user),
    })


@login_required
@require_POST
def mark_all_read(request):
    from chat.models import Message

    Notification.objects.filter(
        user=request.user, is_read=False).update(
            is_read=True, updated_at=timezone.now())
    Message.objects.filter(
        receiver=request.user, is_read=False, is_deleted=False).update(
            is_read=True)
    return redirect('notifications')


@login_required
def open_notification(request, notification_id):
    """Отмечает весь чат прочитанным и ведёт по ссылке уведомления."""
    notification = get_object_or_404(
        Notification, id=notification_id, user=request.user)

    key = notification.conversation_key
    if key:
        mark_conversation_read(request.user, key)
    elif not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read', 'updated_at'])

    # Ссылку строит сервер, но проверяем её на всякий случай: редирект на
    # внешний адрес из уведомления был бы открытым редиректом.
    target = notification.url or ''
    if (
        not target.startswith('/')
        or target.startswith('//')
        or '\\' in target
        or ':' in target.split('/', 1)[0]
    ):
        target = 'main'
    return redirect(target)


@login_required
@rate_limit('notification_poll', limit=120, period=60)
def notification_poll(request):
    """Недавние непрочитанные уведомления для тостов и счётчиков."""
    # Курсор фиксируется до запроса: событие, созданное во время запроса,
    # не потеряется и будет отдано на следующем опросе.
    cursor = timezone.now()
    since = parse_datetime(request.GET.get('since', ''))
    if since is not None and timezone.is_naive(since):
        since = timezone.make_aware(since)

    events = []
    if since is not None:
        notes = Notification.objects.filter(
            user=request.user,
            is_read=False,
            updated_at__gt=since,
            updated_at__lte=cursor,
        ).order_by('-updated_at')[:20]
        for group in _notification_groups(notes):
            events.append({
                'conversation_key': group['conversation_key'],
                'title': group['title'],
                'message': group['message'],
                'url': group['url'],
                'icon': group['icon'],
                'count': group['unread_count'],
            })

    summary = unread_summary(request.user)
    return JsonResponse({
        'events': events,
        'cursor': cursor.isoformat(),
        **summary,
    })

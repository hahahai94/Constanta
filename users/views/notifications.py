"""Просмотр уведомлений (problems.md, П-29)."""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.models import Notification

NOTIFICATIONS_PER_PAGE = 20


@login_required
def notification_list(request):
    queryset = Notification.objects.filter(user=request.user)
    page = Paginator(queryset, NOTIFICATIONS_PER_PAGE).get_page(
        request.GET.get('page', 1))
    return render(request, 'notifications.html', {
        'notifications': page,
        'page_obj': page,
    })


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications')


@login_required
def open_notification(request, notification_id):
    """Отмечает уведомление прочитанным и ведёт по его ссылке."""
    notification = get_object_or_404(
        Notification, id=notification_id, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

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

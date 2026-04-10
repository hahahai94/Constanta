from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.filter
def user_status(user):
    if not user.last_seen:
        return '<span class="status-dot offline"></span> <small class="text-muted">был(а) давно</small>'

    now = timezone.now()
    diff = now - user.last_seen

    if diff < timedelta(minutes=3):
        return '<span class="status-dot online"></span> <small class="text-success">в сети</small>'
    elif diff < timedelta(hours=1):
        return f'<span class="status-dot offline"></span> <small class="text-muted">был(а) {diff.seconds // 60} мин. назад</small>'
    else:
        return f'<span class="status-dot offline"></span> <small class="text-muted">был(а) {diff.days} дн. назад</small>'
from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.filter
def user_status(user):
    if not user or not hasattr(user, 'last_seen'):
        return ''

    if not user.last_seen:
        return '<span class="status-dot offline"></span><small class="text-muted">давно</small>'

    now = timezone.now()
    diff = now - user.last_seen

    if diff < timedelta(minutes=3):
        return '<span class="status-dot online"></span><small class="text-success">онлайн</small>'
    else:
        mins = diff.seconds // 60
        return f'<span class="status-dot offline"></span><small class="text-muted">{mins}м назад</small>'
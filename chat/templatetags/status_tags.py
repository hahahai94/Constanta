from django import template
from django.utils.safestring import mark_safe

from users.presence import format_last_seen, is_user_online

register = template.Library()


@register.filter(is_safe=True)
def user_status(user):
    if not user or not hasattr(user, 'last_seen'):
        return ''

    if is_user_online(user.last_seen):
        return mark_safe('<span class="status-dot online"></span><small class="text-success">онлайн</small>')

    label = format_last_seen(user.last_seen)
    return mark_safe(f'<span class="status-dot offline"></span><small class="text-muted">{label}</small>')

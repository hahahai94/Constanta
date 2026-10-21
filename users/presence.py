from datetime import timedelta

from django.utils import timezone


ONLINE_WINDOW = timedelta(minutes=3)


def is_user_online(last_seen, now=None):
    if not last_seen:
        return False
    now = now or timezone.now()
    return now - last_seen < ONLINE_WINDOW


def _pluralize(value, one, few, many):
    if 11 <= value % 100 <= 14:
        return f'{value} {many}'
    if value % 10 == 1:
        return f'{value} {one}'
    if 2 <= value % 10 <= 4:
        return f'{value} {few}'
    return f'{value} {many}'


def format_last_seen(last_seen, now=None):
    if not last_seen:
        return 'давно'

    now = now or timezone.now()
    seconds = max(0, int((now - last_seen).total_seconds()))

    if seconds < 60:
        return 'меньше минуты'

    minutes = seconds // 60
    if minutes < 60:
        return _pluralize(minutes, 'минута', 'минуты', 'минут')

    hours = minutes // 60
    if hours < 24:
        return _pluralize(hours, 'час', 'часа', 'часов')

    days = hours // 24
    if days < 30:
        return _pluralize(days, 'день', 'дня', 'дней')

    months = days // 30
    if days < 365:
        return _pluralize(months, 'месяц', 'месяца', 'месяцев')

    years = days // 365
    return _pluralize(years, 'год', 'года', 'лет')

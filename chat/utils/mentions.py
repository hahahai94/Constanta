"""Разбор упоминаний.

Разметку здесь больше не строим. Раньше функция возвращала HTML, который оба
вызывающих места выбрасывали, а в базу уходил JSON со списком id — и он же
печатался в шаблоне (problems.md, П-16). Теперь функция отдаёт только id для
уведомлений, а подсветка делается на отображении фильтром `render_mentions`.
"""

import re

# `\\w+` покрывает заявленный набор логина (буквы, цифры, подчёркивание),
# поэтому после экранирования текста в совпадении не может быть разметки.
MENTION_PATTERN = re.compile(r'@(\w+)')


def extract_mentioned_usernames(content):
    """Имена из упоминаний, кроме служебного `@all`."""
    return [name for name in MENTION_PATTERN.findall(content or '') if name != 'all']


def parse_mentions(content, group=None, receiver=None):
    """Возвращает список id упомянутых пользователей.

    `@all` разворачивается в участников группы; в личных чатах и каналах он
    никого не уведомляет, потому что группы там нет.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    mentioned_ids = []

    if group is not None and '@all' in (content or ''):
        from chat.models import GroupMember
        mentioned_ids.extend(
            GroupMember.objects.filter(group=group).values_list('user_id', flat=True)
        )

    usernames = extract_mentioned_usernames(content)
    if usernames:
        mentioned_ids.extend(
            User.objects.filter(username__in=usernames).values_list('id', flat=True)
        )

    return list(set(mentioned_ids))

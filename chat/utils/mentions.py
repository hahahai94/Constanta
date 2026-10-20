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
ALL_MENTION_PATTERN = re.compile(r'(?<![\w@.+-])@all(?![\w@.+-])')


def extract_mentioned_usernames(content):
    """Имена из упоминаний, кроме служебного `@all`."""
    return [name for name in MENTION_PATTERN.findall(content or '') if name != 'all']


def parse_mentions(content, group=None, channel=None, receiver=None):
    """Возвращает id упомянутых пользователей в пределах беседы.

    `@all` разворачивается только в участников группы или подписчиков канала.
    В личном чате допустим только собеседник; глобальный поиск username не
    выполняется, чтобы упоминание не уведомляло постороннего (problems.md,
    П-55, П-56).
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    mentioned_ids = []
    scope_ids = set()

    if receiver is not None:
        scope_ids = {receiver.pk}
    elif group is not None:
        from chat.models import GroupMember
        scope_ids = set(
            GroupMember.objects.filter(group=group).values_list('user_id', flat=True)
        )
    elif channel is not None:
        from chat.models import ChannelMember
        scope_ids = set(
            ChannelMember.objects.filter(channel=channel).values_list('user_id', flat=True)
        )

    if (group is not None or channel is not None) and ALL_MENTION_PATTERN.search(content or ''):
        mentioned_ids.extend(scope_ids)

    usernames = extract_mentioned_usernames(content)
    if usernames and scope_ids:
        mentioned_ids.extend(
            User.objects.filter(
                id__in=scope_ids, username__in=usernames
            ).values_list('id', flat=True)
        )

    return list(set(mentioned_ids))

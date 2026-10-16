"""Фильтры отображения упоминаний.

Раньше `in_mentions`, `mention_class` и `sum_attribute` не использовались ни
в одном шаблоне — их тесты охраняли мёртвый код (problems.md, П-17).
`render_mentions` добавлен вместо сборки HTML при сохранении (П-16).
"""

import json
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

MENTION_PATTERN = re.compile(r'@(\w+)')


def _mentioned_ids(mentions_json):
    """Список id из поля `Message.mentions` (JSON), устойчиво к мусору."""
    if not mentions_json:
        return set()
    try:
        values = json.loads(mentions_json)
    except (TypeError, ValueError):
        return set()
    if not isinstance(values, (list, tuple)):
        return set()
    result = set()
    for value in values:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


@register.filter
def in_mentions(user_id, mentions_json):
    """`True`, если пользователь упомянут в сообщении."""
    try:
        return int(user_id) in _mentioned_ids(mentions_json)
    except (TypeError, ValueError):
        return False


@register.filter
def mention_class(user_id, mentions_json):
    """CSS-класс для сообщения, в котором упомянут текущий пользователь."""
    return 'mentioned' if in_mentions(user_id, mentions_json) else ''


@register.filter
def render_mentions(content):
    """Подсвечивает `@упоминания`, экранируя остальной текст.

    Текст сначала экранируется целиком, и только затем в него подставляется
    разметка: ``@`` + слово не может содержать HTML-спецсимволов, поэтому
    инъекция через содержимое сообщения невозможна.
    """
    text = escape('' if content is None else str(content))
    if '@' not in text:
        return mark_safe(text)

    def replace(match):
        return f'<span class="mention">{match.group(0)}</span>'

    return mark_safe(MENTION_PATTERN.sub(replace, text))

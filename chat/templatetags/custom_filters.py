from django import template
import json

register = template.Library()

@register.filter
def sum_attribute(queryset, attr):
    """Суммирует атрибут у объектов queryset"""
    total = 0
    for obj in queryset:
        total += getattr(obj, attr, 0) or 0
    return total

@register.filter
def in_mentions(user_id, mentions_json):
    try:
        if not mentions_json:
            return False
        mentions = json.loads(mentions_json)
        return int(user_id) in mentions
    except:
        return False


@register.filter
def mention_class(user_id, mentions_json):
    try:
        if not mentions_json:
            return ''
        mentions = json.loads(mentions_json)
        if int(user_id) in mentions:
            return 'mentioned'
        return ''
    except:
        return ''
from django.utils.dateparse import parse_datetime

MESSAGES_PER_PAGE = 200
MESSAGE_RELATED_FIELDS = ('sender', 'receiver', 'reply_to', 'reply_to__sender')


def parse_before(value):
    if not value:
        return None
    try:
        return parse_datetime(value)
    except ValueError:
        return None


def load_message_page(queryset, before=None, limit=MESSAGES_PER_PAGE):
    queryset = queryset.select_related(*MESSAGE_RELATED_FIELDS)
    if before is not None:
        queryset = queryset.filter(created_at__lt=before)
    rows = list(queryset.order_by('-created_at')[:limit + 1])
    has_earlier = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()
    return rows, has_earlier


def build_earlier_url(request, messages, has_earlier):
    if not has_earlier or not messages:
        return ''
    params = request.GET.copy()
    params['before'] = messages[0].created_at.isoformat()
    return f"{request.path}?{params.urlencode()}"

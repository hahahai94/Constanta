"""Единый примитив rate limiting.

Счётчики живут в общем кеше (см. ``CACHES`` в настройках). Ключ **не**
включает ``request.path``: путь содержит UUID ресурса, поэтому прежний лимит
на ``api_channel_post`` обходился созданием новых каналов (problems.md, П-6).

Учёт ведётся атомарно через ``cache.add`` + ``cache.incr``: пара get/set
позволяла параллельным запросам прочитать одно и то же значение и всем
пройти проверку.
"""

from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from users.utils import get_client_ip

RATE_LIMIT_PREFIX = 'ratelimit'


def _cache_key(key):
    return f'{RATE_LIMIT_PREFIX}:{key}'


def peek(key, limit):
    """Возвращает ``True``, если попытка ещё укладывается в лимит.

    Счётчик не увеличивается — нужно, чтобы учитывать только неудачные
    попытки (problems.md, П-7).
    """
    return cache.get(_cache_key(key), 0) < limit


def hit(key, limit, period):
    """Учитывает попытку и возвращает ``(allowed, count)``."""
    cache_key = _cache_key(key)
    if cache.add(cache_key, 1, period):
        return True, 1
    try:
        count = cache.incr(cache_key)
    except ValueError:
        # счётчик истёк между add и incr
        cache.set(cache_key, 1, period)
        return True, 1
    return count <= limit, count


def clear(key):
    """Сбрасывает счётчик."""
    cache.delete(_cache_key(key))


def json_429(request, *args, **kwargs):
    return JsonResponse(
        {'status': 'error', 'message': 'Слишком много запросов. Попробуйте позже.'},
        status=429,
    )


def html_429(request, *args, **kwargs):
    """Ответ для обычных форм: JSON в браузере нечитаем."""
    return HttpResponse(
        'Слишком много запросов. Попробуйте позже.',
        status=429,
        content_type='text/plain; charset=utf-8',
    )


def rate_limit(key_prefix, limit=30, period=60, on_limited=None):
    """Ограничивает частоту запросов к вьюхе.

    Лимит применяется ко **всем** методам, включая GET. Раньше GET/HEAD/OPTIONS
    по умолчанию исключались, поэтому декоратор на ``api_poll`` (GET-only) не
    делал ничего, а самый частый эндпоинт приложения оставался без ограничений
    (problems.md, П-6).

    ``on_limited`` позволяет вернуть ответ, подходящий для HTML-формы;
    по умолчанию отдаётся JSON.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = get_client_ip(request) or 'unknown'
            allowed, _ = hit(f'{key_prefix}:{ip}', limit, period)
            if not allowed:
                responder = on_limited or json_429
                return responder(request, *args, **kwargs)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

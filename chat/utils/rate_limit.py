from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse


def rate_limit(key_prefix, limit=30, period=60):
    """Декоратор rate limiting для API-вьюх (по IP).

    По умолчанию: 30 запросов за 60 секунд.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.META:
                return view_func(request, *args, **kwargs)
            ip = request.META.get('REMOTE_ADDR', 'unknown')
            method = request.method
            path = request.path
            safe_methods = getattr(view_func, '_rate_limit_safe_methods', ['GET', 'HEAD', 'OPTIONS'])
            if method in safe_methods:
                return view_func(request, *args, **kwargs)
            key = f"ratelimit:{key_prefix}:{ip}:{path}"
            count = cache.get(key, 0)
            if count >= limit:
                return JsonResponse(
                    {'status': 'error', 'message': 'Слишком много запросов. Попробуйте позже.'},
                    status=429,
                )
            cache.set(key, count + 1, period)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

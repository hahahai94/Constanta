from django.conf import settings


def get_client_ip(request):
    """Возвращает IP клиента.

    Заголовок X-Forwarded-For учитывается только при USE_X_FORWARDED_FOR=True,
    иначе клиент мог бы подделать свой IP и обойти IP-бан или rate-limit.
    """
    if getattr(settings, 'USE_X_FORWARDED_FOR', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

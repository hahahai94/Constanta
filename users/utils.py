import ipaddress

from django.conf import settings


def normalize_ip(value):
    """Возвращает каноническую форму IP или ``None``, если это не адрес.

    Нужна, чтобы разные записи одного адреса сравнивались с базой одинаково:
    пробелы убираются, IPv6 приводится к каноническому виду, а IPv4-mapped
    адрес (``::ffff:10.0.0.7``) разворачивается в IPv4 — иначе клиент на
    dual-stack слушателе не совпал бы с записью в базе (problems.md, П-33).

    Значения, которые ``ipaddress`` не принимает (например ``127.000.000.001``
    с ведущими нулями), возвращают ``None`` и трактуются как «не адрес».
    """
    if not value:
        return None
    try:
        address = ipaddress.ip_address(str(value).strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return str(address)


def trusted_proxies():
    """Множество доверенных адресов прокси из настроек."""
    proxies = getattr(settings, 'TRUSTED_PROXIES', None) or []
    return {normalize_ip(proxy) or proxy for proxy in proxies}


def _client_ip_from_forwarded(forwarded, trusted):
    """Самый правый адрес в цепочке, который не является доверенным прокси.

    Типовой nginx дописывает заголовок (``$proxy_add_x_forwarded_for``),
    поэтому левое значение контролируется клиентом. Ближайший к приложению
    адрес, который прокси действительно видел, — это первый недоверенный
    адрес при обходе справа налево (problems.md, П-8).
    """
    for hop in reversed([part.strip() for part in forwarded.split(',')]):
        if not hop:
            continue
        candidate = normalize_ip(hop)
        if candidate is None or candidate in trusted:
            continue
        return candidate
    return None


def get_client_ip(request):
    """Возвращает IP клиента.

    Заголовок ``X-Forwarded-For`` учитывается только если сам запрос пришёл с
    адреса из ``TRUSTED_PROXIES``. Без этого любой клиент мог бы подставить
    произвольный IP и обойти IP-бан или rate-limit. Раньше бралось левое
    значение заголовка — это и был обход (problems.md, П-8).
    """
    remote_addr = normalize_ip(request.META.get('REMOTE_ADDR'))
    if remote_addr is None:
        remote_addr = request.META.get('REMOTE_ADDR')

    if not getattr(settings, 'USE_X_FORWARDED_FOR', False):
        return remote_addr

    if not remote_addr:
        return None

    trusted = trusted_proxies()
    if remote_addr not in trusted:
        # запрос пришёл не от прокси — заголовку не верим
        return remote_addr

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if not forwarded:
        return remote_addr

    return _client_ip_from_forwarded(forwarded, trusted) or remote_addr

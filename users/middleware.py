from django.contrib.auth import get_user_model, logout
from django.http import HttpResponseForbidden
from django.conf import settings
from django.shortcuts import render
from django.utils.html import escape

from users.models import BannedIP
from users.utils import get_client_ip

User = get_user_model()


class BannedUserMiddleware:
    """Не пускает забаненного пользователя даже с уже открытой сессией.

    Бэкенд отклоняет бан при входе, но сессия, открытая до бана, оставалась
    рабочей: ``banned_at`` не проверялся нигде (problems.md, П-4). Здесь
    сессия сбрасывается, а пользователь видит ``banned.html`` с причиной.

    Идентификатор берётся прямо из сессии, а не из ``request.user``: слой
    аутентификации уже отбросил забаненного пользователя и вернул анонима,
    поэтому причину блокировки из ``request.user`` показать нельзя.
    """

    SESSION_USER_KEY = '_auth_user_id'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        banned = self._banned_session_user(request)
        if banned is not None:
            # Сначала рендерим ответ, потом разлогиниваем: шаблону нужен
            # объект пользователя, а `logout` его обнуляет.
            response = render(
                request, 'banned.html', {'banned_user': banned}, status=403,
            )
            logout(request)
            return response
        return self.get_response(request)

    @classmethod
    def _banned_session_user(cls, request):
        session = getattr(request, 'session', None)
        if session is None:
            return None
        user_id = session.get(cls.SESSION_USER_KEY)
        if not user_id:
            return None
        try:
            return User.objects.filter(pk=user_id, banned_at__isnull=False).first()
        except (TypeError, ValueError):
            return None


class IPBanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)

        if settings.DEBUG and ip in ['127.0.0.1', '::1', '0.0.0.0']:
            return self.get_response(request)

        if ip and BannedIP.objects.filter(ip_address=ip).exists():
            return HttpResponseForbidden(
                "<h1>Доступ запрещён</h1>"
                "<p>Ваш IP-адрес заблокирован администрацией Constanta.</p>"
                f"<p><small>IP: {escape(ip)}</small></p>"
            )

        return self.get_response(request)

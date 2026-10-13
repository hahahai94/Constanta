from django.http import HttpResponseForbidden
from django.conf import settings
from django.utils.html import escape
from users.models import BannedIP
from users.utils import get_client_ip


class IPBanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)

        if settings.DEBUG and ip in ['127.0.0.1', '::1', '0.0.0.0']:
            return self.get_response(request)

        if BannedIP.objects.filter(ip_address=ip).exists():
            return HttpResponseForbidden(
                "<h1>Доступ запрещён</h1>"
                "<p>Ваш IP-адрес заблокирован администрацией Constanta.</p>"
                f"<p><small>IP: {escape(ip)}</small></p>"
            )

        return self.get_response(request)

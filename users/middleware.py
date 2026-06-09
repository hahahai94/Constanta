from django.http import HttpResponseForbidden
from django.conf import settings
from django.utils.html import escape
from users.models import BannedIP


class IPBanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            ip = ip.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        if settings.DEBUG and ip in ['127.0.0.1', '::1', '0.0.0.0']:
            return self.get_response(request)

        if BannedIP.objects.filter(ip_address=ip).exists():
            return HttpResponseForbidden(
                "<h1>Доступ запрещён</h1>"
                "<p>Ваш IP-адрес заблокирован администрацией Constanta.</p>"
                f"<p><small>IP: {escape(ip)}</small></p>"
            )

        return self.get_response(request)

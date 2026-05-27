# chat/middleware.py
from django.http import HttpResponseForbidden
from django.conf import settings
from chat.models import BannedIP

class IPBanMiddleware:
    def __init__(self, get_response):
        """Django требует такой сигнатуры: (self, get_response)"""
        self.get_response = get_response

    def __call__(self, request):
        # Получаем реальный IP (учитывает прокси/Cloudflare)
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            ip = ip.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        # 🔒 Пропускаем бан в режиме отладки для локальных адресов
        if settings.DEBUG and ip in ['127.0.0.1', '::1', '0.0.0.0']:
            return self.get_response(request)

        # Блокировка
        if BannedIP.objects.filter(ip_address=ip).exists():
            return HttpResponseForbidden(
                "<h1>🚫 Доступ запрещён</h1>"
                "<p>Ваш IP-адрес заблокирован администрацией Constanta.</p>"
                f"<p><small>IP: {ip}</small></p>"
            )

        return self.get_response(request)
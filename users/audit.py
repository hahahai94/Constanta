"""Запись действий администраторов.

Модель ``AdminLog`` существовала с самого начала, но в неё не писал никто:
удаление групп и сообщений вместе с файлами, баны и смены ролей не оставляли
следа (problems.md, П-5).
"""

import logging

from users.utils import get_client_ip, normalize_ip

logger = logging.getLogger(__name__)


def log_admin_action(admin, action, description, target_user=None, request=None,
                     ip_address=None):
    """Создаёт запись аудита.

    Аудит не должен ломать само действие администратора, поэтому любая ошибка
    записи логируется и проглатывается.
    """
    from users.models import AdminLog

    if ip_address is None and request is not None:
        ip_address = get_client_ip(request)
    if ip_address is not None and normalize_ip(ip_address) is None:
        ip_address = None

    try:
        return AdminLog.objects.create(
            admin=admin,
            action=action,
            description=description,
            target_user=target_user,
            ip_address=ip_address,
        )
    except Exception:
        logger.exception('Failed to write admin log entry for action %s', action)
        return None

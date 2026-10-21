import uuid
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver

from chat.utils.uploads import user_avatar_upload_to
from users.presence import is_user_online


class User(AbstractUser):
    nick = models.CharField(max_length=50, unique=True, null=True, blank=True)
    avatar = models.ImageField(upload_to=user_avatar_upload_to, null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True, default='')
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Последний вход")

    @property
    def is_online(self):
        return is_user_online(self.last_seen)

    ban_reason = models.TextField(blank=True, default='Нарушение правил')
    banned_at = models.DateTimeField(null=True, blank=True)
    banned_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='banned_users'
    )

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.nick if self.nick else self.username

    def get_display_name(self):
        return self.nick if self.nick else self.username

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return settings.STATIC_URL + 'default_avatar.png'


class AdminLog(models.Model):
    ACTION_CHOICES = [
        ('delete_user', 'Удаление пользователя'),
        ('impersonate', 'Вход под пользователем'),
        ('edit_message', 'Редактирование сообщения'),
        ('edit_profile', 'Изменение профиля'),
        ('ban_user', 'Бан пользователя'),
        ('unban_user', 'Разбан пользователя'),
        ('delete_message', 'Удаление сообщения'),
        ('delete_group', 'Удаление группы'),
        ('change_role', 'Изменение роли'),
        ('kick_member', 'Исключение из группы'),
        ('ban_ip', 'Блокировка IP'),
        ('unban_ip', 'Разблокировка IP'),
    ]

    admin = models.ForeignKey(
        User, related_name='admin_actions', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    admin_username = models.CharField(max_length=150, blank=True, default='')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_user = models.ForeignKey(User, related_name='admin_logs', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'admin_logs'
        ordering = ['-timestamp']
        verbose_name = 'Лог админа'
        verbose_name_plural = 'Логи админа'

    def save(self, *args, **kwargs):
        if self.admin_id:
            self.admin_username = self.admin.username
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'admin_username'}
        super().save(*args, **kwargs)

    def __str__(self):
        admin_name = self.admin_username
        if not admin_name and self.admin_id:
            admin_name = self.admin.username
        return f"{admin_name or '—'} -> {self.action} -> {self.target_user}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('message', 'Новое сообщение'),
        ('mention', 'Упоминание'),
        ('group_add', 'Добавлен в группу'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    url = models.CharField(max_length=500, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Одна запись на непрочитанный чат: direct:<id>, group:<uuid>, channel:<uuid>.
    conversation_key = models.CharField(
        max_length=80, blank=True, default='', db_index=True)
    unread_count = models.PositiveIntegerField(default=1)

    related_message = models.ForeignKey('chat.Message', related_name='notifications', on_delete=models.CASCADE, null=True,
                                        blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-updated_at', '-created_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['user', 'is_read', '-updated_at']),
            models.Index(fields=['user', 'conversation_key', 'is_read']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'conversation_key'],
                condition=models.Q(
                    notification_type='message',
                    is_read=False,
                ) & ~models.Q(conversation_key=''),
                name='uniq_unread_message_notification',
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.notification_type}"

    def get_icon(self):
        icons = {
            'message': '💬',
            'mention': '📢',
            'group_add': '📁',
        }
        return icons.get(self.notification_type, '🔔')


class BannedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True, verbose_name="IP-Адрес")
    reason = models.TextField(blank=True, verbose_name="Причина бана")
    banned_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата бана")
    banned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='banned_ips',
        verbose_name="Забанил админ"
    )

    class Meta:
        verbose_name = "Заблокированный IP"
        verbose_name_plural = "Заблокированные IP"
        ordering = ['-banned_at']

    def __str__(self):
        return f"IP: {self.ip_address}"


@receiver([post_save, post_delete], sender=BannedIP)
def _invalidate_banned_ip_cache(sender, **kwargs):
    """Сбрасывает кеш списка банов, чтобы бан действовал сразу (П-32)."""
    from users.middleware import IPBanMiddleware
    cache.delete(IPBanMiddleware.CACHE_KEY)


@receiver(post_delete, sender=User)
def _delete_user_avatar(sender, instance, **kwargs):
    """Удаляет файл аватара вместе с пользователем (П-48)."""
    avatar = instance.avatar
    name = getattr(avatar, 'name', '')
    if name and avatar.storage.exists(name):
        avatar.storage.delete(name)

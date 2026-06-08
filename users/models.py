import uuid
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    nick = models.CharField(max_length=50, unique=True, null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True, default='')
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Последний вход")

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        return timezone.now() - self.last_seen < timedelta(minutes=3)

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
    ]

    admin = models.ForeignKey(User, related_name='admin_actions', on_delete=models.CASCADE)
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

    def __str__(self):
        return f"{self.admin.username} -> {self.action} -> {self.target_user}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('message', 'Новое сообщение'),
        ('mention', 'Упоминание'),
        ('friend_request', 'Запрос в друзья'),
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

    related_message = models.ForeignKey('chat.Message', related_name='notifications', on_delete=models.CASCADE, null=True,
                                        blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.notification_type}"

    def get_icon(self):
        icons = {
            'message': '💬',
            'mention': '📢',
            'friend_request': '👥',
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

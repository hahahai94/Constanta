import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    """
    Расширенная модель пользователя с аватарками, никами и системой банов
    """
    nick = models.CharField(max_length=50, unique=True, null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True, default='')
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Последний вход")

    # 🔹 Поля для системы банов
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
        return '/static/default_avatar.png'


class Friendship(models.Model):
    """
    Таблица дружбы между пользователями
    """
    user = models.ForeignKey(User, related_name='friends', on_delete=models.CASCADE)
    friend = models.ForeignKey(User, related_name='friends_of', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'friends'
        unique_together = ('user', 'friend')
        verbose_name = 'Дружба'
        verbose_name_plural = 'Друзья'

    def __str__(self):
        return f"{self.user.username} -> {self.friend.username}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    mentions = models.TextField(blank=True, default='')  # Хранит JSON с упомянутыми user_id
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE, null=True,
                                 blank=True)
    group = models.ForeignKey('Group', related_name='messages', on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()

    # 🔹 Вложения с хешированием
    attachment_type = models.CharField(max_length=20, choices=[
        ('none', 'Нет'),
        ('image', 'Изображение'),
        ('file', 'Файл'),
        ('voice', 'Голосовое'),
    ], default='none')
    attachment = models.FileField(upload_to='attachments/', null=True, blank=True)
    attachment_hash = models.CharField(max_length=64, blank=True, default='')  # SHA256 хеш
    attachment_original_name = models.CharField(max_length=255, blank=True, default='')  # Оригинальное имя
    attachment_size = models.BigIntegerField(default=0)

    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        indexes = [
            models.Index(fields=['sender', 'receiver', '-created_at']),
            models.Index(fields=['group', '-created_at']),
            models.Index(fields=['attachment_hash']),  # Для поиска дубликатов
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.content[:20]}"

    def get_attachment_url(self):
        if self.attachment:
            return self.attachment.url
        return None

    def get_attachment_name(self):
        # Возвращаем оригинальное имя если есть, иначе имя файла
        if self.attachment_original_name:
            return self.attachment_original_name
        if self.attachment:
            return self.attachment.name.split('/')[-1]
        return None

    def save(self, *args, **kwargs):
        # Автоматическое сохранение оригинального имени при первом сохранении
        if self.attachment and not self.attachment_original_name:
            self.attachment_original_name = self.attachment.name.split('/')[-1]
        super().save(*args, **kwargs)


class Group(models.Model):
    """
    Модель группы для групповых чатов
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    owner = models.ForeignKey(User, related_name='owned_groups', on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='group_avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'groups'
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'

    def __str__(self):
        return self.name

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return '/static/default_group_avatar.png'

    def is_owner(self, user):
        return self.owner == user

    def is_member(self, user):
        return GroupMember.objects.filter(group=self, user=user).exists()


class GroupMember(models.Model):
    """
    Участники группы с ролями (владелец, админ, участник, забанен)
    """
    ROLE_CHOICES = [
        ('owner', 'Владелец'),
        ('admin', 'Администратор'),
        ('member', 'Участник'),
        ('muted', 'Заблокирован'),
    ]

    group = models.ForeignKey(Group, related_name='members', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='group_memberships', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_members'
        unique_together = ('group', 'user')
        verbose_name = 'Участник группы'
        verbose_name_plural = 'Участники групп'

    def __str__(self):
        return f"{self.user.username} in {self.group.name} ({self.role})"

    def can_kick(self):
        return self.role in ['owner', 'admin']

    def can_change_role(self):
        return self.role == 'owner'


class AdminLog(models.Model):
    """
    Логирование всех действий администратора/создателя
    """
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
        return f"{self.admin.username} → {self.action} → {self.target_user}"


class Notification(models.Model):
    """Уведомления для пользователей"""
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

    related_message = models.ForeignKey(Message, related_name='notifications', on_delete=models.CASCADE, null=True,
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
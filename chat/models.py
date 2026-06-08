import uuid
import os
import hashlib
from datetime import datetime
from django.conf import settings
from django.db import models



def _file_hash(file_obj, user_id):
    content = file_obj.read()
    file_obj.seek(0)
    ts = datetime.now().isoformat()
    return hashlib.sha256(f"{content.hex()}{user_id}{ts}".encode('utf-8')).hexdigest()


def _attachment_upload_to(instance, filename):
    if instance.attachment_hash:
        h = instance.attachment_hash
    else:
        h = _file_hash(instance.attachment, instance.sender.id)
    ext = os.path.splitext(filename)[1].lower()
    return os.path.join('attachments', h[:2], f"{h}{ext}")


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    mentions = models.TextField(blank=True, default='')  # Хранит JSON с упомянутыми user_id
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE, null=True,
                                 blank=True)
    group = models.ForeignKey('Group', related_name='messages', on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()

    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name="Ответ на"
    )

    # 🔹 Вложения с хешированием
    attachment_type = models.CharField(max_length=20, choices=[
        ('none', 'Нет'),
        ('image', 'Изображение'),
        ('file', 'Файл'),
        ('voice', 'Голосовое'),
    ], default='none')
    attachment = models.FileField(upload_to=_attachment_upload_to, null=True, blank=True)
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
        if self.attachment_original_name:
            return self.attachment_original_name
        if self.attachment:
            return self.attachment.name.split('/')[-1]
        return None

    def save(self, *args, **kwargs):
        if self.attachment:
            if not self.attachment_hash:
                self.attachment_hash = _file_hash(self.attachment, self.sender.id)
            if not self.attachment_original_name:
                self.attachment_original_name = self.attachment.name
            if not self.attachment_size:
                try:
                    self.attachment_size = self.attachment.size
                except Exception:
                    pass
        super().save(*args, **kwargs)


class Group(models.Model):
    """
    Модель группы для групповых чатов
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='owned_groups', on_delete=models.CASCADE)
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
        return settings.STATIC_URL + 'default_group_avatar.png'

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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='group_memberships', on_delete=models.CASCADE)
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



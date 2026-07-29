import uuid
import os
from django.conf import settings
from django.db import models
from chat.utils import generate_file_hash


def _attachment_upload_to(instance, filename):
    if instance.attachment_hash:
        h = instance.attachment_hash
    else:
        h = generate_file_hash(instance.attachment, instance.sender.id)
    ext = os.path.splitext(filename)[1].lower()
    return os.path.join('attachments', h[:2], f"{h}{ext}")


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    mentions = models.TextField(blank=True, default='')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE, null=True,
                                 blank=True)
    group = models.ForeignKey('Group', related_name='messages', on_delete=models.CASCADE, null=True, blank=True)
    channel = models.ForeignKey('Channel', related_name='messages', on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()

    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name="Ответ на"
    )

    attachment_type = models.CharField(max_length=20, choices=[
        ('none', 'Нет'),
        ('image', 'Изображение'),
        ('file', 'Файл'),
        ('voice', 'Голосовое'),
    ], default='none')
    attachment = models.FileField(upload_to=_attachment_upload_to, null=True, blank=True)
    attachment_hash = models.CharField(max_length=64, blank=True, default='')
    attachment_original_name = models.CharField(max_length=255, blank=True, default='')
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
            models.Index(fields=['channel', '-created_at']),
            models.Index(fields=['attachment_hash']),
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
                self.attachment_hash = generate_file_hash(self.attachment, self.sender.id)
            if not self.attachment_original_name:
                self.attachment_original_name = self.attachment.name
            if not self.attachment_size:
                try:
                    self.attachment_size = self.attachment.size
                except Exception:
                    pass
        super().save(*args, **kwargs)

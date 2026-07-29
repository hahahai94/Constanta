import uuid
from django.conf import settings
from django.db import models


class Channel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='owned_channels', on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='channel_avatars/', null=True, blank=True)
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'channels'
        verbose_name = 'Канал'
        verbose_name_plural = 'Каналы'

    def __str__(self):
        return self.name

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return settings.STATIC_URL + 'default_channel_avatar.png'

    def is_owner(self, user):
        return self.owner == user

    def is_admin(self, user):
        return ChannelMember.objects.filter(channel=self, user=user, role__in=['owner', 'admin']).exists()

    def is_subscriber(self, user):
        return ChannelMember.objects.filter(channel=self, user=user).exists()


class ChannelMember(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Владелец'),
        ('admin', 'Администратор'),
        ('subscriber', 'Подписчик'),
    ]

    channel = models.ForeignKey(Channel, related_name='members', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='channel_memberships', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='subscriber')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'channel_members'
        unique_together = ('channel', 'user')
        verbose_name = 'Подписчик канала'
        verbose_name_plural = 'Подписчики каналов'

    def __str__(self):
        return f"{self.user.username} in {self.channel.name} ({self.role})"

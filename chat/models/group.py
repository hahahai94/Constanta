import uuid
from django.conf import settings
from django.db import models


class Group(models.Model):
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

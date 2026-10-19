from django.db.models.signals import post_delete
from django.dispatch import receiver

from chat.models import Channel, Group, Message


def _delete_file(field_file):
    if not field_file:
        return
    name = getattr(field_file, 'name', '')
    if not name:
        return
    storage = field_file.storage
    if storage.exists(name):
        storage.delete(name)


@receiver(post_delete, sender=Message)
def delete_message_attachment(sender, instance, **kwargs):
    if not instance.attachment:
        return
    attachment_name = instance.attachment.name
    if Message.objects.filter(attachment=attachment_name).exists():
        return
    _delete_file(instance.attachment)


@receiver(post_delete, sender=Group)
def delete_group_avatar(sender, instance, **kwargs):
    _delete_file(instance.avatar)


@receiver(post_delete, sender=Channel)
def delete_channel_avatar(sender, instance, **kwargs):
    _delete_file(instance.avatar)

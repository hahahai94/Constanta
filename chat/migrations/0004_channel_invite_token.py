import uuid
from django.db import migrations, models


def populate_tokens(apps, schema_editor):
    # AddField заполняет все существующие строки одним и тем же значением
    # default, поэтому проставляем каждой строке свой уникальный токен.
    Channel = apps.get_model('chat', 'Channel')
    for channel in Channel.objects.all():
        channel.invite_token = uuid.uuid4()
        channel.save(update_fields=['invite_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_channelmember_channel_message_channel_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='channel',
            name='invite_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='channel',
            name='invite_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

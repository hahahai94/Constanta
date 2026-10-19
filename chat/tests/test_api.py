from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from chat.models import Message, Group, GroupMember, Channel, ChannelMember
from chat.views.api import _detect_attachment_type, _content_disposition_header
from chat.tests.factories import image_upload, make_png
from django.utils.dateparse import parse_datetime
from unittest import mock
import json, io, os

User = get_user_model()


class APITests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username='api_tester', password='123')
        self.other = User.objects.create_user(username='api_other', password='456')
        self.client.login(username='api_tester', password='123')

    def test_heartbeat_auth(self):
        response = self.client.post('/api/heartbeat/')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'ok'})

    def test_heartbeat_anonymous(self):
        self.client.logout()
        response = self.client.post('/api/heartbeat/')
        self.assertIn(response.status_code, [302, 403])

    def test_heartbeat_get_fails(self):
        response = self.client.get('/api/heartbeat/')
        self.assertEqual(response.status_code, 405)

    def test_send_empty_message(self):
        """П-41: раньше запрос падал на 404 и проверка содержимого не работала."""
        response = self.client.post('/api/send/', {
            'user_id': str(self.other.id), 'content': '',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Message.objects.filter(sender=self.user).exists())

    def test_send_message_no_recipient(self):
        response = self.client.post('/api/send/', {'content': 'hello'})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Нет получателя', data['message'])

    def test_send_private_message(self):
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'Hello there!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(
            sender=self.user, receiver=self.other, content='Hello there!'
        ).exists())

    def test_send_message_too_long(self):
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'x' * (settings.MAX_MESSAGE_LENGTH + 1)
        })
        self.assertEqual(response.status_code, 400)

    def test_send_file_message(self):
        file = SimpleUploadedFile("test.png", make_png(), content_type="image/png")
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'Check this',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertEqual(msg.attachment_type, 'image')

    def test_send_file_message_audio(self):
        file = SimpleUploadedFile("voice.ogg", io.BytesIO(b'audio').read(), content_type="audio/ogg")
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'Voice message',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertEqual(msg.attachment_type, 'voice')

    def test_send_file_message_other(self):
        file = SimpleUploadedFile("doc.pdf", io.BytesIO(b'pdf').read(), content_type="application/pdf")
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'Document',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertEqual(msg.attachment_type, 'file')

    def test_send_message_get_fails(self):
        response = self.client.get('/api/send/')
        self.assertEqual(response.status_code, 405)

    def test_download_attachment(self):
        file = SimpleUploadedFile("download.txt", b"content", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.user, receiver=self.other,
            content='With file', attachment=file
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 200)

    def test_download_attachment_no_file(self):
        msg = Message.objects.create(
            sender=self.user, receiver=self.other,
            content='No file'
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 302)

    def test_download_attachment_unauthorized(self):
        stranger = User.objects.create_user(username='stranger', password='789')
        msg = Message.objects.create(
            sender=stranger, receiver=stranger,
            content='Private'
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 302)

    def test_download_attachment_not_found(self):
        response = self.client.get('/download/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)

    def test_api_update_group_get_fails(self):
        group = Group.objects.create(name='G', owner=self.user)
        response = self.client.get(f'/groups/{group.id}/settings/')
        self.assertEqual(response.status_code, 405)

    def test_api_update_group_not_owner(self):
        group = Group.objects.create(name='G', owner=self.other)
        response = self.client.post(f'/groups/{group.id}/settings/', {'name': 'Hacked'})
        self.assertEqual(response.status_code, 403)

    def test_api_update_group_success(self):
        group = Group.objects.create(name='Original', owner=self.user)
        response = self.client.post(f'/groups/{group.id}/settings/', {'name': 'Updated'})
        self.assertEqual(response.status_code, 200)
        group.refresh_from_db()
        self.assertEqual(group.name, 'Updated')

    def test_api_update_group_no_name(self):
        group = Group.objects.create(name='Original', owner=self.user)
        response = self.client.post(f'/groups/{group.id}/settings/', {'name': ''})
        self.assertEqual(response.status_code, 400)

    def test_detect_attachment_type_none(self):
        result = _detect_attachment_type(b'\x00\x00\x00', '')
        self.assertEqual(result, 'file')

    def test_content_disposition_non_ascii(self):
        result = _content_disposition_header('файл.txt')
        self.assertIn('filename*', result)

    def test_send_oversized_file(self):
        file = SimpleUploadedFile("big.bin", b"x" * (settings.FILE_UPLOAD_MAX_MEMORY_SIZE + 1), content_type="application/octet-stream")
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'big',
            'attachment': file
        })
        self.assertEqual(response.status_code, 400)

    def test_send_message_with_mention(self):
        mentioned = User.objects.create_user(username='mention_target', password='123')
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': f'Hello @{mentioned.username}'
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertIn(str(mentioned.id), msg.mentions)

    def test_send_message_to_group(self):
        group = Group.objects.create(name='Test Group', owner=self.user)
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        response = self.client.post('/api/send/', {
            'group_id': str(group.id),
            'content': 'Group message'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(group=group, content='Group message').exists())

    def test_send_message_to_group_not_member(self):
        group = Group.objects.create(name='Private', owner=self.other)
        response = self.client.post('/api/send/', {
            'group_id': str(group.id),
            'content': 'Hack'
        })
        self.assertEqual(response.status_code, 403)

    def test_private_reply_to_group_message_ignored(self):
        group = Group.objects.create(name='Reply Group', owner=self.other)
        reply_to = Message.objects.create(
            sender=self.other, group=group, content='Group original')

        response = self.client.post('/api/send/', {
            'user_id': str(self.other.id),
            'content': 'Private reply',
            'reply_to_id': str(reply_to.id),
        })
        self.assertEqual(response.status_code, 200)
        message = Message.objects.get(
            sender=self.user, receiver=self.other, content='Private reply')
        self.assertIsNone(message.reply_to)

    def test_group_reply_to_private_message_ignored(self):
        group = Group.objects.create(name='Reply Group 2', owner=self.user)
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        reply_to = Message.objects.create(
            sender=self.other, receiver=self.user, content='Private original')

        response = self.client.post('/api/send/', {
            'group_id': str(group.id),
            'content': 'Group reply',
            'reply_to_id': str(reply_to.id),
        })
        self.assertEqual(response.status_code, 200)
        message = Message.objects.get(group=group, content='Group reply')
        self.assertIsNone(message.reply_to)

    def test_reply_to_deleted_message_ignored(self):
        reply_to = Message.objects.create(
            sender=self.other, receiver=self.user, content='Deleted original',
            is_deleted=True)

        response = self.client.post('/api/send/', {
            'user_id': str(self.other.id),
            'content': 'Reply to deleted',
            'reply_to_id': str(reply_to.id),
        })
        self.assertEqual(response.status_code, 200)
        message = Message.objects.get(
            sender=self.user, receiver=self.other, content='Reply to deleted')
        self.assertIsNone(message.reply_to)

    def test_reply_to_wrong_group_ignored(self):
        group1 = Group.objects.create(name='Group One', owner=self.user)
        GroupMember.objects.create(group=group1, user=self.user, role='owner')
        group2 = Group.objects.create(name='Group Two', owner=self.user)
        GroupMember.objects.create(group=group2, user=self.user, role='owner')
        reply_to = Message.objects.create(sender=self.user, group=group1, content='Original in group1')
        response = self.client.post('/api/send/', {
            'group_id': str(group2.id),
            'content': 'Reply to wrong group',
            'reply_to_id': str(reply_to.id)
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(group=group2, content='Reply to wrong group')
        self.assertIsNone(msg.reply_to)

    def test_api_update_group_remove_avatar(self):
        group = Group.objects.create(name='Av Group', owner=self.user)
        response = self.client.post(f'/groups/{group.id}/settings/', {
            'name': 'No Av',
            'remove_avatar': 'true'
        })
        self.assertEqual(response.status_code, 200)

    def test_api_add_member_get_fails(self):
        response = self.client.get('/api/add-member/')
        self.assertEqual(response.status_code, 405)

    def test_api_remove_member_get_fails(self):
        response = self.client.get('/api/remove-member/')
        self.assertEqual(response.status_code, 405)

    def test_api_set_role_get_fails(self):
        response = self.client.get('/api/set-role/')
        self.assertEqual(response.status_code, 405)

    def test_api_add_member_already_exists(self):
        group = Group.objects.create(name='G5', owner=self.user)
        GroupMember.objects.create(group=group, user=self.other, role='member')
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        response = self.client.post('/api/add-member/', json.dumps({
            'group_id': str(group.id), 'username': self.other.username
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_api_set_role_not_owner(self):
        group = Group.objects.create(name='G6', owner=self.other)
        GroupMember.objects.create(group=group, user=self.other, role='owner')
        self.client.logout()
        stranger = User.objects.create_user(username='stranger3', password='123')
        self.client.login(username='stranger3', password='123')
        response = self.client.post('/api/set-role/', json.dumps({
            'group_id': str(group.id), 'user_id': self.other.id, 'role': 'member'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_api_set_role_protect_owner(self):
        group = Group.objects.create(name='G7', owner=self.user)
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        response = self.client.post('/api/set-role/', json.dumps({
            'group_id': str(group.id), 'user_id': self.user.id, 'role': 'member'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('владельца', data['message'])

    def test_api_set_role_not_in_group(self):
        group = Group.objects.create(name='G8', owner=self.user)
        stranger = User.objects.create_user(username='stranger2', password='123')
        response = self.client.post('/api/set-role/', json.dumps({
            'group_id': str(group.id), 'user_id': stranger.id, 'role': 'admin'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_api_remove_member_protect_owner(self):
        group = Group.objects.create(name='G9', owner=self.user)
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        response = self.client.post('/api/remove-member/', json.dumps({
            'group_id': str(group.id), 'user_id': self.user.id
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_download_attachment_via_group(self):
        group = Group.objects.create(name='Shared', owner=self.user)
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        GroupMember.objects.create(group=group, user=self.other, role='member')
        file = SimpleUploadedFile("group_file.txt", b"shared", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.other, group=group,
            content='Group file', attachment=file
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 200)

    def test_download_attachment_file_missing(self):
        file = SimpleUploadedFile("temp.txt", b"gone", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.user, receiver=self.other,
            content='Temporary', attachment=file
        )
        os.remove(msg.attachment.path)
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 404)

    def test_download_attachment_group_member_unauthorized(self):
        group = Group.objects.create(name='Secret', owner=self.other)
        file = SimpleUploadedFile("secret.txt", b"secret", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.other, group=group,
            content='Secret file', attachment=file
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 302)

    def test_api_update_group_with_old_avatar(self):
        file = image_upload("old_av.png")
        group = Group.objects.create(name='Old Av', owner=self.user, avatar=file)
        old_path = group.avatar.path
        new_file = image_upload("new_av.png")
        response = self.client.post(f'/groups/{group.id}/settings/', {
            'name': 'New Av',
            'avatar': new_file
        })
        self.assertEqual(response.status_code, 200)
        group.refresh_from_db()
        self.assertTrue(group.avatar)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(group.avatar.name.endswith('.png'))

    def test_send_message_invalid_image_rejected(self):
        file = SimpleUploadedFile("weird.png", b'\x00\x00\x00', content_type="image/png")
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'Detected by content_type',
            'attachment': file
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Message.objects.filter(content='Detected by content_type').exists())

    def test_send_message_image_detected_by_magic_bytes(self):
        file = SimpleUploadedFile("weird.bin", make_png(), content_type="application/octet-stream")
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'Detected by magic bytes',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other, content='Detected by magic bytes')
        self.assertEqual(msg.attachment_type, 'image')

    def test_send_invalid_user_id_returns_400(self):
        response = self.client.post('/api/send/', {'user_id': 'abc', 'content': 'hi'})
        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(response.status_code, 500)

    def test_send_response_contains_cursor(self):
        response = self.client.post('/api/send/', {
            'user_id': self.other.id, 'content': 'cursor test'
        })
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('cursor', data)
        self.assertTrue(data['cursor'])


class PollAPITests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username='poll_a', password='123')
        self.b = User.objects.create_user(username='poll_b', password='123')
        self.client.login(username='poll_a', password='123')

    def test_poll_invalid_after_returns_400(self):
        response = self.client.get('/api/poll/', {'after': 'not-a-date', 'user_id': self.b.id})
        self.assertEqual(response.status_code, 400)

    def test_poll_requires_target(self):
        response = self.client.get('/api/poll/', {'after': ''})
        self.assertEqual(response.status_code, 400)

    def test_poll_private_messages_after_cursor(self):
        m1 = Message.objects.create(sender=self.b, receiver=self.a, content='first')
        cursor = m1.created_at.isoformat()
        m2 = Message.objects.create(sender=self.b, receiver=self.a, content='second')

        response = self.client.get('/api/poll/', {'after': cursor, 'user_id': self.b.id})
        data = json.loads(response.content)
        self.assertEqual(data['count'], 1)
        self.assertIn('second', data['html'])
        self.assertNotIn('first', data['html'])
        self.assertEqual(parse_datetime(data['cursor']), m2.created_at)

    def test_poll_group_after_cursor(self):
        group = Group.objects.create(name='PollGroup', owner=self.a)
        GroupMember.objects.create(group=group, user=self.a, role='owner')
        m1 = Message.objects.create(sender=self.a, group=group, content='g1')
        cursor = m1.created_at.isoformat()
        Message.objects.create(sender=self.a, group=group, content='g2')
        m3 = Message.objects.create(sender=self.a, group=group, content='g3')

        response = self.client.get('/api/poll/', {'after': cursor, 'group_id': group.id})
        data = json.loads(response.content)
        self.assertEqual(data['count'], 2)
        self.assertIn('g2', data['html'])
        self.assertIn('g3', data['html'])
        self.assertEqual(parse_datetime(data['cursor']), m3.created_at)

    def test_poll_channel_no_duplicates(self):
        channel = Channel.objects.create(name='PollChannel', owner=self.a)
        ChannelMember.objects.create(channel=channel, user=self.a, role='owner')
        m1 = Message.objects.create(sender=self.a, channel=channel, content='c1')
        cursor = m1.created_at.isoformat()
        m2 = Message.objects.create(sender=self.a, channel=channel, content='c2')

        response = self.client.get('/api/poll/', {'after': cursor, 'channel_id': channel.id})
        data = json.loads(response.content)
        self.assertEqual(data['count'], 1)
        # сверяем по идентификаторам: короткие строки вроде 'c1' встречаются
        # внутри случайных UUID и делают проверку по подстроке флаки
        self.assertIn(str(m2.id), data['html'])
        self.assertNotIn(str(m1.id), data['html'])
        self.assertEqual(parse_datetime(data['cursor']), m2.created_at)

        second = self.client.get('/api/poll/', {'after': data['cursor'], 'channel_id': channel.id})
        self.assertEqual(json.loads(second.content)['count'], 0)

    def _create_posts(self, channel, count):
        """Создаёт посты со строго возрастающими метками времени.

        `bulk_create` может выдать одинаковые `created_at`, а курсор опирается
        на время, поэтому метки задаются явно.
        """
        from datetime import timedelta
        from django.utils import timezone
        base = timezone.now()
        posts = Message.objects.bulk_create([
            Message(sender=self.a, channel=channel, content=f'post {i}')
            for i in range(count)
        ])
        for index, post in enumerate(posts):
            Message.objects.filter(pk=post.pk).update(
                created_at=base + timedelta(seconds=index))
        return posts

    @mock.patch('chat.views.api.POLL_MAX_MESSAGES', 3)
    def test_poll_response_is_capped(self):
        """П-6: опрос без курсора не выгружает весь канал целиком."""
        channel = Channel.objects.create(name='HugeChannel', owner=self.a)
        ChannelMember.objects.create(channel=channel, user=self.a, role='owner')
        self._create_posts(channel, 5)

        response = self.client.get('/api/poll/', {'channel_id': channel.id})
        self.assertEqual(json.loads(response.content)['count'], 3)

    @mock.patch('chat.views.api.POLL_MAX_MESSAGES', 3)
    def test_poll_cursor_advances_without_losing_posts(self):
        """Ограничение не теряет посты: курсор ведёт к следующей порции."""
        channel = Channel.objects.create(name='CursorCap', owner=self.a)
        ChannelMember.objects.create(channel=channel, user=self.a, role='owner')
        self._create_posts(channel, 5)

        first = json.loads(
            self.client.get('/api/poll/', {'channel_id': channel.id}).content)
        self.assertEqual(first['count'], 3)

        second = json.loads(self.client.get(
            '/api/poll/', {'after': first['cursor'], 'channel_id': channel.id}).content)
        self.assertEqual(second['count'], 2)

    def test_poll_channel_posts_are_chronological(self):
        """П-21: посты канала приходят по возрастанию времени."""
        channel = Channel.objects.create(name='Ordered', owner=self.a)
        ChannelMember.objects.create(channel=channel, user=self.a, role='owner')
        self._create_posts(channel, 2)

        response = self.client.get('/api/poll/', {'channel_id': channel.id})
        html = json.loads(response.content)['html']
        self.assertLess(html.index('post 0'), html.index('post 1'))


class AttachmentAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='att_owner', password='123')
        self.subscriber = User.objects.create_user(username='att_sub', password='123')
        self.outsider = User.objects.create_user(username='att_out', password='123')
        self.channel = Channel.objects.create(name='Attach', owner=self.owner)
        ChannelMember.objects.create(channel=self.channel, user=self.owner, role='owner')
        ChannelMember.objects.create(channel=self.channel, user=self.subscriber, role='subscriber')

    def _channel_message_with_file(self):
        file = SimpleUploadedFile('note.txt', b'hello', content_type='text/plain')
        return Message.objects.create(
            sender=self.owner, channel=self.channel, content='file', attachment=file
        )

    def test_subscriber_can_download_channel_attachment(self):
        msg = self._channel_message_with_file()
        self.client.login(username='att_sub', password='123')
        response = self.client.get(reverse('download_attachment', args=[msg.id]))
        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_download_channel_attachment(self):
        msg = self._channel_message_with_file()
        self.client.login(username='att_out', password='123')
        response = self.client.get(reverse('download_attachment', args=[msg.id]))
        self.assertEqual(response.status_code, 302)

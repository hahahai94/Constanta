from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from chat.models import Message, Group, GroupMember
from chat.views.api import _detect_attachment_type, _content_disposition_header
import json, io, os

User = get_user_model()


class APITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api_tester', password='123')
        self.friend = User.objects.create_user(username='api_friend', password='456')
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
        response = self.client.post('/api/send/', {
            'friend_id': '999', 'content': ''
        })
        self.assertNotEqual(response.status_code, 500)

    def test_send_message_no_recipient(self):
        response = self.client.post('/api/send/', {'content': 'hello'})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Нет получателя', data['message'])

    def test_send_private_message(self):
        response = self.client.post('/api/send/', {
            'friend_id': self.friend.id,
            'content': 'Hello friend!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(
            sender=self.user, receiver=self.friend, content='Hello friend!'
        ).exists())

    def test_send_message_too_long(self):
        response = self.client.post('/api/send/', {
            'friend_id': self.friend.id,
            'content': 'x' * (settings.MAX_MESSAGE_LENGTH + 1)
        })
        self.assertEqual(response.status_code, 400)

    def test_send_file_message(self):
        file = SimpleUploadedFile("test.png", io.BytesIO(b'image').read(), content_type="image/png")
        response = self.client.post('/api/send/', {
            'friend_id': self.friend.id,
            'content': 'Check this',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.friend)
        self.assertEqual(msg.attachment_type, 'image')

    def test_send_file_message_audio(self):
        file = SimpleUploadedFile("voice.ogg", io.BytesIO(b'audio').read(), content_type="audio/ogg")
        response = self.client.post('/api/send/', {
            'friend_id': self.friend.id,
            'content': 'Voice message',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.friend)
        self.assertEqual(msg.attachment_type, 'voice')

    def test_send_file_message_other(self):
        file = SimpleUploadedFile("doc.pdf", io.BytesIO(b'pdf').read(), content_type="application/pdf")
        response = self.client.post('/api/send/', {
            'friend_id': self.friend.id,
            'content': 'Document',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.friend)
        self.assertEqual(msg.attachment_type, 'file')

    def test_send_message_get_fails(self):
        response = self.client.get('/api/send/')
        self.assertEqual(response.status_code, 405)

    def test_download_attachment(self):
        file = SimpleUploadedFile("download.txt", b"content", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.user, receiver=self.friend,
            content='With file', attachment=file
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 200)

    def test_download_attachment_no_file(self):
        msg = Message.objects.create(
            sender=self.user, receiver=self.friend,
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
        group = Group.objects.create(name='G', owner=self.friend)
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
            'friend_id': self.friend.id,
            'content': 'big',
            'attachment': file
        })
        self.assertEqual(response.status_code, 400)

    def test_send_message_with_mention(self):
        mentioned = User.objects.create_user(username='mention_target', password='123')
        response = self.client.post('/api/send/', {
            'friend_id': self.friend.id,
            'content': f'Hello @{mentioned.username}'
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.friend)
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
        group = Group.objects.create(name='Private', owner=self.friend)
        response = self.client.post('/api/send/', {
            'group_id': str(group.id),
            'content': 'Hack'
        })
        self.assertEqual(response.status_code, 403)

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
        GroupMember.objects.create(group=group, user=self.friend, role='member')
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        response = self.client.post('/api/add-member/', json.dumps({
            'group_id': str(group.id), 'username': self.friend.username
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_api_set_role_not_owner(self):
        group = Group.objects.create(name='G6', owner=self.friend)
        GroupMember.objects.create(group=group, user=self.friend, role='owner')
        self.client.logout()
        stranger = User.objects.create_user(username='stranger3', password='123')
        self.client.login(username='stranger3', password='123')
        response = self.client.post('/api/set-role/', json.dumps({
            'group_id': str(group.id), 'user_id': self.friend.id, 'role': 'member'
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
        GroupMember.objects.create(group=group, user=self.friend, role='member')
        file = SimpleUploadedFile("group_file.txt", b"shared", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.friend, group=group,
            content='Group file', attachment=file
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 200)

    def test_download_attachment_file_missing(self):
        file = SimpleUploadedFile("temp.txt", b"gone", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.user, receiver=self.friend,
            content='Temporary', attachment=file
        )
        os.remove(msg.attachment.path)
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 404)

    def test_download_attachment_group_member_unauthorized(self):
        group = Group.objects.create(name='Secret', owner=self.friend)
        file = SimpleUploadedFile("secret.txt", b"secret", content_type="text/plain")
        msg = Message.objects.create(
            sender=self.friend, group=group,
            content='Secret file', attachment=file
        )
        response = self.client.get(f'/download/{msg.id}/')
        self.assertEqual(response.status_code, 302)

    def test_api_update_group_with_old_avatar(self):
        file = SimpleUploadedFile("old_av.png", b"old", content_type="image/png")
        group = Group.objects.create(name='Old Av', owner=self.user, avatar=file)
        new_file = SimpleUploadedFile("new_av.png", b"new", content_type="image/png")
        response = self.client.post(f'/groups/{group.id}/settings/', {
            'name': 'New Av',
            'avatar': new_file
        })
        self.assertEqual(response.status_code, 200)

    def test_send_message_mime_image_by_content_type(self):
        file = SimpleUploadedFile("weird.png", b'\x00\x00\x00', content_type="image/png")
        response = self.client.post('/api/send/', {
            'friend_id': self.friend.id,
            'content': 'Detected by content_type',
            'attachment': file
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.friend, content='Detected by content_type')
        self.assertEqual(msg.attachment_type, 'image')

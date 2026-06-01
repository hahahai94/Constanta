from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from chat.models import Message, Group, GroupMember
import json, io

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
        self.assertEqual(response.status_code, 400)

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
            'content': 'x' * 501
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

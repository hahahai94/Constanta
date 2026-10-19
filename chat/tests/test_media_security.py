from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chat.models import Message
from chat.tests.factories import fake_upload, image_upload

User = get_user_model()


class MediaAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='media_owner', password='123')
        self.other = User.objects.create_user(username='media_other', password='456')
        self.client.login(username='media_owner', password='123')

    def test_attachment_is_not_served_from_media_url(self):
        message = Message.objects.create(
            sender=self.user, receiver=self.other, content='file',
            attachment=fake_upload('secret.txt', b'secret', 'text/plain'))

        response = self.client.get(message.attachment.url)
        self.assertEqual(response.status_code, 404)

    def test_attachment_media_url_is_hidden_even_for_owner(self):
        message = Message.objects.create(
            sender=self.user, receiver=self.other, content='file',
            attachment=fake_upload('secret.txt', b'secret', 'text/plain'))

        self.client.logout()
        self.client.login(username='media_owner', password='123')
        self.assertEqual(self.client.get(message.attachment.url).status_code, 404)

    def test_inline_image_has_safe_headers(self):
        message = Message.objects.create(
            sender=self.user, receiver=self.other, content='',
            attachment=image_upload('photo.png'), attachment_type='image')

        response = self.client.get(
            reverse('download_attachment', args=[message.id]), {'inline': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('inline;', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_regular_download_is_an_attachment(self):
        message = Message.objects.create(
            sender=self.user, receiver=self.other, content='',
            attachment=image_upload('photo.png'), attachment_type='image')

        response = self.client.get(reverse('download_attachment', args=[message.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_inline_does_not_apply_to_documents(self):
        message = Message.objects.create(
            sender=self.user, receiver=self.other, content='',
            attachment=fake_upload('note.txt', b'hello', 'text/plain'),
            attachment_type='file')

        response = self.client.get(
            reverse('download_attachment', args=[message.id]), {'inline': '1'})
        self.assertIn('attachment;', response['Content-Disposition'])


class AvatarMediaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='avatar_user', password='123')
        self.user.avatar = image_upload('avatar.png')
        self.user.save()
        self.client.login(username='avatar_user', password='123')

    def test_avatar_is_served_inline_with_nosniff(self):
        response = self.client.get(self.user.avatar.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('inline;', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_avatar_requires_authentication(self):
        self.client.logout()
        response = self.client.get(self.user.avatar.url)
        self.assertEqual(response.status_code, 302)

    def test_non_image_file_in_avatar_directory_is_hidden(self):
        path = Path(settings.MEDIA_ROOT) / 'avatars' / 'payload.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<script>alert(1)</script>', encoding='utf-8')

        response = self.client.get('/media/avatars/payload.txt')
        self.assertEqual(response.status_code, 404)

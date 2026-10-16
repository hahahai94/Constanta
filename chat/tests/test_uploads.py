"""Тесты валидации и нормализации загрузок (problems.md, П-3, П-10)."""

import io

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from chat.models import Channel, ChannelMember, Group, GroupMember, Message
from chat.tests.factories import fake_upload, image_upload, make_png
from chat.utils.uploads import (
    detect_attachment_type,
    normalize_avatar,
    normalize_upload,
    safe_document_extension,
    validate_image_bytes,
)

User = get_user_model()

HTML_PAYLOAD = b'<html><body><script>alert(document.domain)</script></body></html>'


def make_wav_bytes():
    """Минимальный корректный контейнер RIFF/WAVE."""
    data = bytearray()
    data += b'RIFF' + (36).to_bytes(4, 'little') + b'WAVE'
    data += b'fmt ' + (16).to_bytes(4, 'little')
    data += (1).to_bytes(2, 'little') + (1).to_bytes(2, 'little')
    data += (8000).to_bytes(4, 'little') + (8000).to_bytes(4, 'little')
    data += (1).to_bytes(2, 'little') + (8).to_bytes(2, 'little')
    data += b'data' + (0).to_bytes(4, 'little')
    return bytes(data)


def make_webp_bytes():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (2, 2), (0, 255, 0)).save(buffer, format='WEBP')
    return buffer.getvalue()


class MediaIsolationTests(TestCase):
    """П-14: тесты не должны писать в реальный `media/` проекта."""

    def test_media_root_points_to_a_temporary_directory(self):
        self.assertIn('constanta-test-media-', str(settings.MEDIA_ROOT))
        self.assertNotEqual(
            str(settings.MEDIA_ROOT), str(settings.BASE_DIR / 'media'))

    def test_upload_lands_outside_the_project(self):
        user = User.objects.create_user(username='media_user', password='123')
        other = User.objects.create_user(username='media_other', password='456')
        self.client.login(username='media_user', password='123')

        response = self.client.post('/api/send/', {
            'user_id': other.id,
            'content': 'файл',
            'attachment': fake_upload('note.txt', b'hello', 'text/plain'),
        })
        self.assertEqual(response.status_code, 200)

        message = Message.objects.get(sender=user, receiver=other)
        self.assertIn('constanta-test-media-', message.attachment.path)
        self.assertNotIn(str(settings.BASE_DIR / 'media'), message.attachment.path)


class DetectAttachmentTypeTests(TestCase):
    """RIFF-контейнеры различаются по содержимому, а не по первым 4 байтам."""

    def test_wav_is_voice_not_image(self):
        # Регрессия П-10: раньше b'RIFF' означал image/webp и WAV отклонялся.
        self.assertEqual(detect_attachment_type(make_wav_bytes(), 'audio/wav'), 'voice')

    def test_webp_is_image(self):
        self.assertEqual(detect_attachment_type(make_webp_bytes(), ''), 'image')

    def test_unknown_riff_is_file(self):
        data = b'RIFF' + (0).to_bytes(4, 'little') + b'AVI ' + b'\x00' * 16
        self.assertEqual(detect_attachment_type(data, ''), 'file')

    def test_png_by_magic_bytes_without_content_type(self):
        self.assertEqual(detect_attachment_type(make_png(), ''), 'image')

    def test_garbage_is_file(self):
        self.assertEqual(detect_attachment_type(b'\x00\x00\x00', ''), 'file')


class SafeExtensionTests(TestCase):
    def test_executable_extensions_are_neutralised(self):
        for name in ('evil.html', 'evil.htm', 'evil.xhtml', 'evil.svg',
                     'evil.js', 'evil.xml', 'evil.php'):
            with self.subTest(name=name):
                self.assertEqual(safe_document_extension(name), '.bin')

    def test_document_extensions_are_kept(self):
        for name, expected in (('doc.pdf', '.pdf'), ('doc.docx', '.docx'),
                               ('arch.zip', '.zip'), ('song.mp3', '.mp3')):
            with self.subTest(name=name):
                self.assertEqual(safe_document_extension(name), expected)

    def test_missing_extension_falls_back(self):
        self.assertEqual(safe_document_extension('noext'), '.bin')
        self.assertEqual(safe_document_extension(''), '.bin')


class NormalizeUploadTests(TestCase):
    def test_html_file_never_keeps_html_extension(self):
        attachment = SimpleUploadedFile('evil.html', HTML_PAYLOAD,
                                        content_type='text/html')
        attachment_type, extension = normalize_upload(attachment)
        self.assertEqual(attachment_type, 'file')
        self.assertEqual(extension, '.bin')

    def test_png_named_html_gets_png_extension(self):
        attachment = SimpleUploadedFile('evil.html', make_png(),
                                        content_type='text/html')
        attachment_type, extension = normalize_upload(attachment)
        self.assertEqual(attachment_type, 'image')
        self.assertEqual(extension, '.png')

    def test_html_content_claimed_as_image_is_rejected(self):
        attachment = SimpleUploadedFile('evil.png', HTML_PAYLOAD,
                                        content_type='image/png')
        with self.assertRaises(ValidationError):
            normalize_upload(attachment)

    def test_wav_upload_is_accepted_as_voice(self):
        attachment = SimpleUploadedFile('voice.wav', make_wav_bytes(),
                                        content_type='audio/wav')
        attachment_type, extension = normalize_upload(attachment)
        self.assertEqual(attachment_type, 'voice')
        self.assertEqual(extension, '.wav')


class ValidateImageBytesTests(TestCase):
    def test_garbage_rejected(self):
        with self.assertRaises(ValidationError):
            validate_image_bytes(b'not an image at all')

    def test_valid_png_accepted(self):
        image_format, width, height = validate_image_bytes(make_png())
        self.assertEqual(image_format, 'PNG')
        self.assertEqual((width, height), (2, 2))

    def test_too_many_pixels_rejected(self):
        with self.assertRaises(ValidationError):
            validate_image_bytes(make_png(size=(10, 10)), max_pixels=1)


class NormalizeAvatarTests(TestCase):
    def test_html_avatar_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_avatar(SimpleUploadedFile('x.png', HTML_PAYLOAD,
                                                content_type='image/png'))

    def test_valid_avatar_name_is_rewritten(self):
        avatar = SimpleUploadedFile('evil.html', make_png(), content_type='image/png')
        original = normalize_avatar(avatar)
        self.assertEqual(original, 'evil.html')
        self.assertEqual(avatar.name, 'avatar.png')


class AvatarStorageTests(TestCase):
    """`upload_to` не должен сохранять исполняемое расширение."""

    def setUp(self):
        self.owner = User.objects.create_user(username='avatar_owner', password='123')

    def test_group_avatar_with_html_content_is_not_stored_as_html(self):
        group = Group.objects.create(
            name='XSS', owner=self.owner,
            avatar=SimpleUploadedFile('poc.html', HTML_PAYLOAD, content_type='text/html'),
        )
        self.assertFalse(group.avatar.name.endswith('.html'))
        self.assertTrue(group.avatar.name.endswith('.bin'))

    def test_group_avatar_with_real_image_gets_real_extension(self):
        group = Group.objects.create(
            name='Ok', owner=self.owner,
            avatar=SimpleUploadedFile('poc.html', make_png(), content_type='text/html'),
        )
        self.assertTrue(group.avatar.name.endswith('.png'))


class GroupAvatarValidationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='g_owner', password='123')
        self.group = Group.objects.create(name='G', owner=self.owner)
        GroupMember.objects.create(group=self.group, user=self.owner, role='owner')
        self.client.login(username='g_owner', password='123')

    def test_api_rejects_html_avatar(self):
        response = self.client.post(f'/groups/{self.group.id}/settings/', {
            'name': 'G', 'avatar': fake_upload('poc.html', HTML_PAYLOAD, 'text/html'),
        })
        self.assertEqual(response.status_code, 400)
        self.group.refresh_from_db()
        self.assertFalse(self.group.avatar)

    def test_api_keeps_old_avatar_when_new_one_is_invalid(self):
        self.group.avatar = image_upload('good.png')
        self.group.save()
        response = self.client.post(f'/groups/{self.group.id}/settings/', {
            'name': 'G', 'avatar': fake_upload('poc.html', HTML_PAYLOAD, 'text/html'),
        })
        self.assertEqual(response.status_code, 400)
        self.group.refresh_from_db()
        self.assertTrue(self.group.avatar)
        self.assertTrue(self.group.avatar.name.endswith('.png'))

    def test_edit_group_rejects_html_avatar(self):
        response = self.client.post(reverse('edit_group', args=[self.group.id]), {
            'name': 'Renamed', 'avatar': fake_upload('poc.html', HTML_PAYLOAD, 'text/html'),
        })
        self.assertEqual(response.status_code, 302)
        self.group.refresh_from_db()
        self.assertFalse(self.group.avatar)
        # изменение не применяется, чтобы не оставлять частичное обновление
        self.assertEqual(self.group.name, 'G')


class ChannelAvatarValidationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='c_owner', password='123')
        self.channel = Channel.objects.create(name='C', owner=self.owner)
        ChannelMember.objects.create(channel=self.channel, user=self.owner, role='owner')
        self.client.login(username='c_owner', password='123')

    def test_edit_channel_rejects_html_avatar(self):
        response = self.client.post(reverse('edit_channel', args=[self.channel.id]), {
            'name': 'C', 'avatar': fake_upload('poc.html', HTML_PAYLOAD, 'text/html'),
        })
        self.assertEqual(response.status_code, 302)
        self.channel.refresh_from_db()
        self.assertFalse(self.channel.avatar)

    def test_edit_channel_accepts_real_image(self):
        response = self.client.post(reverse('edit_channel', args=[self.channel.id]), {
            'name': 'C2', 'avatar': image_upload('good.png'),
        })
        self.assertEqual(response.status_code, 302)
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.avatar)
        self.assertTrue(self.channel.avatar.name.endswith('.png'))
        self.assertEqual(self.channel.name, 'C2')


class AttachmentStorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='att_user', password='123')
        self.other = User.objects.create_user(username='att_other', password='456')
        self.client.login(username='att_user', password='123')

    def test_html_attachment_is_not_stored_as_html(self):
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'file',
            'attachment': fake_upload('evil.html', HTML_PAYLOAD, 'text/html'),
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertFalse(msg.attachment.name.endswith('.html'))
        self.assertTrue(msg.attachment.name.endswith('.bin'))

    def test_original_name_is_preserved_for_download(self):
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'file',
            'attachment': fake_upload('report.pdf', b'%PDF-1.4', 'application/pdf'),
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertEqual(msg.attachment_original_name, 'report.pdf')
        self.assertTrue(msg.attachment.name.endswith('.pdf'))

    def test_wav_voice_message_is_accepted(self):
        # Регрессия П-10: раньше WAV отклонялся как «не валидное изображение».
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'voice',
            'attachment': SimpleUploadedFile('voice.wav', make_wav_bytes(),
                                             content_type='audio/wav'),
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertEqual(msg.attachment_type, 'voice')
        self.assertTrue(msg.attachment.name.endswith('.wav'))

    def test_png_named_html_is_stored_as_png(self):
        response = self.client.post('/api/send/', {
            'user_id': self.other.id,
            'content': 'image',
            'attachment': fake_upload('evil.html', make_png(), 'text/html'),
        })
        self.assertEqual(response.status_code, 200)
        msg = Message.objects.get(sender=self.user, receiver=self.other)
        self.assertEqual(msg.attachment_type, 'image')
        self.assertTrue(msg.attachment.name.endswith('.png'))

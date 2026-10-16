"""Проверки интерфейса чата.

Покрывают четыре изменения: переписка отдаётся целиком и прокручивается к
последнему сообщению, в списке чатов под ником появляется описание вложения,
изображения открываются в полный экран и скачиваются, а превью в списке
обновляется без перезагрузки страницы.
"""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from chat.models import Group, GroupMember, Message
from chat.tests.factories import fake_upload, image_upload

User = get_user_model()


class MessagePreviewTextTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username='prev_sender', password='123')
        self.receiver = User.objects.create_user(username='prev_receiver', password='456')

    def _message(self, **kwargs):
        return Message.objects.create(
            sender=self.sender, receiver=self.receiver, **kwargs)

    def test_text(self):
        self.assertEqual(self._message(content='привет').preview_text, 'привет')

    def test_image(self):
        message = self._message(
            attachment=image_upload('photo.png'), attachment_type='image')
        self.assertEqual(message.preview_text, '📷 Фото')

    def test_voice(self):
        message = self._message(
            attachment=fake_upload('voice.ogg', b'OggSdata', 'audio/ogg'),
            attachment_type='voice')
        self.assertEqual(message.preview_text, '🎤 Голосовое сообщение')

    def test_file_keeps_the_original_name(self):
        message = self._message(
            attachment=fake_upload('doc.pdf', b'%PDF-1.4', 'application/pdf'),
            attachment_type='file')
        self.assertEqual(message.preview_text, '📎 doc.pdf')

    def test_without_content_or_attachment(self):
        self.assertEqual(self._message(content='').preview_text, '')


class WholeConversationTests(TestCase):
    """Переписка показывается целиком, кнопки «Загрузить ещё» больше нет."""

    def setUp(self):
        self.user = User.objects.create_user(username='whole_user', password='123')
        self.peer = User.objects.create_user(username='whole_peer', password='456')
        self.client.login(username='whole_user', password='123')

    def test_all_private_messages_are_rendered(self):
        for index in range(35):
            Message.objects.create(
                sender=self.peer, receiver=self.user, content=f'сообщение {index}')

        response = self.client.get(reverse('main'), {'user_id': self.peer.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['messages']), 35)
        self.assertContains(response, 'сообщение 34')
        self.assertNotContains(response, 'Загрузить ещё')

    def test_all_group_messages_are_rendered(self):
        group = Group.objects.create(name='WholeGroup', owner=self.user)
        GroupMember.objects.create(group=group, user=self.user, role='owner')
        for index in range(35):
            Message.objects.create(sender=self.user, group=group, content=f'группа {index}')

        response = self.client.get(reverse('group_chat', args=[group.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['messages']), 35)
        self.assertNotContains(response, 'Загрузить ещё')

    def test_sidebar_shows_attachment_placeholder(self):
        Message.objects.create(
            sender=self.peer, receiver=self.user,
            attachment=image_upload('photo.png'), attachment_type='image')

        response = self.client.get(reverse('main'), {'user_id': self.peer.id})
        self.assertContains(response, '📷 Фото')


class MobileLayoutTests(TestCase):
    """Мобильная вёрстка: панель уезжает в выдвижной ящик.

    В `style.css` правила для неё были написаны с самого начала, но шаблоны
    использовали свои классы и жёсткую ширину, поэтому на телефоне чатом было
    пользоваться нельзя.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='mobile_user', password='123')
        self.peer = User.objects.create_user(username='mobile_peer', password='456')
        self.client.login(username='mobile_user', password='123')

    def test_private_chat_has_drawer_markup(self):
        response = self.client.get(reverse('main'), {'user_id': self.peer.id})
        self.assertContains(response, 'class="sidebar"')
        self.assertContains(response, 'id="sidebar-overlay"')
        self.assertContains(response, 'id="mobile-menu-btn"')
        self.assertContains(response, 'class="chat-wrapper"')

    def test_group_chat_has_drawer_markup(self):
        group = Group.objects.create(name='MobileGroup', owner=self.user)
        GroupMember.objects.create(group=group, user=self.user, role='owner')

        response = self.client.get(reverse('group_chat', args=[group.id]))
        self.assertContains(response, 'class="sidebar"')
        self.assertContains(response, 'id="sidebar-overlay"')
        self.assertContains(response, 'id="mobile-menu-btn"')
        self.assertContains(response, 'class="chat-wrapper"')

    def test_no_hardcoded_sidebar_width(self):
        """Ширина задаётся классом, иначе мобильные правила не применяются."""
        response = self.client.get(reverse('main'), {'user_id': self.peer.id})
        self.assertNotContains(response, 'width: 350px')

    def test_stylesheet_has_mobile_breakpoint(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'style.css').read_text(
            encoding='utf-8')
        self.assertIn('@media (max-width: 768px)', css)
        self.assertIn('.sidebar.show', css)
        self.assertIn('.sidebar-overlay.show', css)


class ImageViewerTests(TestCase):
    """П-…: изображение открывается в полный экран и скачивается."""

    def setUp(self):
        self.user = User.objects.create_user(username='viewer_user', password='123')
        self.peer = User.objects.create_user(username='viewer_peer', password='456')
        self.client.login(username='viewer_user', password='123')
        self.message = Message.objects.create(
            sender=self.peer, receiver=self.user,
            attachment=image_upload('photo.png'), attachment_type='image')

    def test_image_has_viewer_and_download_attributes(self):
        response = self.client.get(reverse('main'), {'user_id': self.peer.id})
        self.assertContains(response, 'data-image-viewer')
        self.assertContains(
            response,
            f'data-image-download="{reverse("download_attachment", args=[self.message.id])}"',
        )
        self.assertContains(response, 'data-image-name="photo.png"')

    def test_viewer_overlay_exists_on_every_page(self):
        for url in ('/auth/', reverse('profile')):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'id="image-viewer"')

    def test_download_endpoint_serves_the_file_as_attachment(self):
        response = self.client.get(
            reverse('download_attachment', args=[self.message.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])


class SendResponsePreviewTests(TestCase):
    """Превью для списка чатов приходит вместе с ответом на отправку."""

    def setUp(self):
        # счётчик rate-limit общий для процесса: сбрасываем, чтобы тесты
        # не зависели от порядка выполнения
        cache.clear()
        self.sender = User.objects.create_user(username='send_prev_a', password='123')
        self.receiver = User.objects.create_user(username='send_prev_b', password='456')
        self.client.login(username='send_prev_a', password='123')

    def test_send_returns_preview_and_peer_id(self):
        response = self.client.post('/api/send/', {
            'user_id': self.receiver.id, 'content': 'текст для превью',
        })
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['preview'], 'текст для превью')
        self.assertEqual(data['peer_id'], self.receiver.id)

    def test_send_image_returns_placeholder_preview(self):
        response = self.client.post('/api/send/', {
            'user_id': self.receiver.id, 'content': '',
            'attachment': image_upload('photo.png'),
        })
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['preview'], '📷 Фото')

    def test_poll_returns_preview_and_peer_id(self):
        Message.objects.create(
            sender=self.receiver, receiver=self.sender, content='входящее')
        response = self.client.get('/api/poll/', {'user_id': self.receiver.id})
        data = json.loads(response.content)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['preview'], 'входящее')
        self.assertEqual(data['peer_id'], self.receiver.id)

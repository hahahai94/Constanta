from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from chat.models import Message

User = get_user_model()
import io


class PrivateChatTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='alice', password='123')
        self.user2 = User.objects.create_user(username='bob', password='123')
        self.client.login(username='alice', password='123')

    def test_send_text_message(self):
        """Тест: Отправка текстового сообщения через API"""
        response = self.client.post('/api/send/', {
            'friend_id': self.user2.id,
            'content': 'Привет, Боб!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'ok'})

        # Проверка БД
        msg = Message.objects.get(sender=self.user1, receiver=self.user2)
        self.assertEqual(msg.content, 'Привет, Боб!')

    def test_send_file_message(self):
        """Тест: Отправка сообщения с файлом (картинкой)"""
        file_content = io.BytesIO(b'fake image content')
        uploaded_file = SimpleUploadedFile("test.png", file_content.read(), content_type="image/png")

        response = self.client.post('/api/send/', {
            'friend_id': self.user2.id,
            'content': 'Смотри фотку',
            'attachment': uploaded_file
        })

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'ok'})

        msg = Message.objects.get(sender=self.user1, receiver=self.user2)
        self.assertTrue(msg.attachment)
        self.assertEqual(msg.attachment_type, 'image')

    def test_view_chat_page(self):
        """Тест: Страница чата грузится (200)"""
        response = self.client.get(f'/?friend_id={self.user2.id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user2.username)
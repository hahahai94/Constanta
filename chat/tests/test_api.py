from django.test import TestCase
from django.urls import reverse
from chat.models import User

class APITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api_tester', password='123')

    def test_heartbeat_auth(self):
        """Тест: Heartbeat от авторизованного юзера (обновляет last_seen)"""
        self.client.login(username='api_tester', password='123')
        response = self.client.post('/api/heartbeat/')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'ok'})

    def test_heartbeat_anonymous(self):
        """Тест: Heartbeat от анонима (должен быть forbidden)"""
        response = self.client.post('/api/heartbeat/')
        self.assertIn(response.status_code, [302, 403])

    def test_send_empty_message(self):
        """Тест: Отправка пустого сообщения (валидация)"""
        self.client.login(username='api_tester', password='123')
        response = self.client.post('/api/send/', {
            'friend_id': '999', # Несуществующий ID
            'content': ''
        })
        # Django обычно возвращает 400 или 200 с ошибкой, но не падает 500
        self.assertNotEqual(response.status_code, 500)
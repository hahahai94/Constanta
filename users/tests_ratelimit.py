"""Тесты ограничения частоты запросов (problems.md, П-6 и П-7).

Прежняя схема обнуляла счётчик при успехе, поэтому подбор пароля был
бесконечным: четыре неверных попытки плюс регистрация с того же адреса
сбрасывали лимит. Кроме того, `api_poll` (GET) не ограничивался вовсе, а
ключ включал путь с UUID ресурса, из-за чего лимит обходился созданием
новых групп и каналов.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='ratelimited', password='correct123',
        )

    def _fail_login(self, username='ratelimited'):
        return self.client.post('/auth/', {'username': username, 'password': 'wrong'})

    def _register(self, username):
        return self.client.post('/auth/', {
            'username': username,
            'password1': 'newpass123',
            'password2': 'newpass123',
            'register': '1',
        })

    def test_registration_does_not_reset_login_counter(self):
        """П-7: регистрация не обнуляет счётчик подбора пароля."""
        for _ in range(4):
            self._fail_login()

        self.assertEqual(self._register('fresh_account').status_code, 302)

        self._fail_login()               # пятая неудача ещё укладывается в лимит
        blocked = self._fail_login()     # шестая должна быть отклонена
        self.assertContains(blocked, 'много попыток')

    def test_ip_ceiling_survives_successful_login(self):
        """П-7: успешный вход не обнуляет счётчик по IP."""
        for _ in range(3):
            self._fail_login()

        ip_key = 'ratelimit:login_ip:127.0.0.1'
        self.assertEqual(cache.get(ip_key), 3)

        response = self.client.post('/auth/', {
            'username': 'ratelimited', 'password': 'correct123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(cache.get(ip_key), 3)

    def test_successful_login_clears_own_account_counter(self):
        """Счётчик аккаунта сбрасывается только доказанным паролем."""
        for _ in range(3):
            self._fail_login()
        self.assertEqual(cache.get('ratelimit:login_user:ratelimited'), 3)

        self.client.post('/auth/', {
            'username': 'ratelimited', 'password': 'correct123',
        })
        self.assertIsNone(cache.get('ratelimit:login_user:ratelimited'))

    def test_registration_is_limited_per_ip(self):
        """П-6: у регистрации отдельный лимит по адресу."""
        for index in range(5):
            self.assertEqual(self._register(f'bulk_user_{index}').status_code, 302)

        blocked = self._register('bulk_user_final')
        self.assertContains(blocked, 'попыток регистрации')
        self.assertFalse(User.objects.filter(username='bulk_user_final').exists())

    def test_successful_login_is_not_counted(self):
        """Лимит считает только неудачные попытки."""
        for _ in range(6):
            response = self.client.post('/auth/', {
                'username': 'ratelimited', 'password': 'correct123',
            })
            self.assertEqual(response.status_code, 302)
            cache.clear()


class HtmlFormRateLimitTests(TestCase):
    """П-6: лимитеры появились и на обычных формах, а не только в API."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='form_user', password='pass123',
        )
        self.client.login(username='form_user', password='pass123')

    def test_change_username_returns_429_after_limit(self):
        for _ in range(5):
            response = self.client.post(reverse('change_username'), {
                'username': 'form_user',
            })
            self.assertEqual(response.status_code, 302)

        response = self.client.post(reverse('change_username'), {'username': 'form_user'})
        self.assertEqual(response.status_code, 429)

    def test_change_password_returns_429_after_limit(self):
        for _ in range(5):
            self.client.post(reverse('change_password'), {
                'old_password': 'pass123',
                'new_password1': 'newpass456',
                'new_password2': 'newpass456',
            })
        response = self.client.post(reverse('change_password'), {
            'old_password': 'pass123',
            'new_password1': 'newpass456',
            'new_password2': 'newpass456',
        })
        self.assertEqual(response.status_code, 429)

    def test_profile_update_returns_429_after_limit(self):
        for _ in range(20):
            self.client.post(reverse('profile'), {'nick': 'nick'})
        response = self.client.post(reverse('profile'), {'nick': 'nick'})
        self.assertEqual(response.status_code, 429)

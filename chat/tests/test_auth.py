from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthAndProfileTests(TestCase):
    def setUp(self):
        """Создаём пользователя для тестов"""
        self.user = User.objects.create_user(
            username='tester',
            password='securepassword123',
            email='test@example.com'
        )
        self.client.login(username='tester', password='securepassword123')

    def test_login_success(self):
        """Тест: Вход с верным паролем (редирект 302)"""
        response = self.client.post('/auth/', {
            'username': 'tester',
            'password': 'securepassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('main'))

    def test_login_fail_wrong_pass(self):
        """Тест: Вход с НЕВЕРНЫМ паролем (возврат формы 200)"""
        response = self.client.post('/auth/', {
            'username': 'tester',
            'password': 'WRONG_PASSWORD'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '❌ Неверный логин или пароль')

    def test_registration_success(self):
        """Тест: Регистрация нового юзера"""
        response = self.client.post('/auth/', {
            'username': 'new_guy',
            'password1': 'newpass123',
            'password2': 'newpass123',
            'register': '1' # Флаг регистрации
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='new_guy').exists())

    def test_logout(self):
        """Тест: Выход из аккаунта"""
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        # После редиректа пользователь должен быть анонимным
        final_response = self.client.get(response.url)
        self.assertFalse(final_response.context['user'].is_authenticated)

    def test_change_username(self):
        """Тест: Смена логина в профиле"""
        response = self.client.post(reverse('change_username'), {
            'username': 'super_tester'
        })
        self.assertEqual(response.status_code, 302) # Редирект на профиль
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'super_tester')

    def test_change_password(self):
        """Тест: Смена пароля"""
        response = self.client.post(reverse('change_password'), {
            'old_password': 'securepassword123',
            'new_password1': 'newpass456',
            'new_password2': 'newpass456'
        })
        self.assertEqual(response.status_code, 302)
        # Проверяем, что старый пароль больше не работает
        login_check = self.client.login(username='tester', password='securepassword123')
        self.assertFalse(login_check)
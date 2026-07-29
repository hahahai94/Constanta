from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from users.models import BannedIP, AdminLog, Notification
from users.forms import RegistrationForm, ChangeUsernameForm, ProfileForm, ChangePasswordForm
from users.backends import CustomAuthBackend
from users.middleware import IPBanMiddleware
from users.views import auth_view, logout_view, profile_view, users_catalog, change_username, change_password, password_done
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='pass123', email='test@example.com'
        )

    def test_user_str(self):
        self.assertEqual(str(self.user), 'testuser')

    def test_user_str_with_nick(self):
        self.user.nick = 'tester'
        self.assertEqual(str(self.user), 'tester')

    def test_get_display_name(self):
        self.assertEqual(self.user.get_display_name(), 'testuser')

    def test_get_display_name_with_nick(self):
        self.user.nick = 'tester'
        self.assertEqual(self.user.get_display_name(), 'tester')

    def test_get_avatar_url_default(self):
        self.assertEqual(self.user.get_avatar_url(), '/static/default_avatar.png')

    def test_banned_ip(self):
        banned = BannedIP.objects.create(ip_address='10.0.0.1', reason='spam')
        self.assertEqual(str(banned), 'IP: 10.0.0.1')

    def test_admin_log(self):
        admin_user = User.objects.create_superuser(username='admin1', password='admin123')
        log = AdminLog.objects.create(
            admin=admin_user, action='ban_user',
            description='test ban', target_user=self.user
        )
        self.assertIn('ban_user', str(log))

    def test_notification_creation(self):
        notification = Notification.objects.create(
            user=self.user, notification_type='message',
            title='New message', message='Hello!'
        )
        self.assertEqual(notification.get_icon(), '💬')

    def test_user_banned_by(self):
        admin_user = User.objects.create_superuser(username='admin2', password='admin123')
        self.user.banned_by = admin_user
        self.user.save()
        self.assertEqual(self.user.banned_by, admin_user)

    def test_user_is_online(self):
        self.user.last_seen = timezone.now() - timedelta(minutes=1)
        self.assertTrue(self.user.is_online)

    def test_user_is_offline(self):
        self.user.last_seen = timezone.now() - timedelta(minutes=5)
        self.assertFalse(self.user.is_online)

    def test_get_avatar_url_with_avatar(self):
        file = SimpleUploadedFile("avatar.png", b"x", content_type="image/png")
        self.user.avatar = file
        self.user.save()
        self.assertTrue(self.user.get_avatar_url().startswith('/media/'))

    def test_notification_str(self):
        notification = Notification.objects.create(
            user=self.user, notification_type='mention',
            title='Test', message='Hello'
        )
        self.assertIn('mention', str(notification))


class CustomAuthBackendTests(TestCase):
    def setUp(self):
        self.backend = CustomAuthBackend()

    def test_user_can_authenticate_active(self):
        user = User(username='activeuser')
        self.assertTrue(self.backend.user_can_authenticate(user))

    def test_user_can_authenticate_inactive(self):
        user = User(username='inactive', is_active=False)
        self.assertFalse(self.backend.user_can_authenticate(user))

    def test_authenticate_inactive_user_returns_none(self):
        User.objects.create_user(username='inactive_user', password='pass123', is_active=False)
        user = self.backend.authenticate(request=None, username='inactive_user', password='pass123')
        self.assertIsNone(user)

    def test_login_view_rejects_inactive_user(self):
        User.objects.create_user(username='disabled', password='pass123', is_active=False)
        from django.core.cache import cache
        cache.clear()
        response = self.client.post('/auth/', {'username': 'disabled', 'password': 'pass123'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'правильные имя пользователя и пароль')


class IPBanMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_middleware_allows_local_in_debug(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertIsNone(response)

    @override_settings(DEBUG=False)
    def test_middleware_bans_ip(self):
        BannedIP.objects.create(ip_address='10.0.0.99', reason='test')
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.99'
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False)
    def test_middleware_allows_clean_ip(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertIsNone(response)

    @override_settings(DEBUG=False)
    def test_middleware_x_forwarded_for(self):
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.99, 10.0.0.1'
        BannedIP.objects.create(ip_address='10.0.0.99', reason='proxy')
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertEqual(response.status_code, 403)

    def test_middleware_banned_ip_in_debug(self):
        BannedIP.objects.create(ip_address='10.0.0.88', reason='test')
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.88'
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertEqual(response.status_code, 403)


class RegistrationFormTests(TestCase):
    def test_valid_registration_form(self):
        form = RegistrationForm(data={
            'username': 'newuser',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
        })
        self.assertTrue(form.is_valid())

    def test_password_mismatch(self):
        form = RegistrationForm(data={
            'username': 'newuser',
            'password1': 'validpassword123',
            'password2': 'different',
        })
        self.assertFalse(form.is_valid())


class ChangeUsernameFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='existing', password='pass123')

    def test_change_username_already_taken(self):
        User.objects.create_user(username='taken', password='pass123')
        form = ChangeUsernameForm(data={'username': 'taken'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('занят', str(form.errors))


class AuthViewTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        User.objects.create_user(username='loginuser', password='pass123')

    def test_login_get(self):
        response = self.client.get('/auth/')
        self.assertEqual(response.status_code, 200)

    def test_login_post_success(self):
        response = self.client.post('/auth/', {
            'username': 'loginuser', 'password': 'pass123'
        })
        self.assertEqual(response.status_code, 302)

    def test_login_post_fail(self):
        response = self.client.post('/auth/', {
            'username': 'loginuser', 'password': 'wrong'
        })
        self.assertEqual(response.status_code, 200)

    def test_registration_post_success(self):
        response = self.client.post('/auth/', {
            'username': 'registeruser', 'password1': 'strongpassword123',
            'password2': 'strongpassword123', 'register': '1'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='registeruser').exists())

    def test_logout(self):
        self.client.login(username='loginuser', password='pass123')
        response = self.client.get('/logout/')
        self.assertEqual(response.status_code, 302)

    def test_registration_mode(self):
        response = self.client.get('/auth/?mode=reg')
        self.assertEqual(response.status_code, 200)

    def test_registration_invalid(self):
        response = self.client.post('/auth/?mode=reg', {
            'username': '', 'password1': '123',
            'password2': '123', 'register': '1'
        })
        self.assertEqual(response.status_code, 200)


class RateLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_rate_limit_blocked(self):
        for _ in range(5):
            self.client.post('/auth/', {
                'username': 'nobody', 'password': 'wrong'
            })
        response = self.client.post('/auth/', {
            'username': 'nobody', 'password': 'wrong'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'много попыток')


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='profileuser', password='pass123'
        )
        self.client.login(username='profileuser', password='pass123')

    def test_profile_get(self):
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

    def test_profile_update_nick(self):
        response = self.client.post('/profile/', {'nick': 'newnick'})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nick, 'newnick')

    def test_profile_update_email(self):
        response = self.client.post('/profile/', {'email': 'new@test.com'})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@test.com')

    def test_profile_form_errors(self):
        other = User.objects.create_user(username='nick_taken', password='pass123', nick='taken')
        response = self.client.post('/profile/', {'nick': 'taken'})
        self.assertEqual(response.status_code, 302)

    def test_change_username(self):
        response = self.client.post('/profile/change-username/', {
            'username': 'changedname'
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'changedname')

    def test_change_username_get(self):
        response = self.client.get('/profile/change-username/')
        self.assertEqual(response.status_code, 200)

    def test_change_password_get(self):
        response = self.client.get('/profile/change-password/')
        self.assertEqual(response.status_code, 200)

    def test_password_done(self):
        response = self.client.get('/profile/password-done/')
        self.assertEqual(response.status_code, 200)

    def test_users_catalog(self):
        User.objects.create_user(username='otheruser', password='pass456')
        response = self.client.get('/users/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'otheruser')

    def test_users_catalog_search(self):
        User.objects.create_user(username='zzz_findme', password='pass456')
        response = self.client.get('/users/?q=findme')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'zzz_findme')

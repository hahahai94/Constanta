from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from users.models import BannedIP, Friendship, AdminLog, Notification
from users.forms import RegistrationForm, ChangeUsernameForm, ProfileForm
from users.backends import CustomAuthBackend
from users.middleware import IPBanMiddleware
from users.views import auth_view, logout_view, profile_view, users_catalog, change_username

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

    def test_friendship_creation(self):
        friend = User.objects.create_user(username='friend1', password='pass456')
        friendship = Friendship.objects.create(user=self.user, friend=friend)
        self.assertEqual(str(friendship), 'testuser -> friend1')

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


class CustomAuthBackendTests(TestCase):
    def test_user_can_authenticate_always(self):
        backend = CustomAuthBackend()
        user = User(username='anyuser')
        self.assertTrue(backend.user_can_authenticate(user))


class IPBanMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_middleware_allows_local_in_debug(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertIsNone(response)


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


class AuthViewTests(TestCase):
    def setUp(self):
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

    def test_change_username(self):
        response = self.client.post('/profile/change-username/', {
            'username': 'changedname'
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'changedname')

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

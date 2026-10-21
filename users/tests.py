from pathlib import Path

from django.conf import settings
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from chat.tests.factories import fake_upload, image_upload
from users.models import BannedIP, AdminLog, Notification
from users.forms import RegistrationForm, ChangeUsernameForm, ProfileForm, ChangePasswordForm
from users.backends import CustomAuthBackend
from users.middleware import IPBanMiddleware
from users.presence import format_last_seen
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


class LastSeenFormattingTests(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def test_never_seen(self):
        self.assertEqual(format_last_seen(None), 'давно')

    def test_less_than_a_minute(self):
        self.assertEqual(self._format(seconds=30), 'меньше минуты')

    def test_minutes_use_plural_forms(self):
        cases = (
            (1, '1 минута'),
            (3, '3 минуты'),
            (5, '5 минут'),
            (11, '11 минут'),
            (21, '21 минута'),
        )
        for minutes, expected in cases:
            with self.subTest(minutes=minutes):
                self.assertEqual(self._format(minutes=minutes), expected)

    def test_hours_and_days(self):
        self.assertEqual(self._format(hours=2), '2 часа')
        self.assertEqual(self._format(days=3), '3 дня')
        self.assertEqual(self._format(days=19), '19 дней')

    def test_months_and_years(self):
        self.assertEqual(self._format(days=40), '1 месяц')
        self.assertEqual(self._format(days=800), '2 года')
        self.assertEqual(self._format(days=1900), '5 лет')

    def test_future_timestamp_does_not_go_negative(self):
        self.assertEqual(
            format_last_seen(self.now + timedelta(minutes=1), now=self.now),
            'меньше минуты',
        )

    def _format(self, **delta):
        return format_last_seen(self.now - timedelta(**delta), now=self.now)


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
        from django.core.cache import cache
        # кеш списка банов не откатывается вместе с транзакцией теста
        cache.clear()
        self.factory = RequestFactory()

    @override_settings(DEBUG=True)
    def test_middleware_allows_banned_local_ip_in_debug(self):
        """П-41: проверка осмысленна только если адрес действительно забанен."""
        BannedIP.objects.create(ip_address='127.0.0.1', reason='local')
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertIsNone(response)

    @override_settings(DEBUG=False)
    def test_middleware_bans_local_ip_when_debug_is_off(self):
        """То же исключение не должно работать вне DEBUG."""
        BannedIP.objects.create(ip_address='127.0.0.1', reason='local')
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertEqual(response.status_code, 403)

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

    @override_settings(DEBUG=False, USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['10.0.0.1'])
    def test_middleware_x_forwarded_for(self):
        """П-8: от доверенного прокси берётся правый недоверенный адрес."""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.99'
        BannedIP.objects.create(ip_address='10.0.0.99', reason='proxy')
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False, USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['10.0.0.1'])
    def test_middleware_ignores_spoofed_leftmost_hop(self):
        """П-8: подделанное левое значение не становится IP клиента."""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        # клиент подставил себе забаненный IP, прокси дописал реальный
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.99, 10.0.0.77'
        BannedIP.objects.create(ip_address='10.0.0.99', reason='spoofed')
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertIsNone(response)

    @override_settings(DEBUG=False, USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['10.0.0.1'])
    def test_middleware_bans_real_client_behind_proxy(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.99, 10.0.0.77'
        BannedIP.objects.create(ip_address='10.0.0.77', reason='real client')
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False, USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['10.0.0.1'])
    def test_middleware_ignores_forwarded_from_untrusted_source(self):
        """П-8: заголовок от недоверенного источника не учитывается вовсе."""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.99'
        BannedIP.objects.create(ip_address='10.0.0.99', reason='spoofed')
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertIsNone(response)

    @override_settings(DEBUG=False, USE_X_FORWARDED_FOR=False)
    def test_middleware_ignores_x_forwarded_for_by_default(self):
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.99'
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        BannedIP.objects.create(ip_address='10.0.0.99', reason='spoofed')
        response = IPBanMiddleware(lambda r: None)(request)
        self.assertIsNone(response)

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
        response = self.client.post('/logout/')  # П-9: выход только POST
        self.assertEqual(response.status_code, 302)

    def test_logout_rejects_get(self):
        self.client.login(username='loginuser', password='pass123')
        response = self.client.get('/logout/')
        self.assertEqual(response.status_code, 405)

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
        """П-41: раньше проверялся только код ответа, который совпадает и при успехе."""
        User.objects.create_user(username='nick_taken', password='pass123', nick='taken')
        self.user.nick = 'original'
        self.user.save(update_fields=['nick'])

        response = self.client.post('/profile/', {'nick': 'taken'})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nick, 'original')

    def test_profile_avatar_extension_comes_from_content(self):
        response = self.client.post('/profile/', {
            'avatar': fake_upload('payload.html', image_upload().read(), 'image/png'),
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith('.png'))
        self.assertFalse(self.user.avatar.name.endswith('.html'))

    def test_profile_avatar_rejects_non_image(self):
        old_name = self.user.avatar.name if self.user.avatar else None
        response = self.client.post('/profile/', {
            'avatar': fake_upload(
                'payload.html', b'<script>alert(1)</script>', 'text/html'),
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar.name if self.user.avatar else None, old_name)

    def test_profile_avatar_removes_previous_file(self):
        self.user.avatar = image_upload('old.png')
        self.user.save()
        old_name = self.user.avatar.name
        old_path = Path(settings.MEDIA_ROOT) / old_name

        response = self.client.post('/profile/', {
            'avatar': image_upload('new.png'),
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.avatar.name, old_name)
        self.assertFalse(old_path.exists())

    def test_user_deletion_removes_avatar(self):
        """П-48: аватар не остаётся на диске после удаления пользователя."""
        self.user.avatar = image_upload('deleted.png')
        self.user.save()
        avatar_path = Path(self.user.avatar.path)

        self.user.delete()
        self.assertFalse(avatar_path.exists())

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

    def test_change_username_rejects_quote_payload(self):
        """П-2: логин с кавычкой больше не принимается.

        Раньше `ChangeUsernameForm` не применял `UnicodeUsernameValidator`,
        поэтому логин вроде `a');alert(1)//` попадал в шаблоны и исполнялся
        как JS в inline-обработчике.
        """
        response = self.client.post('/profile/change-username/', {
            'username': "a');alert(1)//"
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'profileuser')

    def test_change_username_rejects_markup(self):
        response = self.client.post('/profile/change-username/', {
            'username': '<script>alert(1)</script>'
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'profileuser')

    def test_change_username_still_accepts_valid_login(self):
        response = self.client.post('/profile/change-username/', {
            'username': 'valid.login+tag@host'
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'valid.login+tag@host')

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

    def test_users_catalog_formats_last_seen(self):
        other = User.objects.create_user(username='catalog_last_seen', password='pass456')
        other.last_seen = timezone.now() - timedelta(days=2)
        other.save(update_fields=['last_seen'])

        response = self.client.get('/users/')
        self.assertContains(response, '2 дня')
        self.assertNotContains(response, 'назад')
        self.assertNotContains(response, '2880')

    def test_public_profile_online_status_is_not_duplicated(self):
        other = User.objects.create_user(username='online_profile', password='pass456')
        other.last_seen = timezone.now()
        other.save(update_fields=['last_seen'])

        response = self.client.get(reverse('public_profile', args=[other.username]))
        body = response.content.decode('utf-8')
        self.assertEqual(body.lower().count('онлайн'), 1)

    def test_public_profile_formats_last_seen(self):
        other = User.objects.create_user(username='offline_profile', password='pass456')
        other.last_seen = timezone.now() - timedelta(days=19)
        other.save(update_fields=['last_seen'])

        response = self.client.get(reverse('public_profile', args=[other.username]))
        self.assertContains(response, '19 дней')
        self.assertNotContains(response, 'назад')
        self.assertNotContains(response, '28193')


class ClientIPTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_default_ignores_x_forwarded_for(self):
        from users.utils import get_client_ip
        request = self.factory.get(
            '/', REMOTE_ADDR='1.2.3.4', HTTP_X_FORWARDED_FOR='9.9.9.9'
        )
        self.assertEqual(get_client_ip(request), '1.2.3.4')

    @override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['1.2.3.4'])
    def test_uses_rightmost_untrusted_hop(self):
        """П-8: берётся ближайший к приложению недоверенный адрес, не левый."""
        from users.utils import get_client_ip
        request = self.factory.get(
            '/', REMOTE_ADDR='1.2.3.4', HTTP_X_FORWARDED_FOR='9.9.9.9, 8.8.8.8'
        )
        self.assertEqual(get_client_ip(request), '8.8.8.8')

    @override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['1.2.3.4', '8.8.8.8'])
    def test_skips_trusted_hops(self):
        from users.utils import get_client_ip
        request = self.factory.get(
            '/', REMOTE_ADDR='1.2.3.4', HTTP_X_FORWARDED_FOR='9.9.9.9, 8.8.8.8'
        )
        self.assertEqual(get_client_ip(request), '9.9.9.9')

    @override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['1.2.3.4'])
    def test_ignores_header_from_untrusted_source(self):
        """П-8: без доверенного источника заголовок игнорируется полностью."""
        from users.utils import get_client_ip
        request = self.factory.get(
            '/', REMOTE_ADDR='7.7.7.7', HTTP_X_FORWARDED_FOR='9.9.9.9'
        )
        self.assertEqual(get_client_ip(request), '7.7.7.7')

    @override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXIES=['1.2.3.4'])
    def test_garbage_header_falls_back_to_remote_addr(self):
        from users.utils import get_client_ip
        request = self.factory.get(
            '/', REMOTE_ADDR='1.2.3.4', HTTP_X_FORWARDED_FOR='not-an-ip'
        )
        self.assertEqual(get_client_ip(request), '1.2.3.4')

    def test_ipv6_is_normalized(self):
        """П-33: разные записи одного адреса сравниваются одинаково."""
        from users.utils import normalize_ip
        self.assertEqual(normalize_ip('::ffff:127.0.0.1'), '127.0.0.1')
        self.assertEqual(normalize_ip(' 10.0.0.1 '), '10.0.0.1')
        self.assertEqual(normalize_ip('2001:0db8::1'), '2001:db8::1')
        self.assertIsNone(normalize_ip('nonsense'))
        # ведущие нули ipaddress не принимает: значение считается не-адресом
        self.assertIsNone(normalize_ip('127.000.000.001'))

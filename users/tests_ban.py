"""Тесты подсистемы бана пользователей (problems.md, П-4) и её аудита (П-5).

До исправления `banned_at` не проверялся нигде: забаненный пользователь и
входил, и продолжал работать, а сам бан нельзя было выставить даже из админки.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.backends import CustomAuthBackend
from users.models import AdminLog

User = get_user_model()


class BanEnforcementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='banned_guy', password='secret123',
        )

    def _ban(self, reason='спам'):
        self.user.banned_at = timezone.now()
        self.user.ban_reason = reason
        self.user.save(update_fields=['banned_at', 'ban_reason'])

    def test_banned_user_cannot_authenticate(self):
        self._ban()
        self.assertIsNone(
            CustomAuthBackend().authenticate(
                request=None, username='banned_guy', password='secret123',
            )
        )

    def test_no_configured_backend_lets_banned_user_in(self):
        """Каждый бэкенд из настроек обязан отклонять бан.

        `django.contrib.auth.backends.ModelBackend` использует собственную
        `user_can_authenticate` и не знает про `banned_at`, поэтому его наличие
        в списке полностью отменяло бан (problems.md, П-4).
        """
        from django.conf import settings
        from django.contrib.auth import load_backend

        self._ban()
        for backend_path in settings.AUTHENTICATION_BACKENDS:
            with self.subTest(backend=backend_path):
                backend = load_backend(backend_path)
                self.assertIsNone(backend.authenticate(
                    request=None, username='banned_guy', password='secret123',
                ))

    def test_banned_user_cannot_log_in_and_sees_reason(self):
        self._ban()
        response = self.client.post(
            '/auth/', {'username': 'banned_guy', 'password': 'secret123'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'заблокирован')
        self.assertContains(response, 'спам')

    def test_wrong_password_does_not_reveal_ban(self):
        """Причина блокировки показывается только при верном пароле."""
        self._ban()
        response = self.client.post(
            '/auth/', {'username': 'banned_guy', 'password': 'WRONG'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'заблокирован')

    def test_open_session_is_terminated_after_ban(self):
        """Бан обрывает уже открытую сессию, а не только следующий вход."""
        self.client.login(username='banned_guy', password='secret123')
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)

        self._ban()

        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'спам', status_code=403)
        # сессия сброшена: следующий запрос уже анонимный
        self.assertEqual(self.client.get(reverse('profile')).status_code, 302)

    def test_unban_restores_access(self):
        self._ban()
        self.user.banned_at = None
        self.user.save(update_fields=['banned_at'])
        self.client.login(username='banned_guy', password='secret123')
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)

    def test_inactive_user_is_still_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIsNone(
            CustomAuthBackend().authenticate(
                request=None, username='banned_guy', password='secret123',
            )
        )

    def test_ban_page_is_not_an_orphan_template(self):
        """`banned.html` действительно рендерится middleware.

        Войти забаненным нельзя, поэтому сессия открывается до бана.
        """
        self.client.login(username='banned_guy', password='secret123')
        self._ban(reason='нарушение правил')
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'нарушение правил', status_code=403)
        self.assertContains(response, 'banned_guy', status_code=403)
        self.assertContains(response, 'заблокирован', status_code=403)


class BanAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='audit_admin', password='admin123',
        )
        self.target = User.objects.create_user(username='target_user', password='123')
        self.client.login(username='audit_admin', password='admin123')

    def _run_action(self, action, pks):
        return self.client.post('/admin/users/user/', {
            'action': action,
            '_selected_action': [str(pk) for pk in pks],
        })

    def test_banned_at_is_editable_in_admin(self):
        """П-4: поле больше не readonly, иначе бан нельзя выставить из админки."""
        response = self.client.get(f'/admin/users/user/{self.target.pk}/change/')
        self.assertEqual(response.status_code, 200)
        form = response.context['adminform'].form
        self.assertIn('banned_at', form.fields)
        self.assertFalse(form.fields['banned_at'].disabled)

    def test_ban_action_sets_fields_and_writes_audit_log(self):
        """П-4 + П-5: действие бана работает и оставляет след."""
        response = self._run_action('ban_users', [self.target.pk])
        self.assertEqual(response.status_code, 302)

        self.target.refresh_from_db()
        self.assertIsNotNone(self.target.banned_at)
        self.assertEqual(self.target.banned_by, self.admin)

        log = AdminLog.objects.filter(action='ban_user', target_user=self.target).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.admin, self.admin)

    def test_unban_action_clears_fields_and_writes_audit_log(self):
        self._run_action('ban_users', [self.target.pk])
        self._run_action('unban_users', [self.target.pk])

        self.target.refresh_from_db()
        self.assertIsNone(self.target.banned_at)
        self.assertIsNone(self.target.banned_by)
        self.assertTrue(
            AdminLog.objects.filter(action='unban_user', target_user=self.target).exists()
        )

    def test_admin_cannot_ban_self(self):
        self._run_action('ban_users', [self.admin.pk])
        self.admin.refresh_from_db()
        self.assertIsNone(self.admin.banned_at)
        self.assertFalse(
            AdminLog.objects.filter(action='ban_user', target_user=self.admin).exists()
        )

    def test_ban_action_is_idempotent(self):
        self._run_action('ban_users', [self.target.pk])
        self._run_action('ban_users', [self.target.pk])
        self.assertEqual(
            AdminLog.objects.filter(action='ban_user', target_user=self.target).count(), 1,
        )


class UserAdminAuditTests(TestCase):
    """П-5: изменения пользователя из админки попадают в аудит."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='edit_admin', password='admin123',
        )
        self.target = User.objects.create_user(username='edit_target', password='123')
        self.client.login(username='edit_admin', password='admin123')

    def test_profile_edit_is_logged(self):
        response = self.client.post(f'/admin/users/user/{self.target.pk}/change/', {
            'username': 'edit_target',
            'nick': 'Изменённый',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AdminLog.objects.filter(action='edit_profile', target_user=self.target).exists()
        )

    def test_user_deletion_is_logged(self):
        response = self.client.post('/admin/users/user/', {
            'action': 'delete_selected',
            '_selected_action': [str(self.target.pk)],
            'post': 'yes',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AdminLog.objects.filter(action='delete_user').exists())


class IpBanAuditTests(TestCase):
    """П-5: блокировка IP тоже оставляет след."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='ip_admin', password='admin123',
        )
        self.client.login(username='ip_admin', password='admin123')

    def test_ip_ban_is_logged(self):
        response = self.client.post('/admin/users/bannedip/add/', {
            'ip_address': '10.10.10.10',
            'reason': 'спам',
        })
        self.assertEqual(response.status_code, 302)
        log = AdminLog.objects.filter(action='ban_ip').first()
        self.assertIsNotNone(log)
        self.assertIn('10.10.10.10', log.description)

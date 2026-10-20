from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from users.models import BannedIP, AdminLog, Notification

User = get_user_model()


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='superadmin', password='123')
        self.client.login(username='superadmin', password='123')
        self.user = User.objects.create_user(username='test_user', password='123')

    def test_admin_user_list(self):
        response = self.client.get('/admin/users/user/')
        self.assertEqual(response.status_code, 200)

    def test_admin_user_avatar_preview(self):
        file = SimpleUploadedFile("admin_av.png", b"x", content_type="image/png")
        self.user.avatar = file
        self.user.save()
        response = self.client.get('/admin/users/user/')
        self.assertEqual(response.status_code, 200)

    def test_admin_banned_ip_list(self):
        response = self.client.get('/admin/users/bannedip/')
        self.assertEqual(response.status_code, 200)

    def test_admin_adminlog_list(self):
        response = self.client.get('/admin/users/adminlog/')
        self.assertEqual(response.status_code, 200)

    def test_admin_notification_list(self):
        response = self.client.get('/admin/users/notification/')
        self.assertEqual(response.status_code, 200)

    def test_admin_banned_ip_save_model(self):
        response = self.client.post('/admin/users/bannedip/add/', {
            'ip_address': '10.0.0.55',
            'reason': 'test ban',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BannedIP.objects.filter(ip_address='10.0.0.55').exists())

    def test_admin_adminlog_no_add(self):
        self.client.logout()
        staff_user = User.objects.create_user(username='staff1', password='123', is_staff=True)
        self.client.login(username='staff1', password='123')
        response = self.client.get('/admin/users/adminlog/add/')
        self.assertEqual(response.status_code, 403)

    def test_admin_adminlog_no_change(self):
        self.client.logout()
        staff_user = User.objects.create_user(username='staff2', password='123', is_staff=True)
        self.client.login(username='staff2', password='123')
        log = AdminLog.objects.create(
            admin=self.admin, action='ban_user', description='test', target_user=self.user
        )
        response = self.client.get(f'/admin/users/adminlog/{log.pk}/change/')
        self.assertEqual(response.status_code, 403)

    def test_admin_adminlog_no_delete(self):
        log = AdminLog.objects.create(
            admin=self.admin, action='ban_user', description='test', target_user=self.user
        )
        response = self.client.get(f'/admin/users/adminlog/{log.pk}/delete/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AdminLog.objects.filter(pk=log.pk).exists())

    def test_adminlog_keeps_admin_username_after_user_deletion(self):
        log = AdminLog.objects.create(
            admin=self.admin, action='ban_user', description='test', target_user=self.user
        )
        deleter = User.objects.create_superuser(
            username='deleter', password='123',
        )
        self.client.logout()
        self.client.login(username='deleter', password='123')
        response = self.client.post('/admin/users/user/', {
            'action': 'delete_selected',
            '_selected_action': [str(self.admin.pk)],
            'post': 'yes',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.admin.pk).exists())
        log.refresh_from_db()
        self.assertIsNone(log.admin)
        self.assertEqual(log.admin_username, 'superadmin')


class StaffPrivilegeEscalationTests(TestCase):
    """П-1: персонал не должен выдавать привилегии через админку.

    В Django 6 штатный `UserAdmin` больше не отключает `is_superuser`,
    `groups` и `user_permissions`, поэтому защита нужна в `UltimateUserAdmin`.
    """

    def setUp(self):
        self.target = User.objects.create_user(username='victim', password='123')
        self.superadmin = User.objects.create_superuser(
            username='esc_super', password='123',
        )
        self.staff = User.objects.create_user(
            username='esc_staff', password='123', is_staff=True,
        )
        self.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label='users',
                                   codename='change_user')
        )
        self.client.login(username='esc_staff', password='123')
        self.url = f'/admin/users/user/{self.target.pk}/change/'

    def test_precondition_staff_can_change_users(self):
        # предусловие уязвимости: право на изменение пользователей есть
        self.assertTrue(self.staff.has_perm('users.change_user'))

    def test_change_form_hides_privileged_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="is_superuser"')
        self.assertNotContains(response, 'name="user_permissions"')

    def test_post_cannot_escalate_to_superuser(self):
        response = self.client.post(self.url, {
            'username': 'victim',
            'is_active': 'on',
            'is_superuser': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_superuser)

    def test_post_cannot_escalate_to_staff_on_self(self):
        self_url = f'/admin/users/user/{self.staff.pk}/change/'
        response = self.client.post(self_url, {
            'username': 'esc_staff',
            'is_active': 'on',
            'is_staff': 'on',
            'is_superuser': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_superuser)

    def test_superuser_can_still_grant_superuser(self):
        # положительный контроль: защита не сломала штатное поведение
        self.client.logout()
        self.client.login(username='esc_super', password='123')
        response = self.client.post(self.url, {
            'username': 'victim',
            'is_active': 'on',
            'is_superuser': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_superuser)

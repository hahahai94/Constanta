from django.test import TestCase
from django.contrib.auth import get_user_model
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

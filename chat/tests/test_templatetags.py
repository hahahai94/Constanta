from django.test import TestCase
from django.contrib.auth import get_user_model
from django.template import Template, Context
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserStatusTagTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='taguser', password='123')

    def test_status_online_recent(self):
        self.user.last_seen = timezone.now()
        result = self._render_status(self.user)
        self.assertIn('online', result)

    def test_status_offline_never(self):
        self.user.last_seen = None
        result = self._render_status(self.user)
        self.assertIn('offline', result)

    def test_status_offline_long_ago(self):
        self.user.last_seen = timezone.now() - timedelta(hours=2)
        result = self._render_status(self.user)
        self.assertIn('offline', result)

    def test_status_none_user(self):
        result = self._render_status(None)
        self.assertEqual(result.strip(), '')

    def _render_status(self, user):
        t = Template('{% load status_tags %}{{ user|user_status }}')
        return t.render(Context({'user': user}))

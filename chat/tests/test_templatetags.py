import json
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


class CustomFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cfilter', password='123')

    def test_sum_attribute_empty(self):
        t = Template('{% load custom_filters %}{{ qs|sum_attribute:"id" }}')
        result = t.render(Context({'qs': User.objects.none()}))
        self.assertEqual(result, '0')

    def test_sum_attribute_with_values(self):
        User.objects.create_user(username='cfilter2', password='123')
        t = Template('{% load custom_filters %}{{ qs|sum_attribute:"id" }}')
        result = t.render(Context({'qs': User.objects.all()}))
        self.assertNotEqual(result, '0')

    def test_in_mentions_empty(self):
        t = Template('{% load custom_filters %}{{ uid|in_mentions:"" }}')
        result = t.render(Context({'uid': '1'}))
        self.assertEqual(result, 'False')

    def test_in_mentions_present(self):
        mentions = json.dumps([1, 2, 3])
        t = Template('{% load custom_filters %}{{ uid|in_mentions:mj }}')
        result = t.render(Context({'uid': '1', 'mj': mentions}))
        self.assertEqual(result, 'True')

    def test_in_mentions_absent(self):
        mentions = json.dumps([2, 3])
        t = Template('{% load custom_filters %}{{ uid|in_mentions:mj }}')
        result = t.render(Context({'uid': '1', 'mj': mentions}))
        self.assertEqual(result, 'False')

    def test_in_mentions_invalid_json(self):
        t = Template('{% load custom_filters %}{{ uid|in_mentions:"not json" }}')
        result = t.render(Context({'uid': '1'}))
        self.assertEqual(result, 'False')

    def test_mention_class_present(self):
        mentions = json.dumps([1])
        t = Template('{% load custom_filters %}{{ uid|mention_class:mj }}')
        result = t.render(Context({'uid': '1', 'mj': mentions}))
        self.assertEqual(result, 'mentioned')

    def test_mention_class_absent(self):
        mentions = json.dumps([2])
        t = Template('{% load custom_filters %}{{ uid|mention_class:mj }}')
        result = t.render(Context({'uid': '1', 'mj': mentions}))
        self.assertEqual(result, '')

    def test_mention_class_empty(self):
        t = Template('{% load custom_filters %}{{ uid|mention_class:"" }}')
        result = t.render(Context({'uid': '1'}))
        self.assertEqual(result, '')

    def test_mention_class_invalid_json(self):
        t = Template('{% load custom_filters %}{{ uid|mention_class:"bad" }}')
        result = t.render(Context({'uid': '1'}))
        self.assertEqual(result, '')

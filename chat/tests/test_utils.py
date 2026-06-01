from django.test import TestCase
from chat.utils import generate_file_hash, parse_mentions, format_mention_content, create_notification
from chat.models import Group, GroupMember
from django.contrib.auth import get_user_model
from users.models import Notification
import io

User = get_user_model()


class UtilsHashTests(TestCase):
    def test_generate_file_hash(self):
        fake_file = io.BytesIO(b'test content')
        hash1 = generate_file_hash(fake_file, user_id=1, timestamp='2024-01-01')
        fake_file.seek(0)
        hash2 = generate_file_hash(fake_file, user_id=1, timestamp='2024-01-01')
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)

    def test_generate_file_hash_different_users(self):
        f = io.BytesIO(b'content')
        h1 = generate_file_hash(f, user_id=1, timestamp='t1')
        f.seek(0)
        h2 = generate_file_hash(f, user_id=2, timestamp='t1')
        self.assertNotEqual(h1, h2)


class UtilsMentionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mentioned_user', password='123')
        self.sender = User.objects.create_user(username='sender_user', password='123')

    def test_parse_no_mentions(self):
        text, ids = parse_mentions('Hello world')
        self.assertEqual(ids, [])

    def test_parse_mention_user(self):
        text, ids = parse_mentions(f'Hey @{self.user.username}')
        self.assertIn(self.user.id, ids)

    def test_parse_mention_all_in_group(self):
        group = Group.objects.create(name='Test Group', owner=self.sender)
        GroupMember.objects.create(group=group, user=self.user, role='member')
        text, ids = parse_mentions('@all', group=group)
        self.assertIn(self.user.id, ids)
        self.assertIn('mention-all', text)

    def test_parse_mention_all_no_group(self):
        text, ids = parse_mentions('@all')
        self.assertEqual(ids, [])

    def test_format_mention_content(self):
        raw = '<span class="mention mention-all">@all</span>'
        result = format_mention_content(raw)
        self.assertIn('mention-all', result)


class UtilsNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='notif_user', password='123')

    def test_create_notification(self):
        create_notification(
            user=self.user,
            notification_type='friend_request',
            title='Friend request',
            message='Someone wants to be your friend'
        )
        self.assertTrue(Notification.objects.filter(user=self.user).exists())

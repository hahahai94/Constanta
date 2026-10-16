from django.test import TestCase, TransactionTestCase
from chat.utils import generate_file_hash, parse_mentions, create_notification
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

    def test_generate_file_hash_without_timestamp(self):
        fake_file = io.BytesIO(b'auto timestamp')
        h = generate_file_hash(fake_file, user_id=1)
        self.assertEqual(len(h), 64)

    def test_generate_file_hash_no_chunks(self):
        class FakeFile:
            def __init__(self, data):
                self._data = data
                self._pos = 0
            def seek(self, pos):
                self._pos = pos
            def read(self, size=65536):
                chunk = self._data[self._pos:self._pos+size]
                self._pos += len(chunk)
                return chunk

        f = FakeFile(b'read-based content')
        h = generate_file_hash(f, user_id=1, timestamp='fixed')
        self.assertEqual(len(h), 64)

    def test_generate_file_hash_with_chunks(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile("test.txt", b"chunked content", content_type="text/plain")
        h1 = generate_file_hash(f, user_id=1, timestamp='chunk')
        f.seek(0)
        h2 = generate_file_hash(f, user_id=1, timestamp='chunk')
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)


class UtilsMentionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mentioned_user', password='123')
        self.sender = User.objects.create_user(username='sender_user', password='123')

    def test_parse_no_mentions(self):
        self.assertEqual(parse_mentions('Hello world'), [])

    def test_parse_mention_user(self):
        self.assertIn(self.user.id, parse_mentions(f'Hey @{self.user.username}'))

    def test_parse_mention_all_in_group(self):
        group = Group.objects.create(name='Test Group', owner=self.sender)
        GroupMember.objects.create(group=group, user=self.user, role='member')
        self.assertIn(self.user.id, parse_mentions('@all', group=group))

    def test_parse_mention_all_no_group(self):
        self.assertEqual(parse_mentions('@all'), [])

    def test_parse_mention_all_in_group_multiple_members(self):
        group = Group.objects.create(name='G2', owner=self.sender)
        u2 = User.objects.create_user(username='another_user', password='123')
        GroupMember.objects.create(group=group, user=self.user, role='member')
        GroupMember.objects.create(group=group, user=u2, role='member')
        ids = parse_mentions('@all check', group=group)
        self.assertIn(self.user.id, ids)
        self.assertIn(u2.id, ids)
        self.assertEqual(len(ids), 2)

    def test_parse_mentions_returns_plain_ids(self):
        """П-16: функция отдаёт id, а не разметку — HTML собирался и выбрасывался."""
        ids = parse_mentions(f'@{self.user.username}')
        self.assertTrue(all(isinstance(value, int) for value in ids))

class UtilsNotificationTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='notif_user', password='123')

    def test_create_notification(self):
        create_notification(
            user=self.user,
            notification_type='message',
            title='New message',
            message='Someone sent you a message'
        )
        self.assertTrue(Notification.objects.filter(user=self.user).exists())


class RateLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_rate_limit_decorator_blocks_excess(self):
        from chat.utils import rate_limit
        from django.http import HttpResponse

        call_count = [0]

        @rate_limit('test_endpoint', limit=2, period=10)
        def my_view(request):
            call_count[0] += 1
            return HttpResponse('ok')

        from django.http import HttpRequest
        req = HttpRequest()
        req.META = {'REMOTE_ADDR': '127.0.0.1'}
        req.method = 'POST'
        req.path = '/test/'

        resp1 = my_view(req)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(call_count[0], 1)

        resp2 = my_view(req)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(call_count[0], 2)

        resp3 = my_view(req)
        self.assertEqual(resp3.status_code, 429)
        self.assertEqual(call_count[0], 2)

    def test_rate_limit_applies_to_get(self):
        """П-6: GET больше не исключается — иначе лимит на `api_poll` не работал."""
        from chat.utils import rate_limit
        from django.http import HttpResponse

        call_count = [0]

        @rate_limit('test_get', limit=1, period=10)
        def my_view(request):
            call_count[0] += 1
            return HttpResponse('ok')

        from django.http import HttpRequest
        req = HttpRequest()
        req.META = {'REMOTE_ADDR': '127.0.0.1'}
        req.method = 'GET'
        req.path = '/test/'

        self.assertEqual(my_view(req).status_code, 200)
        self.assertEqual(my_view(req).status_code, 429)
        self.assertEqual(my_view(req).status_code, 429)
        self.assertEqual(call_count[0], 1)

    def test_rate_limit_key_ignores_path(self):
        """П-6: ключ не включает путь, иначе лимит обходится сменой UUID."""
        from chat.utils import rate_limit
        from django.http import HttpRequest, HttpResponse

        call_count = [0]

        @rate_limit('test_path', limit=1, period=10)
        def my_view(request):
            call_count[0] += 1
            return HttpResponse('ok')

        first = HttpRequest()
        first.META = {'REMOTE_ADDR': '127.0.0.1'}
        first.method = 'POST'
        first.path = '/groups/11111111-1111-1111-1111-111111111111/settings/'

        second = HttpRequest()
        second.META = {'REMOTE_ADDR': '127.0.0.1'}
        second.method = 'POST'
        second.path = '/groups/22222222-2222-2222-2222-222222222222/settings/'

        self.assertEqual(my_view(first).status_code, 200)
        self.assertEqual(my_view(second).status_code, 429)
        self.assertEqual(call_count[0], 1)

    def test_rate_limit_counter_is_atomic(self):
        """П-6: параллельные запросы не проходят все сразу (нет пары get/set)."""
        from users.ratelimit import hit

        allowed = [hit('atomic', limit=3, period=10)[0] for _ in range(6)]
        self.assertEqual(allowed, [True, True, True, False, False, False])

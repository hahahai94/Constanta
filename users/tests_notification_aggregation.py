"""Агрегированные уведомления по чатам и живые счётчики."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from chat.models import Channel, ChannelMember, Group, GroupMember, Message
from users.models import Notification

User = get_user_model()


class NotificationAggregationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sender = User.objects.create_user(
            username='agg_sender', password='123')
        self.receiver = User.objects.create_user(
            username='agg_receiver', password='123')

    def _send_direct(self, content='привет'):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('api_send'), {
                'user_id': self.receiver.id,
                'content': content,
            })
        self.assertEqual(response.status_code, 200)
        return response

    def _login(self, user):
        self.client.force_login(user)

    def test_direct_messages_share_one_unread_notification(self):
        self._login(self.sender)
        self._send_direct('первое')
        self._send_direct('второе')

        notes = Notification.objects.filter(
            user=self.receiver, notification_type='message')
        self.assertEqual(notes.count(), 1)
        note = notes.get()
        self.assertEqual(note.unread_count, 2)
        self.assertEqual(note.conversation_key, f'direct:{self.sender.id}')
        self.assertIn('второе', note.message)

    def test_opening_direct_chat_marks_notification_and_messages_read(self):
        self._login(self.sender)
        self._send_direct('первое')
        self._send_direct('второе')

        self._login(self.receiver)
        response = self.client.get(reverse('main'), {'user_id': self.sender.id})
        self.assertEqual(response.status_code, 200)

        note = Notification.objects.get(
            user=self.receiver, notification_type='message')
        self.assertTrue(note.is_read)
        self.assertFalse(Message.objects.filter(
            receiver=self.receiver, sender=self.sender, is_read=False).exists())
        chat = response.context['chats'][0]
        self.assertEqual(chat['unread_count'], 0)

    def test_group_messages_are_aggregated_and_cleared_by_open(self):
        member = User.objects.create_user(username='agg_member', password='123')
        group = Group.objects.create(name='Agg Group', owner=self.sender)
        GroupMember.objects.create(group=group, user=self.sender, role='owner')
        GroupMember.objects.create(group=group, user=member, role='member')
        self._login(self.sender)
        for index in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse('api_send'), {
                    'group_id': str(group.id),
                    'content': f'группа {index}',
                })
            self.assertEqual(response.status_code, 200)

        note = Notification.objects.get(
            user=member, notification_type='message')
        self.assertEqual(note.unread_count, 2)
        self.assertEqual(note.conversation_key, f'group:{group.id}')

        self._login(member)
        self.client.get(reverse('group_chat', args=[group.id]))
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_channel_posts_are_aggregated_and_cleared_by_open(self):
        channel = Channel.objects.create(name='Agg Channel', owner=self.sender)
        ChannelMember.objects.create(
            channel=channel, user=self.sender, role='owner')
        subscriber = User.objects.create_user(
            username='agg_subscriber', password='123')
        ChannelMember.objects.create(
            channel=channel, user=subscriber, role='subscriber')
        self._login(self.sender)
        for index in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse('api_channel_post', args=[channel.id]),
                    {'content': f'пост {index}'})
            self.assertEqual(response.status_code, 200)

        note = Notification.objects.get(
            user=subscriber, notification_type='message')
        self.assertEqual(note.unread_count, 2)
        self.assertEqual(note.conversation_key, f'channel:{channel.id}')

        self._login(subscriber)
        self.client.get(reverse('channel_view', args=[channel.id]))
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_notification_page_shows_one_entry_per_chat(self):
        self._login(self.sender)
        self._send_direct(f'@{self.receiver.username} первое')
        self._send_direct(f'@{self.receiver.username} второе')

        self._login(self.receiver)
        response = self.client.get(reverse('notifications'))
        grouped = list(response.context['notifications'])
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]['unread_count'], 2)

    def test_opening_chat_removes_it_from_unread_notifications_page(self):
        self._login(self.sender)
        self._send_direct('привет')

        self._login(self.receiver)
        self.client.get(reverse('main'), {'user_id': self.sender.id})
        response = self.client.get(reverse('notifications'))
        self.assertEqual(len(list(response.context['notifications'])), 0)

        history = self.client.get(reverse('notifications'), {'all': '1'})
        self.assertEqual(len(list(history.context['notifications'])), 1)

    def test_poll_returns_counts_without_history_then_new_event(self):
        self._login(self.receiver)
        first = self.client.get(reverse('notifications_poll'))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['events'], [])
        cursor = first.json()['cursor']

        self._login(self.sender)
        self._send_direct('новое')

        self._login(self.receiver)
        response = self.client.get(
            reverse('notifications_poll'), {'since': cursor})
        data = response.json()
        self.assertEqual(len(data['events']), 1)
        self.assertEqual(
            data['events'][0]['conversation_key'],
            f'direct:{self.sender.id}',
        )
        self.assertEqual(data['unread_messages_count'], 1)

    def test_deleting_message_reduces_unread_count(self):
        self._login(self.sender)
        self._send_direct('первое')
        second = self._send_direct('второе')
        message_id = Message.objects.filter(
            sender=self.sender, receiver=self.receiver,
            content='второе').get().id
        self.assertEqual(second.status_code, 200)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('api_delete_message', args=[message_id]))
        self.assertEqual(response.status_code, 200)

        note = Notification.objects.get(
            user=self.receiver, notification_type='message')
        self.assertEqual(note.unread_count, 1)
        self.assertIn('первое', note.message)


class NotificationMarkAllTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='mark_all_user', password='123')
        self.client.force_login(self.user)

    def test_mark_all_read_covers_chats_and_direct_messages(self):
        sender = User.objects.create_user(username='mark_all_sender', password='123')
        Notification.objects.create(
            user=self.user, notification_type='message',
            title='t', message='m', conversation_key=f'direct:{sender.id}')
        Message.objects.create(
            sender=sender, receiver=self.user, content='непрочитано')

        response = self.client.post(reverse('notifications_read_all'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Notification.objects.filter(
            user=self.user, is_read=False).exists())
        self.assertFalse(Message.objects.filter(
            receiver=self.user, is_read=False).exists())

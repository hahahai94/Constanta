"""Живой список личных чатов и счётчики в списках групп/каналов."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chat.models import Channel, ChannelMember, Group, GroupMember, Message
from users.models import Notification

User = get_user_model()


class PrivateChatListTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            username='list_viewer', password='123')
        self.older = User.objects.create_user(
            username='list_older', password='123')
        self.newer = User.objects.create_user(
            username='list_newer', password='123')
        self.client.force_login(self.viewer)

        old_message = Message.objects.create(
            sender=self.older, receiver=self.viewer, content='старое')
        new_message = Message.objects.create(
            sender=self.newer, receiver=self.viewer, content='новое')
        Message.objects.filter(id=old_message.id).update(
            created_at=timezone.now() - timedelta(hours=1))
        Message.objects.filter(id=new_message.id).update(
            created_at=timezone.now())

        Notification.objects.create(
            user=self.viewer, notification_type='message',
            title='old', message='old',
            conversation_key=f'direct:{self.older.id}', unread_count=3)
        Notification.objects.create(
            user=self.viewer, notification_type='message',
            title='new', message='new',
            conversation_key=f'direct:{self.newer.id}', unread_count=1)

    def test_chats_are_sorted_by_last_message_with_badges(self):
        response = self.client.get(reverse('main'))
        chats = response.context['chats']
        self.assertEqual(
            [chat['user'] for chat in chats], [self.newer, self.older])
        self.assertEqual(chats[0]['unread_count'], 1)
        self.assertEqual(chats[1]['unread_count'], 3)
        self.assertContains(response, 'chat-unread-badge')

    def test_chat_list_api_returns_fragment_and_marks_active(self):
        response = self.client.get(
            reverse('api_chat_list'), {'active_user_id': self.older.id})
        data = response.json()
        self.assertIn(f'data-chat-user="{self.older.id}"', data['html'])
        self.assertIn('active', data['html'])
        self.assertEqual(data['unread_total'], 4)

    def test_group_messages_do_not_appear_in_private_list(self):
        group = Group.objects.create(name='Not Private', owner=self.viewer)
        GroupMember.objects.create(
            group=group, user=self.viewer, role='owner')
        Message.objects.create(sender=self.viewer, group=group, content='группа')

        response = self.client.get(reverse('main'))
        self.assertEqual(len(response.context['chats']), 2)


class ConversationListBadgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='badge_user', password='123')
        self.client.force_login(self.user)

    def test_group_list_has_unread_badge(self):
        group = Group.objects.create(name='Badge Group', owner=self.user)
        GroupMember.objects.create(
            group=group, user=self.user, role='owner')
        Notification.objects.create(
            user=self.user, notification_type='message',
            title='group', message='group',
            conversation_key=f'group:{group.id}', unread_count=4)

        response = self.client.get(reverse('groups'))
        membership = list(response.context['memberships'])[0]
        self.assertEqual(membership.unread_count, 4)
        self.assertContains(response, '>4</span>')

    def test_channel_list_has_unread_badge(self):
        channel = Channel.objects.create(name='Badge Channel', owner=self.user)
        ChannelMember.objects.create(
            channel=channel, user=self.user, role='owner')
        Notification.objects.create(
            user=self.user, notification_type='message',
            title='channel', message='channel',
            conversation_key=f'channel:{channel.id}', unread_count=2)

        response = self.client.get(reverse('channel_list'))
        membership = list(response.context['memberships'])[0]
        self.assertEqual(membership.unread_count, 2)
        self.assertContains(response, '>2</span>')

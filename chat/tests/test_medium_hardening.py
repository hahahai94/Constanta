"""Регрессионные тесты средних пунктов: П-12, П-13, П-22, П-23, П-24, П-28."""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chat.models import Channel, ChannelMember, Group, GroupMember, Message

User = get_user_model()


class MutedMemberTests(TestCase):
    """П-12: роль «Заблокирован» должна запрещать отправку."""

    def setUp(self):
        self.owner = User.objects.create_user(username='mute_owner', password='123')
        self.muted = User.objects.create_user(username='mute_guy', password='123')
        self.group = Group.objects.create(name='Muted', owner=self.owner)
        GroupMember.objects.create(group=self.group, user=self.owner, role='owner')
        GroupMember.objects.create(group=self.group, user=self.muted, role='muted')
        self.client.login(username='mute_guy', password='123')

    def test_muted_member_cannot_post(self):
        response = self.client.post('/api/send/', {
            'group_id': str(self.group.id), 'content': 'всё ещё пишу',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Message.objects.filter(group=self.group).exists())

    def test_active_member_can_post(self):
        GroupMember.objects.filter(
            group=self.group, user=self.muted).update(role='member')
        response = self.client.post('/api/send/', {
            'group_id': str(self.group.id), 'content': 'обычное сообщение',
        })
        self.assertEqual(response.status_code, 200)


class SetRoleValidationTests(TestCase):
    """П-13: роль проверяется по модели, а не принимается как есть."""

    def setUp(self):
        self.owner = User.objects.create_user(username='role_owner', password='123')
        self.member = User.objects.create_user(username='role_member', password='123')
        self.group = Group.objects.create(name='Roles', owner=self.owner)
        GroupMember.objects.create(group=self.group, user=self.owner, role='owner')
        GroupMember.objects.create(group=self.group, user=self.member, role='member')
        self.client.login(username='role_owner', password='123')

    def _set_role(self, role):
        return self.client.post('/api/set-role/', json.dumps({
            'group_id': str(self.group.id),
            'user_id': self.member.id,
            'role': role,
        }), content_type='application/json')

    def test_invalid_role_rejected(self):
        self.assertEqual(self._set_role('superuser').status_code, 400)
        self.assertEqual(
            GroupMember.objects.get(group=self.group, user=self.member).role, 'member')

    def test_owner_role_cannot_be_assigned(self):
        self.assertEqual(self._set_role('owner').status_code, 400)

    def test_valid_role_applied(self):
        self.assertEqual(self._set_role('admin').status_code, 200)
        self.assertEqual(
            GroupMember.objects.get(group=self.group, user=self.member).role, 'admin')


class ApiNotFoundTests(TestCase):
    """П-23: Http404 не должен превращаться в 500 или 400."""

    def setUp(self):
        self.user = User.objects.create_user(username='notfound_user', password='123')
        self.client.login(username='notfound_user', password='123')

    def test_send_to_unknown_user_returns_404(self):
        response = self.client.post('/api/send/', {'user_id': '999999', 'content': 'hi'})
        self.assertEqual(response.status_code, 404)

    def test_send_to_unknown_group_returns_404(self):
        response = self.client.post('/api/send/', {
            'group_id': '00000000-0000-0000-0000-000000000000', 'content': 'hi',
        })
        self.assertEqual(response.status_code, 404)

    def test_add_member_to_unknown_group_returns_404(self):
        response = self.client.post('/api/add-member/', json.dumps({
            'group_id': '00000000-0000-0000-0000-000000000000', 'username': 'nobody',
        }), content_type='application/json')
        self.assertEqual(response.status_code, 404)


class RobotsTxtTests(TestCase):
    """П-22: robots.txt не раскрывает путь админки."""

    def test_admin_path_is_not_published(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('admin', response.content.decode().lower())


class EnvExampleTests(TestCase):
    """П-24: пример конфигурации не должен включать DEBUG."""

    def test_debug_is_disabled_in_example(self):
        content = (Path(settings.BASE_DIR) / '.env.example').read_text(encoding='utf-8')
        self.assertIn('DEBUG=False', content)
        self.assertNotIn('DEBUG=True', content)


class ChannelLimitTests(TestCase):
    """П-28: каналы ограничены, списки на странице не безграничны."""

    def setUp(self):
        self.user = User.objects.create_user(username='chan_limit', password='123')
        self.client.login(username='chan_limit', password='123')

    def test_channel_creation_is_limited(self):
        for index in range(settings.MAX_CHANNELS_PER_USER):
            Channel.objects.create(name=f'C{index}', owner=self.user)

        response = self.client.post(reverse('create_channel'), {'name': 'Overflow'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Channel.objects.filter(name='Overflow').exists())

    def test_channel_list_is_bounded(self):
        for index in range(5):
            channel = Channel.objects.create(name=f'Owned{index}', owner=self.user)
            ChannelMember.objects.create(channel=channel, user=self.user, role='owner')

        response = self.client.get(reverse('channel_list'))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.context['memberships']), 100)

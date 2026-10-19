from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from chat.models import Channel, ChannelMember, Message
import json

User = get_user_model()


class ChannelModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ch_owner', password='123')

    def test_create_channel(self):
        ch = Channel.objects.create(name='News', owner=self.user)
        self.assertEqual(str(ch), 'News')
        self.assertEqual(ch.get_avatar_url(), '/static/default_channel_avatar.png')

    def test_channel_is_owner(self):
        ch = Channel.objects.create(name='Test', owner=self.user)
        self.assertTrue(ch.is_owner(self.user))
        other = User.objects.create_user(username='other', password='123')
        self.assertFalse(ch.is_owner(other))

    def test_channel_is_admin(self):
        ch = Channel.objects.create(name='Test', owner=self.user)
        ChannelMember.objects.create(channel=ch, user=self.user, role='owner')
        self.assertTrue(ch.is_admin(self.user))

    def test_channel_is_subscriber(self):
        ch = Channel.objects.create(name='Test', owner=self.user)
        ChannelMember.objects.create(channel=ch, user=self.user, role='subscriber')
        self.assertTrue(ch.is_subscriber(self.user))

    def test_channel_member_str(self):
        ch = Channel.objects.create(name='News', owner=self.user)
        cm = ChannelMember.objects.create(channel=ch, user=self.user, role='owner')
        self.assertIn('ch_owner', str(cm))
        self.assertIn('owner', str(cm))


class ChannelViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='ch_owner2', password='123')
        self.user = User.objects.create_user(username='ch_user', password='123')
        self.client.login(username='ch_owner2', password='123')
        self.channel = Channel.objects.create(name='Updates', owner=self.owner)
        ChannelMember.objects.create(channel=self.channel, user=self.owner, role='owner')

    def test_channel_list(self):
        response = self.client.get(reverse('channel_list'))
        self.assertEqual(response.status_code, 200)

    def test_channel_view_not_subscribed(self):
        self.client.logout()
        self.client.login(username='ch_user', password='123')
        response = self.client.get(reverse('channel_view', args=[self.channel.id]))
        self.assertRedirects(response, reverse('channel_list'))

    def test_channel_view_subscribed(self):
        response = self.client.get(reverse('channel_view', args=[self.channel.id]))
        self.assertEqual(response.status_code, 200)

    def test_join_channel_rejects_get(self):
        """П-9: подписка через GET больше не работает."""
        public = Channel.objects.create(name='Public', owner=self.owner)
        response = self.client.get(reverse('join_channel', args=[public.id]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(
            ChannelMember.objects.filter(channel=public, user=self.owner).exists()
        )

    def test_leave_channel_rejects_get(self):
        """П-9: отписка через GET больше не работает."""
        self.client.login(username='ch_user', password='123')
        ChannelMember.objects.create(channel=self.channel, user=self.user, role='subscriber')
        response = self.client.get(reverse('leave_channel', args=[self.channel.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            ChannelMember.objects.filter(channel=self.channel, user=self.user).exists()
        )

    def test_create_channel_post(self):
        response = self.client.post(reverse('create_channel'), {'name': 'NewChan'})
        self.assertTrue(Channel.objects.filter(name='NewChan').exists())
        self.assertRedirects(response, reverse('channel_view', args=[Channel.objects.get(name='NewChan').id]))

    def test_join_channel(self):
        self.client.logout()
        self.client.login(username='ch_user', password='123')
        response = self.client.post(reverse('join_channel', args=[self.channel.id]))
        self.assertTrue(ChannelMember.objects.filter(channel=self.channel, user=self.user).exists())
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))

    def test_join_channel_already_subscribed(self):
        """П-41: проверяем отсутствие дубликата подписки, а не только редирект."""
        ChannelMember.objects.create(channel=self.channel, user=self.user, role='subscriber')
        self.client.logout()
        self.client.login(username='ch_user', password='123')
        response = self.client.post(reverse('join_channel', args=[self.channel.id]))
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))
        self.assertEqual(
            ChannelMember.objects.filter(channel=self.channel, user=self.user).count(), 1)

    def test_leave_channel(self):
        ChannelMember.objects.create(channel=self.channel, user=self.user, role='subscriber')
        self.client.logout()
        self.client.login(username='ch_user', password='123')
        response = self.client.post(reverse('leave_channel', args=[self.channel.id]))
        self.assertFalse(ChannelMember.objects.filter(channel=self.channel, user=self.user).exists())
        self.assertRedirects(response, reverse('channel_list'))

    def test_leave_channel_owner_protected(self):
        response = self.client.post(reverse('leave_channel', args=[self.channel.id]))
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))
        self.assertTrue(ChannelMember.objects.filter(channel=self.channel, user=self.owner).exists())

    def test_delete_channel(self):
        ch = Channel.objects.create(name='Temp', owner=self.owner)
        ChannelMember.objects.create(channel=ch, user=self.owner, role='owner')
        response = self.client.post(reverse('delete_channel', args=[ch.id]))
        self.assertFalse(Channel.objects.filter(id=ch.id).exists())
        self.assertRedirects(response, reverse('channel_list'))

    def test_delete_channel_removes_avatar_and_posts(self):
        """П-48: удаление канала не оставляет файлы на диске."""
        import os
        from django.core.files.uploadedfile import SimpleUploadedFile
        from chat.models import Message

        ch = Channel.objects.create(name='Temp files', owner=self.owner)
        ch.avatar = SimpleUploadedFile('channel.png', b'avatar', content_type='image/png')
        ch.save()
        avatar_path = ch.avatar.path
        post = Message.objects.create(
            sender=self.owner, channel=ch, content='post',
            attachment=SimpleUploadedFile('post.txt', b'content'),
        )
        attachment_path = post.attachment.path

        response = self.client.post(reverse('delete_channel', args=[ch.id]))
        self.assertRedirects(response, reverse('channel_list'))
        self.assertFalse(os.path.exists(avatar_path))
        self.assertFalse(os.path.exists(attachment_path))

    def test_delete_channel_not_owner(self):
        ch = Channel.objects.create(name='Temp2', owner=self.user)
        ChannelMember.objects.create(channel=ch, user=self.user, role='owner')
        ChannelMember.objects.create(channel=ch, user=self.owner, role='subscriber')
        response = self.client.post(reverse('delete_channel', args=[ch.id]))
        self.assertTrue(Channel.objects.filter(id=ch.id).exists())
        self.assertRedirects(response, reverse('channel_view', args=[ch.id]))

    def test_edit_channel_post(self):
        response = self.client.post(reverse('edit_channel', args=[self.channel.id]), {
            'name': 'Updated', 'description': 'Desc'
        })
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.name, 'Updated')
        self.assertEqual(self.channel.description, 'Desc')
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))

    def test_edit_channel_get(self):
        response = self.client.get(reverse('edit_channel', args=[self.channel.id]))
        self.assertEqual(response.status_code, 200)

    def test_edit_channel_no_permission(self):
        self.client.logout()
        self.client.login(username='ch_user', password='123')
        ChannelMember.objects.create(channel=self.channel, user=self.user, role='subscriber')
        response = self.client.get(reverse('edit_channel', args=[self.channel.id]))
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))


class ChannelAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='api_owner', password='123')
        self.user = User.objects.create_user(username='api_user', password='123')
        self.client.login(username='api_owner', password='123')
        self.channel = Channel.objects.create(name='API Chan', owner=self.owner)
        ChannelMember.objects.create(channel=self.channel, user=self.owner, role='owner')

    def test_channel_post_get_fails(self):
        response = self.client.get(reverse('api_channel_post', args=[self.channel.id]))
        self.assertEqual(response.status_code, 405)

    def test_channel_post_no_permission(self):
        self.client.logout()
        self.client.login(username='api_user', password='123')
        ChannelMember.objects.create(channel=self.channel, user=self.user, role='subscriber')
        response = self.client.post(reverse('api_channel_post', args=[self.channel.id]), {'content': 'hi'})
        self.assertEqual(response.status_code, 403)

    def test_channel_post_empty(self):
        response = self.client.post(reverse('api_channel_post', args=[self.channel.id]), {'content': ''})
        self.assertEqual(response.status_code, 400)

    def test_channel_post_success(self):
        response = self.client.post(reverse('api_channel_post', args=[self.channel.id]), {'content': 'Hello channel!'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(channel=self.channel, content='Hello channel!').exists())

    def test_channel_post_too_long(self):
        long_text = 'x' * 3000
        response = self.client.post(reverse('api_channel_post', args=[self.channel.id]), {'content': long_text})
        self.assertEqual(response.status_code, 400)

    def test_channel_post_anonymous(self):
        self.client.logout()
        response = self.client.post(reverse('api_channel_post', args=[self.channel.id]), {'content': 'test'})
        self.assertIn(response.status_code, [302, 403])


class ChannelModelTestAdditional(TestCase):
    def test_channel_avatar_url(self):
        user = User.objects.create_user(username='av_test', password='123')
        ch = Channel.objects.create(name='AvChan', owner=user)
        self.assertEqual(ch.get_avatar_url(), '/static/default_channel_avatar.png')

    def test_channel_has_unique_invite_token(self):
        user = User.objects.create_user(username='tok_test', password='123')
        ch1 = Channel.objects.create(name='C1', owner=user)
        ch2 = Channel.objects.create(name='C2', owner=user)
        self.assertIsNotNone(ch1.invite_token)
        self.assertNotEqual(ch1.invite_token, ch2.invite_token)


class ChannelInviteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='inv_owner', password='123')
        self.user = User.objects.create_user(username='inv_user', password='123')
        self.channel = Channel.objects.create(name='Private', owner=self.owner, is_private=True)
        ChannelMember.objects.create(channel=self.channel, user=self.owner, role='owner')

    def test_create_private_channel(self):
        self.client.login(username='inv_owner', password='123')
        response = self.client.post(reverse('create_channel'), {'name': 'Secret', 'is_private': '1'})
        channel = Channel.objects.get(name='Secret')
        self.assertTrue(channel.is_private)
        self.assertRedirects(response, reverse('channel_view', args=[channel.id]))

    def test_edit_channel_toggle_private(self):
        self.client.login(username='inv_owner', password='123')
        self.client.post(reverse('edit_channel', args=[self.channel.id]), {
            'name': 'Private', 'description': '', 'is_private': '0'
        })
        self.channel.refresh_from_db()
        self.assertFalse(self.channel.is_private)

    def test_invite_link_shown_to_owner(self):
        self.client.login(username='inv_owner', password='123')
        response = self.client.get(reverse('channel_view', args=[self.channel.id]))
        self.assertContains(response, str(self.channel.invite_token))

    def test_invite_join_private_channel(self):
        self.client.login(username='inv_user', password='123')
        response = self.client.get(reverse('channel_invite', args=[self.channel.invite_token]))
        self.assertTrue(ChannelMember.objects.filter(channel=self.channel, user=self.user).exists())
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))

    def test_invite_already_subscribed(self):
        ChannelMember.objects.create(channel=self.channel, user=self.user, role='subscriber')
        self.client.login(username='inv_user', password='123')
        response = self.client.get(reverse('channel_invite', args=[self.channel.invite_token]))
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))
        self.assertEqual(ChannelMember.objects.filter(channel=self.channel, user=self.user).count(), 1)

    def test_invalid_invite_token_404(self):
        self.client.login(username='inv_user', password='123')
        response = self.client.get(reverse('channel_invite', args=['00000000-0000-0000-0000-000000000000']))
        self.assertEqual(response.status_code, 404)

    def test_regenerate_invite_changes_token(self):
        self.client.login(username='inv_owner', password='123')
        old = self.channel.invite_token
        response = self.client.post(reverse('channel_regenerate_invite', args=[self.channel.id]))
        self.channel.refresh_from_db()
        self.assertNotEqual(old, self.channel.invite_token)
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))

    def test_regenerate_invite_old_token_invalid(self):
        old = self.channel.invite_token
        self.client.login(username='inv_owner', password='123')
        self.client.post(reverse('channel_regenerate_invite', args=[self.channel.id]))
        self.client.logout()
        self.client.login(username='inv_user', password='123')
        response = self.client.get(reverse('channel_invite', args=[old]))
        self.assertEqual(response.status_code, 404)

    def test_regenerate_invite_not_owner(self):
        ChannelMember.objects.create(channel=self.channel, user=self.user, role='subscriber')
        self.client.login(username='inv_user', password='123')
        old = self.channel.invite_token
        response = self.client.post(reverse('channel_regenerate_invite', args=[self.channel.id]))
        self.channel.refresh_from_db()
        self.assertEqual(old, self.channel.invite_token)
        self.assertRedirects(response, reverse('channel_view', args=[self.channel.id]))

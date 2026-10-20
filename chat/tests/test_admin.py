from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from chat.models import Group, GroupMember, Message, Channel
from chat.admin import (
    UltimateGroupAdmin, UltimateMessageAdmin, UltimateGroupMemberAdmin,
    ChannelAdmin,
)
from chat.tests.factories import image_upload
from users.models import AdminLog
import io, os, csv

User = get_user_model()


class ChatAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='chatadmin', password='123')
        self.client.login(username='chatadmin', password='123')
        self.user = User.objects.create_user(username='regular', password='123')
        self.group = Group.objects.create(name='Admin Group', owner=self.admin)
        GroupMember.objects.create(group=self.group, user=self.admin, role='owner')

    def test_admin_group_list(self):
        response = self.client.get('/admin/chat/group/')
        self.assertEqual(response.status_code, 200)

    def test_admin_message_list(self):
        response = self.client.get('/admin/chat/message/')
        self.assertEqual(response.status_code, 200)

    def test_admin_groupmember_list(self):
        response = self.client.get('/admin/chat/groupmember/')
        self.assertEqual(response.status_code, 200)

    def test_admin_hard_delete_groups(self):
        g = Group.objects.create(name='To Delete', owner=self.user)
        g_pk = g.pk
        response = self.client.post('/admin/chat/group/', {
            'action': 'hard_delete_groups',
            '_selected_action': [g_pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Group.objects.filter(pk=g_pk).exists())

    def test_admin_hard_delete_messages(self):
        file = SimpleUploadedFile("del_msg.txt", b"content", content_type="text/plain")
        msg = Message.objects.create(sender=self.user, receiver=self.admin, content='delete me', attachment=file)
        msg_pk = msg.pk
        attachment_path = msg.attachment.path
        response = self.client.post('/admin/chat/message/', {
            'action': 'hard_delete_messages',
            '_selected_action': [msg_pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Message.objects.filter(pk=msg_pk).exists())
        self.assertFalse(os.path.exists(attachment_path))

    def test_admin_hard_delete_group_removes_avatar_and_attachments(self):
        """П-48: каскадное удаление группы чистит файлы, а не только БД."""
        group = Group.objects.create(name='With Files', owner=self.admin)
        group.avatar = SimpleUploadedFile('group.png', b'avatar', content_type='image/png')
        group.save()
        avatar_path = group.avatar.path
        message = Message.objects.create(
            sender=self.admin, group=group, content='attachment',
            attachment=SimpleUploadedFile('group.txt', b'content'),
        )
        attachment_path = message.attachment.path

        response = self.client.post('/admin/chat/group/', {
            'action': 'hard_delete_groups',
            '_selected_action': [group.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())
        self.assertFalse(os.path.exists(avatar_path))
        self.assertFalse(os.path.exists(attachment_path))

    def test_admin_group_avatar_replacement_removes_old_file(self):
        group = Group.objects.create(
            name='Admin Avatar Group', owner=self.admin,
            avatar=image_upload('admin_old_group.png'))
        old_path = group.avatar.path
        group.avatar = image_upload('admin_new_group.png')
        request = RequestFactory().post('/admin/chat/group/')
        request.user = self.admin
        UltimateGroupAdmin(Group, AdminSite()).save_model(
            request, group, None, change=True)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(group.avatar.path))

    def test_admin_channel_avatar_replacement_removes_old_file(self):
        channel = Channel.objects.create(
            name='Admin Avatar Channel', owner=self.admin,
            avatar=image_upload('admin_old_channel.png'))
        old_path = channel.avatar.path
        channel.avatar = image_upload('admin_new_channel.png')
        request = RequestFactory().post('/admin/chat/channel/')
        request.user = self.admin
        ChannelAdmin(Channel, AdminSite()).save_model(
            request, channel, None, change=True)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(channel.avatar.path))

    def test_admin_export_group_members(self):
        GroupMember.objects.create(group=self.group, user=self.user, role='member')
        response = self.client.post('/admin/chat/group/', {
            'action': 'export_group_members',
            '_selected_action': [self.group.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_admin_export_group_members_escapes_formulas(self):
        group = Group.objects.create(name='=1+1', owner=self.admin)
        GroupMember.objects.create(group=group, user=self.user, role='member')
        response = self.client.post('/admin/chat/group/', {
            'action': 'export_group_members',
            '_selected_action': [group.pk],
        })
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[1][0], "'=1+1")

    def test_admin_export_messages_csv(self):
        Message.objects.create(sender=self.user, receiver=self.admin, content='export me')
        msg = Message.objects.first()
        response = self.client.post('/admin/chat/message/', {
            'action': 'export_messages_csv',
            '_selected_action': [msg.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_admin_promote_to_admin(self):
        gm = GroupMember.objects.create(group=self.group, user=self.user, role='member')
        response = self.client.post('/admin/chat/groupmember/', {
            'action': 'promote_to_admin',
            '_selected_action': [gm.pk],
        })
        self.assertEqual(response.status_code, 302)
        gm.refresh_from_db()
        self.assertEqual(gm.role, 'admin')

    def test_admin_demote_to_member(self):
        gm = GroupMember.objects.create(group=self.group, user=self.user, role='admin')
        response = self.client.post('/admin/chat/groupmember/', {
            'action': 'demote_to_member',
            '_selected_action': [gm.pk],
        })
        self.assertEqual(response.status_code, 302)
        gm.refresh_from_db()
        self.assertEqual(gm.role, 'member')

    def test_admin_kick_from_groups(self):
        gm = GroupMember.objects.create(group=self.group, user=self.user, role='member')
        response = self.client.post('/admin/chat/groupmember/', {
            'action': 'kick_from_groups',
            '_selected_action': [gm.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GroupMember.objects.filter(pk=gm.pk).exists())


class ChatAdminAuditTests(TestCase):
    """П-5: разрушительные действия админки оставляют след в AdminLog.

    До исправления `AdminLog` не заполнялся вообще: удаление групп и сообщений
    вместе с файлами, баны и смены ролей не логировались.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser(username='audit_chat', password='123')
        self.client.login(username='audit_chat', password='123')
        self.user = User.objects.create_user(username='audit_target', password='123')
        self.group = Group.objects.create(name='Audited', owner=self.admin)
        GroupMember.objects.create(group=self.group, user=self.admin, role='owner')

    def test_hard_delete_groups_is_logged(self):
        group = Group.objects.create(name='To audit', owner=self.user)
        response = self.client.post('/admin/chat/group/', {
            'action': 'hard_delete_groups',
            '_selected_action': [group.pk],
        })
        self.assertEqual(response.status_code, 302)
        log = AdminLog.objects.filter(action='delete_group').first()
        self.assertIsNotNone(log)
        self.assertIn('To audit', log.description)
        self.assertEqual(log.admin, self.admin)

    def test_hard_delete_messages_is_logged(self):
        msg = Message.objects.create(sender=self.user, receiver=self.admin, content='gone')
        response = self.client.post('/admin/chat/message/', {
            'action': 'hard_delete_messages',
            '_selected_action': [msg.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AdminLog.objects.filter(action='delete_message').exists())

    def test_role_change_is_logged(self):
        gm = GroupMember.objects.create(group=self.group, user=self.user, role='member')
        self.client.post('/admin/chat/groupmember/', {
            'action': 'promote_to_admin',
            '_selected_action': [gm.pk],
        })
        self.assertTrue(AdminLog.objects.filter(action='change_role').exists())

    def test_kick_member_is_logged(self):
        gm = GroupMember.objects.create(group=self.group, user=self.user, role='member')
        self.client.post('/admin/chat/groupmember/', {
            'action': 'kick_from_groups',
            '_selected_action': [gm.pk],
        })
        self.assertTrue(AdminLog.objects.filter(action='kick_member').exists())

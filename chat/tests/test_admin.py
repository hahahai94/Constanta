from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from chat.models import Group, GroupMember, Message
from chat.admin import UltimateGroupAdmin, UltimateMessageAdmin, UltimateGroupMemberAdmin
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
        response = self.client.post('/admin/chat/message/', {
            'action': 'hard_delete_messages',
            '_selected_action': [msg_pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Message.objects.filter(pk=msg_pk).exists())

    def test_admin_export_group_members(self):
        GroupMember.objects.create(group=self.group, user=self.user, role='member')
        response = self.client.post('/admin/chat/group/', {
            'action': 'export_group_members',
            '_selected_action': [self.group.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

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

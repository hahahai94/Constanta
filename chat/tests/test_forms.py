from django.test import TestCase
from django.contrib.auth import get_user_model
from chat.forms import MessageForm, GroupForm, GroupEditForm, AddMemberForm, ChangeMemberRoleForm
from chat.models import Group, GroupMember

User = get_user_model()


class MessageFormTests(TestCase):
    def test_message_form_valid(self):
        form = MessageForm(data={'content': 'Hello'})
        self.assertTrue(form.is_valid())

    def test_message_form_empty(self):
        form = MessageForm(data={'content': ''})
        self.assertFalse(form.is_valid())


class GroupFormTests(TestCase):
    def test_group_form_valid(self):
        form = GroupForm(data={'name': 'Test Group', 'description': 'desc'})
        self.assertTrue(form.is_valid())

    def test_group_form_no_name(self):
        form = GroupForm(data={'name': ''})
        self.assertFalse(form.is_valid())

    def test_group_edit_form_valid(self):
        form = GroupEditForm(data={'name': 'Edited', 'description': 'new desc'})
        self.assertTrue(form.is_valid())


class AddMemberFormTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='form_owner', password='123')
        self.other = User.objects.create_user(username='form_member', password='456')
        self.group = Group.objects.create(name='Form Group', owner=self.owner)

    def test_add_member_form_initial(self):
        form = AddMemberForm()
        self.assertIn('form_owner', str(form))
        self.assertIn('form_member', str(form))

    def test_add_member_form_excludes_existing(self):
        GroupMember.objects.create(group=self.group, user=self.other, role='member')
        form = AddMemberForm(group=self.group)
        self.assertNotIn('form_member', str(form))


class ChangeMemberRoleFormTests(TestCase):
    def test_role_choices(self):
        form = ChangeMemberRoleForm(data={'role': 'admin'})
        self.assertTrue(form.is_valid())

    def test_invalid_role(self):
        form = ChangeMemberRoleForm(data={'role': 'invalid'})
        self.assertFalse(form.is_valid())

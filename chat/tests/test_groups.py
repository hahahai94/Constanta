from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from chat.models import Group, GroupMember, Message
import json

User = get_user_model()


class GroupTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='boss', password='123')
        self.member = User.objects.create_user(username='worker', password='123')
        self.client.login(username='boss', password='123')

    def test_create_group(self):
        response = self.client.post(reverse('create_group'), {
            'name': 'Test Group'
        })
        self.assertIn(response.status_code, [302, 200])
        self.assertTrue(Group.objects.filter(name='Test Group').exists())

    def test_add_member(self):
        group = Group.objects.create(name='My Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        response = self.client.post(reverse('add_member', args=[group.id]), {
            'username': 'worker'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GroupMember.objects.filter(group=group, user=self.member).exists())

    def test_add_member_not_found(self):
        group = Group.objects.create(name='G', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        response = self.client.post(reverse('add_member', args=[group.id]), {
            'username': 'nonexistent'
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GroupMember.objects.filter(group=group).count() > 1)

    def test_remove_member(self):
        group = Group.objects.create(name='My Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        GroupMember.objects.create(group=group, user=self.member, role='member')
        response = self.client.post(reverse('remove_member', args=[group.id, self.member.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GroupMember.objects.filter(group=group, user=self.member).exists())

    def test_member_cannot_kick(self):
        group = Group.objects.create(name='My Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        GroupMember.objects.create(group=group, user=self.member, role='member')
        self.client.login(username='worker', password='123')
        response = self.client.post(reverse('remove_member', args=[group.id, self.owner.id]))
        self.assertTrue(GroupMember.objects.filter(group=group, user=self.owner).exists())

    def test_remove_member_owner_protected(self):
        group = Group.objects.create(name='G', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        response = self.client.post(reverse('remove_member', args=[group.id, self.owner.id]))
        self.assertEqual(response.status_code, 302)

    def test_group_list(self):
        group = Group.objects.create(name='Visible', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        response = self.client.get(reverse('groups'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible')

    def test_group_chat_access(self):
        group = Group.objects.create(name='Chat Room', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        response = self.client.get(reverse('group_chat', args=[group.id]))
        self.assertEqual(response.status_code, 200)

    def test_group_chat_denied(self):
        group = Group.objects.create(name='Private', owner=self.member)
        response = self.client.get(reverse('group_chat', args=[group.id]))
        self.assertEqual(response.status_code, 302)

    def test_edit_group(self):
        group = Group.objects.create(name='Old Name', owner=self.owner)
        response = self.client.post(reverse('edit_group', args=[group.id]), {
            'name': 'New Name', 'description': 'New desc'
        })
        self.assertEqual(response.status_code, 302)
        group.refresh_from_db()
        self.assertEqual(group.name, 'New Name')

    def test_change_role(self):
        group = Group.objects.create(name='G', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        GroupMember.objects.create(group=group, user=self.member, role='member')
        response = self.client.get(reverse('change_role', args=[group.id, self.member.id, 'admin']))
        self.assertEqual(response.status_code, 302)
        gm = GroupMember.objects.get(group=group, user=self.member)
        self.assertEqual(gm.role, 'admin')

    def test_change_role_not_owner(self):
        group = Group.objects.create(name='G', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        GroupMember.objects.create(group=group, user=self.member, role='member')
        self.client.login(username='worker', password='123')
        response = self.client.get(reverse('change_role', args=[group.id, self.member.id, 'admin']))
        self.assertEqual(response.status_code, 302)
        gm = GroupMember.objects.get(group=group, user=self.member)
        self.assertNotEqual(gm.role, 'admin')

    def test_group_messages_displayed(self):
        group = Group.objects.create(name='Messages', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        Message.objects.create(sender=self.owner, group=group, content='Group message!')
        response = self.client.get(reverse('group_chat', args=[group.id]))
        self.assertContains(response, 'Group message!')

    def test_api_add_member(self):
        group = Group.objects.create(name='API Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        other = User.objects.create_user(username='newguy', password='123')
        response = self.client.post('/api/add-member/', json.dumps({
            'group_id': str(group.id), 'username': 'newguy'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(GroupMember.objects.filter(group=group, user=other).exists())

    def test_api_add_member_not_owner(self):
        group = Group.objects.create(name='API G2', owner=self.member)
        other = User.objects.create_user(username='other', password='123')
        response = self.client.post('/api/add-member/', json.dumps({
            'group_id': str(group.id), 'username': 'other'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_api_remove_member(self):
        group = Group.objects.create(name='API G3', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        GroupMember.objects.create(group=group, user=self.member, role='member')
        response = self.client.post('/api/remove-member/', json.dumps({
            'group_id': str(group.id), 'user_id': self.member.id
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GroupMember.objects.filter(group=group, user=self.member).exists())

    def test_api_set_role(self):
        group = Group.objects.create(name='API G4', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.member, role='member')
        response = self.client.post('/api/set-role/', json.dumps({
            'group_id': str(group.id), 'user_id': self.member.id, 'role': 'admin'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        gm = GroupMember.objects.get(group=group, user=self.member)
        self.assertEqual(gm.role, 'admin')

    def test_create_group_get(self):
        response = self.client.get(reverse('create_group'))
        self.assertEqual(response.status_code, 302)

    def test_create_group_limit_reached(self):
        from django.conf import settings
        for i in range(settings.MAX_GROUPS_PER_USER):
            g = Group.objects.create(name=f'G{i}', owner=self.owner)
            GroupMember.objects.create(group=g, user=self.owner, role='owner')
        response = self.client.post(reverse('create_group'), {'name': 'Overflow'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Group.objects.filter(name='Overflow').exists())

    def test_edit_group_not_owner(self):
        group = Group.objects.create(name='Original', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        self.client.login(username='worker', password='123')
        response = self.client.post(reverse('edit_group', args=[group.id]), {'name': 'Hacked'})
        self.assertEqual(response.status_code, 302)
        group.refresh_from_db()
        self.assertEqual(group.name, 'Original')

    def test_edit_group_with_avatar(self):
        group = Group.objects.create(name='Av Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        from django.core.files.uploadedfile import SimpleUploadedFile
        avatar = SimpleUploadedFile("av.png", b"avatar", content_type="image/png")
        response = self.client.post(reverse('edit_group', args=[group.id]), {
            'name': 'Updated', 'avatar': avatar
        })
        self.assertEqual(response.status_code, 302)
        group.refresh_from_db()
        self.assertEqual(group.name, 'Updated')

    def test_add_member_not_admin(self):
        group = Group.objects.create(name='Locked', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        self.client.login(username='worker', password='123')
        other = User.objects.create_user(username='newguy2', password='123')
        response = self.client.post(reverse('add_member', args=[group.id]), {'username': 'newguy2'})
        self.assertEqual(response.status_code, 302)

    def test_add_member_already_exists(self):
        group = Group.objects.create(name='Existing Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        response = self.client.post(reverse('add_member', args=[group.id]), {
            'username': 'worker'
        })
        self.assertEqual(response.status_code, 302)

    def test_change_role_protect_owner(self):
        group = Group.objects.create(name='Owner Protected', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        response = self.client.get(reverse('change_role', args=[group.id, self.owner.id, 'member']))
        self.assertRedirects(response, reverse('group_chat', args=[group.id]))
        gm = GroupMember.objects.get(group=group, user=self.owner)
        self.assertEqual(gm.role, 'owner')

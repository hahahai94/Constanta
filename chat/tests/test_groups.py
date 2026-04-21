from django.test import TestCase
from django.urls import reverse
from chat.models import User, Group, GroupMember


class GroupTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='boss', password='123')
        self.member = User.objects.create_user(username='worker', password='123')
        self.client.login(username='boss', password='123')

    def test_create_group(self):
        """Тест: Создание новой группы"""
        response = self.client.post(reverse('create_group'), {
            'name': 'Test Group',
            'description': 'For testing only'
        })
        # create_group обычно делает редирект в чат группы
        self.assertIn(response.status_code, [302, 200])
        self.assertTrue(Group.objects.filter(name='Test Group').exists())

    def test_add_member(self):
        """Тест: Добавление участника в группу"""
        group = Group.objects.create(name='My Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')

        response = self.client.post(reverse('add_member', args=[group.id]), {
            'username': 'worker'
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(GroupMember.objects.filter(group=group, user=self.member).exists())

    def test_remove_member(self):
        """Тест: Удаление участника (только админ/владелец)"""
        group = Group.objects.create(name='My Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        GroupMember.objects.create(group=group, user=self.member, role='member')

        response = self.client.post(reverse('remove_member', args=[group.id, self.member.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(GroupMember.objects.filter(group=group, user=self.member).exists())

    def test_member_cannot_kick(self):
        """Тест: Обычный участник НЕ может удалять других"""
        group = Group.objects.create(name='My Group', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.owner, role='owner')
        GroupMember.objects.create(group=group, user=self.member, role='member')

        self.client.login(username='worker', password='123')  # Заходим как воркер

        response = self.client.post(reverse('remove_member', args=[group.id, self.owner.id]))
        # Должно перенаправить обратно или выдать ошибку, но не удалить
        self.assertTrue(GroupMember.objects.filter(group=group, user=self.owner).exists())
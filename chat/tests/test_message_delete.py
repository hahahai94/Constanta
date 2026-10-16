"""Тесты удаления сообщений (problems.md, П-20).

Поле `is_deleted` существовало с самого начала, но не выставлялось нигде, а
фильтры по нему уже стояли — удаление сообщений как функция отсутствовало.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chat.models import Group, GroupMember, Message
from chat.tests.factories import fake_upload

User = get_user_model()


class MessageDeleteTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username='del_sender', password='123')
        self.receiver = User.objects.create_user(username='del_receiver', password='456')
        self.stranger = User.objects.create_user(username='del_stranger', password='789')
        self.client.login(username='del_sender', password='123')
        self.message = Message.objects.create(
            sender=self.sender, receiver=self.receiver, content='удали меня')

    def _delete(self, message=None):
        return self.client.post(
            reverse('api_delete_message', args=[(message or self.message).id]))

    def test_sender_can_delete_own_message(self):
        self.assertEqual(self._delete().status_code, 200)
        self.message.refresh_from_db()
        self.assertTrue(self.message.is_deleted)

    def test_deleted_message_disappears_from_chat_page(self):
        self._delete()
        response = self.client.get(reverse('main'), {'user_id': self.receiver.id})
        self.assertNotContains(response, 'удали меня')

    def test_deleted_message_disappears_from_poll(self):
        self._delete()
        response = self.client.get('/api/poll/', {'user_id': self.receiver.id})
        self.assertEqual(response.json()['count'], 0)

    def test_cannot_delete_foreign_message(self):
        self.client.logout()
        self.client.login(username='del_stranger', password='789')
        response = self._delete()
        self.assertEqual(response.status_code, 403)
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_deleted)

    def test_cannot_delete_twice(self):
        self._delete()
        self.assertEqual(self._delete().status_code, 404)

    def test_get_is_rejected(self):
        response = self.client.get(
            reverse('api_delete_message', args=[self.message.id]))
        self.assertEqual(response.status_code, 405)

    def test_group_member_can_delete_own_message(self):
        group = Group.objects.create(name='DelGroup', owner=self.sender)
        GroupMember.objects.create(group=group, user=self.sender, role='owner')
        message = Message.objects.create(
            sender=self.sender, group=group, content='в группе')
        self.assertEqual(self._delete(message).status_code, 200)

    def test_deleted_attachment_is_not_downloadable(self):
        message = Message.objects.create(
            sender=self.sender, receiver=self.receiver, content='файл',
            attachment=fake_upload('secret.txt', b'top secret', 'text/plain'))
        self.assertEqual(
            self.client.get(reverse('download_attachment', args=[message.id])).status_code,
            200,
        )

        self._delete(message)
        response = self.client.get(reverse('download_attachment', args=[message.id]))
        self.assertEqual(response.status_code, 302)

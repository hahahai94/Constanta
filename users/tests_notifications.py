"""Тесты уведомлений: создание, список, отметка прочтения (problems.md, П-29)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import Notification

User = get_user_model()


class NotificationCreationTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username='note_sender', password='123')
        self.receiver = User.objects.create_user(username='note_receiver', password='456')
        self.client.login(username='note_sender', password='123')

    def test_direct_message_creates_notification(self):
        """П-29: уведомления о личных сообщениях не создавались вообще."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/send/', {
                'user_id': self.receiver.id, 'content': 'привет',
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.filter(
            user=self.receiver, notification_type='message').exists())

    def test_mention_creates_notification(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/send/', {
                'user_id': self.receiver.id,
                'content': f'@{self.receiver.username} привет',
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.filter(
            user=self.receiver, notification_type='mention').exists())

    def test_sender_is_not_notified_about_own_mention(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/api/send/', {
                'user_id': self.receiver.id,
                'content': f'@{self.sender.username} себе',
            })
        self.assertFalse(
            Notification.objects.filter(user=self.sender, notification_type='mention').exists())

    def test_mentions_are_stored_as_ids(self):
        """П-16: в поле остаётся JSON с id, а не разметка."""
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/api/send/', {
                'user_id': self.receiver.id,
                'content': f'@{self.receiver.username}',
            })
        from chat.models import Message
        message = Message.objects.get(sender=self.sender, receiver=self.receiver)
        self.assertNotIn('<span', message.mentions)
        self.assertNotIn('<a ', message.mentions)


class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='note_user', password='123')
        self.client.login(username='note_user', password='123')
        self.note = Notification.objects.create(
            user=self.user, notification_type='mention',
            title='Упоминание', message='вас упомянули', url='/',
        )

    def test_list_shows_notifications(self):
        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'вас упомянули')

    def test_unread_counter_is_exposed_to_templates(self):
        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.context['unread_notifications_count'], 1)

    def test_counter_is_zero_for_anonymous(self):
        self.client.logout()
        response = self.client.get(reverse('auth'))
        self.assertEqual(response.context['unread_notifications_count'], 0)

    def test_open_marks_read_and_redirects(self):
        response = self.client.get(reverse('notification_open', args=[self.note.id]))
        self.assertEqual(response.status_code, 302)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_read)

    def test_open_rejects_foreign_notification(self):
        other = User.objects.create_user(username='note_other', password='123')
        foreign = Notification.objects.create(
            user=other, notification_type='message', title='t', message='m')
        response = self.client.get(reverse('notification_open', args=[foreign.id]))
        self.assertEqual(response.status_code, 404)

    def test_open_refuses_external_redirect(self):
        self.note.url = 'https://evil.example/steal'
        self.note.save(update_fields=['url'])
        response = self.client.get(reverse('notification_open', args=[self.note.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('main'))

    def test_mark_all_read(self):
        response = self.client.post(reverse('notifications_read_all'))
        self.assertEqual(response.status_code, 302)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_read)

    def test_mark_all_read_rejects_get(self):
        response = self.client.get(reverse('notifications_read_all'))
        self.assertEqual(response.status_code, 405)

    def test_anonymous_is_redirected(self):
        self.client.logout()
        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.status_code, 302)

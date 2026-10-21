from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from chat.models import Message
from chat.tests.factories import fake_upload, image_upload

import re
from datetime import timedelta

User = get_user_model()


class PrivateChatTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='alice', password='123')
        self.user2 = User.objects.create_user(username='bob', password='123')
        self.client.login(username='alice', password='123')

    def test_send_text_message(self):
        """Тест: Отправка текстового сообщения через API"""
        response = self.client.post('/api/send/', {
            'user_id': self.user2.id,
            'content': 'Привет, Боб!'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('html', data)
        self.assertIn('message_id', data)

        # Проверка БД
        msg = Message.objects.get(sender=self.user1, receiver=self.user2)
        self.assertEqual(msg.content, 'Привет, Боб!')

    def test_send_file_message(self):
        """Тест: Отправка сообщения с файлом (картинкой)"""
        uploaded_file = image_upload('test.png')

        response = self.client.post('/api/send/', {
            'user_id': self.user2.id,
            'content': 'Смотри фотку',
            'attachment': uploaded_file
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('html', data)
        self.assertIn('message_id', data)

        msg = Message.objects.get(sender=self.user1, receiver=self.user2)
        self.assertTrue(msg.attachment)
        self.assertEqual(msg.attachment_type, 'image')

    def test_send_fake_image_rejected(self):
        """Файл, который только выдаёт себя за картинку, не принимается.

        Регрессия к tasks.md:13: валидация должна проверять файл целиком, а не
        доверять Content-Type или первым байтам.
        """
        response = self.client.post('/api/send/', {
            'user_id': self.user2.id,
            'content': 'Подделка',
            'attachment': fake_upload('fake.png', b'fake image content'),
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Message.objects.filter(content='Подделка').exists())

    def test_view_chat_page(self):
        """Тест: Страница чата грузится (200)"""
        response = self.client.get(f'/?user_id={self.user2.id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user2.username)

    def test_chat_header_formats_last_seen(self):
        self.user2.last_seen = timezone.now() - timedelta(hours=2)
        self.user2.save(update_fields=['last_seen'])

        response = self.client.get(f'/?user_id={self.user2.id}')
        self.assertContains(response, '2 часа')
        self.assertNotContains(response, 'назад')


class ReplyButtonRenderingTests(TestCase):
    """П-2: имя пользователя не должно попадать в исполняемый JS-код.

    Смена логина теперь отклоняет опасные символы, но шаблон обязан быть
    безопасным и для уже существующих «плохих» логинов, поэтому пользователь
    создаётся в обход формы.
    """

    PAYLOAD = "a');alert(1);//"
    TEMPLATES = ('parts/message_list.html', 'parts/group_message_list.html')
    HANDLER_RE = re.compile(r'\son[a-z]+\s*=\s*"([^"]*)"')

    def setUp(self):
        self.sender = User.objects.create_user(username=self.PAYLOAD, password='123')
        self.receiver = User.objects.create_user(username='reply_receiver', password='123')
        self.message = Message.objects.create(
            sender=self.sender, receiver=self.receiver, content='hello'
        )

    def _render(self, template, message=None):
        from django.template.loader import render_to_string
        return render_to_string(template, {
            'messages': [message or self.message],
            'user': self.receiver,
            'request': None,
        })

    def test_username_never_appears_inside_an_inline_handler(self):
        # берём сообщение с цитатой, раньше там был inline-обработчик
        reply = Message.objects.create(
            sender=self.receiver, receiver=self.sender,
            content='original text', reply_to=self.message,
        )
        for template in self.TEMPLATES:
            with self.subTest(template=template):
                markup = self._render(template, message=reply)
                values = self.HANDLER_RE.findall(markup)
                self.assertEqual(values, [], 'inline-обработчики запрещены CSP')

    def test_reply_button_has_no_inline_handler(self):
        for template in self.TEMPLATES:
            with self.subTest(template=template):
                markup = self._render(template)
                self.assertIn('data-reply-author', markup)
                self.assertIn('data-reply-id', markup)
                button = markup.split('class="reply-btn"', 1)[1].split('>', 1)[0]
                self.assertNotIn('onclick', button)

    def test_payload_is_html_escaped_in_the_data_attribute(self):
        markup = self._render('parts/message_list.html')
        self.assertIn('&#x27;', markup)
        self.assertNotIn(self.PAYLOAD, markup)

    def test_reply_quote_passes_uuid_through_data_attribute(self):
        reply = Message.objects.create(
            sender=self.receiver, receiver=self.sender,
            content='original text', reply_to=self.message,
        )
        for template in self.TEMPLATES:
            with self.subTest(template=template):
                markup = self._render(template, message=reply)
                self.assertNotIn('onclick', markup)
                match = re.search(r'data-scroll-to="([^"]+)"', markup)
                self.assertIsNotNone(match)
                self.assertRegex(match.group(1), r'^[0-9a-f-]{36}$')

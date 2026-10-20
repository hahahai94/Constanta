"""Проверка, что шаблоны не отдают собственную разметку в HTML.

Регрессия: короткая форма комментария `{# ... #}` в Django работает только в
пределах одной строки. Многострочный вариант комментарием не считается и
печатается прямо на странице — так и произошло в `base.html` при правке П-38,
и надпись была видна над шапкой страницы входа.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class TemplateSyntaxLeakTests(TestCase):
    ANONYMOUS_URLS = ('/auth/', '/robots.txt', '/llms.txt', '/sitemap.xml')
    AUTHENTICATED_VIEWS = (
        'main', 'profile', 'users_catalog', 'task_lists', 'notifications',
        'groups', 'channel_list',
    )
    MARKERS = ('{#', '{%', '{{')

    def _assert_clean(self, url, response):
        body = response.content.decode('utf-8', errors='replace')
        for marker in self.MARKERS:
            self.assertNotIn(
                marker, body,
                f'{url} отдаёт в HTML шаблонный синтаксис {marker!r}')

    def test_anonymous_pages_have_no_template_syntax(self):
        for url in self.ANONYMOUS_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self._assert_clean(url, response)

    def test_authenticated_pages_have_no_template_syntax(self):
        User.objects.create_user(username='syntax_user', password='pass1234')
        self.client.login(username='syntax_user', password='pass1234')

        for name in self.AUTHENTICATED_VIEWS:
            url = reverse(name)
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self._assert_clean(url, response)

    def test_csrf_meta_is_still_present(self):
        """Правка комментария не должна была убрать сам тег."""
        response = self.client.get('/auth/')
        self.assertContains(response, 'name="csrf-token"')


class ContentSecurityPolicyTests(TestCase):
    INLINE_SCRIPT = re.compile(r'<script(?![^>]*\bsrc=)', re.IGNORECASE)
    INLINE_HANDLER = re.compile(r'\son[a-z]+\s*=', re.IGNORECASE)

    def test_script_src_allows_no_inline_code(self):
        response = self.client.get('/auth/')
        self.assertEqual(response.status_code, 200)

        directives = [
            item.strip()
            for item in response['Content-Security-Policy'].split(';')
            if item.strip()
        ]
        script_src = next(
            item for item in directives if item.startswith('script-src'))

        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertIn("'self'", script_src)

    def test_templates_have_no_inline_scripts_or_handlers(self):
        templates = Path(settings.BASE_DIR) / 'templates'
        offenders = []

        for path in templates.rglob('*.html'):
            source = path.read_text(encoding='utf-8')
            if self.INLINE_SCRIPT.search(source):
                offenders.append(f'{path.name}: inline <script>')
            if self.INLINE_HANDLER.search(source):
                offenders.append(f'{path.name}: inline event handler')

        self.assertEqual(offenders, [], '\n'.join(offenders))

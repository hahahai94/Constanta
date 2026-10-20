"""Ошибки форм показываются без служебных имён полей."""

from django import forms
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from users.utils import form_error_messages


class LabeledForm(forms.Form):
    username = forms.CharField(label='Логин')


class NonFieldForm(forms.Form):
    value = forms.CharField()

    def clean(self):
        raise ValidationError('Общая ошибка формы')


class FormErrorMessageTests(SimpleTestCase):
    def test_field_label_replaces_machine_name(self):
        form = LabeledForm(data={})
        messages = form_error_messages(form)
        self.assertTrue(messages)
        self.assertTrue(messages[0].startswith('Логин:'))
        self.assertNotIn('username:', messages[0])

    def test_non_field_error_has_no_all_prefix(self):
        form = NonFieldForm(data={'value': 'ok'})
        messages = form_error_messages(form)
        self.assertEqual(messages, ['Общая ошибка формы'])

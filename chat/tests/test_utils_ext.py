from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from chat.models import Message
from chat.utils import get_file_upload_path, get_file_hash_from_path, get_original_filename_from_hash
import io

User = get_user_model()


class UtilsPathTests(TestCase):
    def test_get_file_upload_path(self):
        class FakeInstance:
            attachment = io.BytesIO(b'data')
            sender = type('obj', (object,), {'id': 1})()

        path = get_file_upload_path(FakeInstance(), 'test.pdf', file_hash='a1b2c3d4')
        self.assertIn('a1/', path)  # uses first 2 chars of hash as subdir
        self.assertIn('a1b2c3d4', path)
        self.assertTrue(path.endswith('.pdf'))

    def test_get_file_hash_from_path(self):
        result = get_file_hash_from_path('attachments/a1/a1b2c3d4e5.pdf')
        self.assertEqual(result, 'a1b2c3d4e5')

    def test_get_original_filename_from_hash(self):
        result = get_original_filename_from_hash('abc123', 'original.pdf')
        self.assertEqual(result, 'original.pdf')


class UtilsFormatMentionTests(TestCase):
    def test_format_mention_escaped(self):
        from chat.utils import format_mention_content
        result = format_mention_content('&lt;span class="mention"&gt;@user&lt;/span&gt;')
        self.assertIn('mention', result)

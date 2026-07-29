from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from chat.models import Message, Group, GroupMember, _attachment_upload_to
from chat.utils import generate_file_hash
import io
import os


User = get_user_model()


class MessageModelTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username='sender', password='123')
        self.receiver = User.objects.create_user(username='receiver', password='123')

    def test_create_message(self):
        msg = Message.objects.create(
            sender=self.sender, receiver=self.receiver,
            content='Hello!'
        )
        self.assertEqual(str(msg), 'sender -> Hello!')

    def test_get_attachment_url_none(self):
        msg = Message.objects.create(
            sender=self.sender, receiver=self.receiver,
            content='No attach'
        )
        self.assertIsNone(msg.get_attachment_url())

    def test_get_attachment_name_none(self):
        msg = Message.objects.create(
            sender=self.sender, receiver=self.receiver,
            content='No name'
        )
        self.assertIsNone(msg.get_attachment_name())

    def test_message_with_attachment(self):
        file = SimpleUploadedFile("test.png", io.BytesIO(b'png').read(), content_type="image/png")
        msg = Message.objects.create(
            sender=self.sender, receiver=self.receiver,
            content='With file', attachment=file
        )
        self.assertIsNotNone(msg.get_attachment_url())
        self.assertIsNotNone(msg.get_attachment_name())

    def test_reply_to_message(self):
        original = Message.objects.create(
            sender=self.sender, receiver=self.receiver,
            content='Original'
        )
        reply = Message.objects.create(
            sender=self.receiver, receiver=self.sender,
            content='Reply', reply_to=original
        )
        self.assertEqual(reply.reply_to, original)

    def test_soft_delete_message(self):
        msg = Message.objects.create(
            sender=self.sender, receiver=self.receiver,
            content='To be deleted'
        )
        msg.is_deleted = True
        msg.save()
        self.assertTrue(Message.objects.get(id=msg.id).is_deleted)


class GroupModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='gowner', password='123')
        self.member_user = User.objects.create_user(username='gmember', password='123')

    def test_create_group(self):
        group = Group.objects.create(name='Test Group', owner=self.owner)
        self.assertEqual(str(group), 'Test Group')

    def test_group_get_avatar_default(self):
        group = Group.objects.create(name='No Avatar', owner=self.owner)
        self.assertEqual(group.get_avatar_url(), '/static/default_group_avatar.png')

    def test_group_get_avatar_with_avatar(self):
        file = SimpleUploadedFile("group_av.png", b"x", content_type="image/png")
        group = Group.objects.create(name='Has Avatar', owner=self.owner, avatar=file)
        self.assertTrue(group.get_avatar_url().startswith('/media/'))

    def test_is_owner(self):
        group = Group.objects.create(name='Owned', owner=self.owner)
        self.assertTrue(group.is_owner(self.owner))
        self.assertFalse(group.is_owner(self.member_user))

    def test_is_member(self):
        group = Group.objects.create(name='Membership', owner=self.owner)
        GroupMember.objects.create(group=group, user=self.member_user, role='member')
        self.assertTrue(group.is_member(self.member_user))
        self.assertFalse(group.is_member(self.owner))  # owner not in member list

    def test_group_member_str(self):
        group = Group.objects.create(name='Str Test', owner=self.owner)
        gm = GroupMember.objects.create(group=group, user=self.member_user, role='admin')
        self.assertIn('gmember', str(gm))
        self.assertIn('admin', str(gm))

    def test_group_member_can_kick(self):
        group = Group.objects.create(name='Kick Test', owner=self.owner)
        gm_owner = GroupMember.objects.create(group=group, user=self.owner, role='owner')
        gm_admin = GroupMember.objects.create(group=group, user=self.member_user, role='admin')
        self.assertTrue(gm_owner.can_kick())
        self.assertTrue(gm_admin.can_kick())

    def test_group_member_can_change_role(self):
        group = Group.objects.create(name='Role Test', owner=self.owner)
        gm = GroupMember.objects.create(group=group, user=self.owner, role='owner')
        gm_member = GroupMember.objects.create(group=group, user=self.member_user, role='member')
        self.assertTrue(gm.can_change_role())
        self.assertFalse(gm_member.can_change_role())

    def test_message_str(self):
        group = Group.objects.create(name='Group Msg', owner=self.owner)
        msg = Message.objects.create(
            sender=self.owner, group=group, content='Group hello'
        )
        self.assertIn('Group hello', str(msg))


class FileHashTests(TestCase):
    def test_file_hash_without_chunks(self):
        class FakeFile:
            def __init__(self, data):
                self._data = data
                self._pos = 0
            def seek(self, pos):
                self._pos = pos
            def read(self, size=65536):
                chunk = self._data[self._pos:self._pos+size]
                self._pos += len(chunk)
                return chunk

        result = generate_file_hash(FakeFile(b'hash me'), user_id=1)
        self.assertEqual(len(result), 64)

    def test_attachment_upload_to_without_hash(self):
        class FakeMsg:
            attachment_hash = ''
            attachment = SimpleUploadedFile("upload.txt", b"content")
            sender = type('obj', (object,), {'id': 1})()

        path = _attachment_upload_to(FakeMsg(), "upload.txt")
        self.assertIn(os.path.join('attachments'), path)
        self.assertTrue(path.endswith('.txt'))


class MessageGetAttachmentNameTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username='name_tester', password='123')

    def test_get_attachment_name_with_attachment_only(self):
        file = SimpleUploadedFile("onlyfile.pdf", b"pdf content", content_type="application/pdf")
        msg = Message.objects.create(
            sender=self.sender, receiver=self.sender,
            content='Has file', attachment=file
        )
        msg.attachment_original_name = ''
        name = msg.get_attachment_name()
        self.assertIsNotNone(name)
        self.assertIn('.pdf', name)

    def test_get_attachment_name_no_attachment_no_name(self):
        msg = Message.objects.create(
            sender=self.sender, receiver=self.sender,
            content='Nothing'
        )
        self.assertIsNone(msg.get_attachment_name())


class MessageSaveTests(TestCase):
    def test_save_sets_original_name(self):
        sender = User.objects.create_user(username='attacher', password='123')
        file = SimpleUploadedFile("document.pdf", b"pdf content", content_type="application/pdf")
        msg = Message.objects.create(
            sender=sender, receiver=sender,
            content='PDF file', attachment=file
        )
        self.assertEqual(msg.attachment_original_name, 'document.pdf')

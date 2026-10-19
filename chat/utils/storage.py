from django.core.files.storage import FileSystemStorage


class AttachmentStorage(FileSystemStorage):
    """Хранилище вложений с дедупликацией по детерминированному имени.

    Имя файла — это хеш содержимого и отправителя, поэтому повторная загрузка
    того же файла не должна создавать копию с суффиксом ``_1``.
    """

    def save(self, name, content, max_length=None):
        name = str(name).replace("\\", "/")
        if self.exists(name):
            return name
        return super().save(name, content, max_length=max_length)


attachment_storage = AttachmentStorage()

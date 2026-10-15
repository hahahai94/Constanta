"""Общие тестовые фабрики для приложения chat."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile


def make_image_bytes(fmt='PNG', size=(2, 2), color=(255, 0, 0)):
    """Возвращает байты корректного изображения заданного формата."""
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, format=fmt)
    return buffer.getvalue()


def make_png(size=(2, 2)):
    """Байты корректного PNG."""
    return make_image_bytes('PNG', size)


def image_upload(name='image.png', fmt='PNG', size=(2, 2), content_type='image/png'):
    """Загруженный файл с реальным изображением внутри."""
    return SimpleUploadedFile(name, make_image_bytes(fmt, size), content_type=content_type)


def fake_upload(name, content=b'not an image', content_type='image/png'):
    """Загруженный файл, который только выдаёт себя за изображение."""
    if isinstance(content, str):
        content = content.encode()
    return SimpleUploadedFile(name, content, content_type=content_type)

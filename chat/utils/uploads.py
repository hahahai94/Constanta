"""Единая валидация и нормализация загружаемых файлов.

Правила, на которых держится безопасность загрузок (problems.md, П-3):

* тип файла определяется по содержимому (сигнатуры + Pillow), а не по
  заявленному клиентом ``Content-Type``;
* расширение сохранённого файла всегда выводится из реального содержимого,
  поэтому положить под ``/media/`` файл с расширением ``.html``/``.svg`` и
  получить его обратно с исполняемым ``Content-Type`` невозможно;
* изображения проверяются целиком и ограничены по размеру и числу пикселей.
"""

import os
import uuid
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image

# Форматы изображений, которые мы принимаем, и расширение для сохранения.
IMAGE_EXTENSIONS = {
    'JPEG': '.jpg',
    'PNG': '.png',
    'GIF': '.gif',
    'WEBP': '.webp',
    'BMP': '.bmp',
}

# Аудио/видео, которые помечаются как «голосовое сообщение».
MEDIA_EXTENSIONS = {
    'audio/ogg': '.ogg',
    'audio/opus': '.opus',
    'audio/wav': '.wav',
    'audio/x-wav': '.wav',
    'audio/vnd.wave': '.wav',
    'audio/mpeg': '.mp3',
    'audio/mp3': '.mp3',
    'audio/mp4': '.m4a',
    'audio/x-m4a': '.m4a',
    'audio/aac': '.aac',
    'audio/flac': '.flac',
    'audio/webm': '.webm',
    'video/webm': '.webm',
}

# Расширения, которые безопасно отдавать статикой: браузер не интерпретирует
# их как разметку или скрипт. `.svg`, `.html`, `.xml`, `.js` сюда намеренно не
# входят — они исполняются в origin приложения и дали бы stored XSS.
SAFE_DOCUMENT_EXTENSIONS = frozenset({
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.rtf', '.txt', '.csv', '.md', '.json',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
    '.mp3', '.ogg', '.oga', '.opus', '.wav', '.flac', '.m4a', '.aac',
    '.mp4', '.mov', '.avi', '.mkv', '.webm',
})

FALLBACK_EXTENSION = '.bin'

# 30 Мп — заметно ниже порога Pillow (89 Мп), чтобы отсекать «бомбы».
MAX_IMAGE_PIXELS = 30_000_000

# `b'BM'` — слабая двухбайтовая сигнатура BMP, поэтому она проверяется после
# остальных. Ложное срабатывание безопасно: изображение всё равно пройдёт
# проверку Pillow, а не-изображение будет отклонено.
_IMAGE_MAGIC = (
    b'\xff\xd8\xff',        # JPEG
    b'\x89PNG\r\n\x1a\n',   # PNG
    b'GIF87a',
    b'GIF89a',
    b'\x42\x4d',            # BMP
)

_AUDIO_MAGIC = {
    b'OggS': '.ogg',
    b'fLaC': '.flac',
    b'ID3': '.mp3',
    b'\xff\xfb': '.mp3',
    b'\x1a\x45\xdf\xa3': '.webm',   # Matroska/WebM
}


def read_all(uploaded_file):
    """Читает файл целиком и возвращает указатель в начало."""
    data = uploaded_file.read()
    uploaded_file.seek(0)
    return data


def detect_attachment_type(data, content_type=''):
    """Определяет тип по содержимому: ``'image'``, ``'voice'`` или ``'file'``.

    RIFF-контейнеры различаются по идентификатору на смещении 8. Раньше
    ``b'RIFF'`` одновременно означал и ``image/webp``, и ``audio/wav``, причём
    проверка изображений шла первой, поэтому любой WAV определялся как
    изображение и отклонялся (problems.md, П-10).
    """
    if data.startswith(b'RIFF'):
        container = data[8:12]
        if container == b'WEBP':
            return 'image'
        if container == b'WAVE':
            return 'voice'
        return 'file'

    # Аудио проверяется раньше изображений: пересечений у сигнатур нет, но так
    # слабая сигнатура ``b'BM'`` не может перехватить чужой контейнер.
    for magic in _AUDIO_MAGIC:
        if data.startswith(magic):
            return 'voice'

    for magic in _IMAGE_MAGIC:
        if data.startswith(magic):
            return 'image'

    declared = (content_type or '').lower()
    if declared.startswith(('audio/', 'video/')):
        return 'voice'
    if declared.startswith('image/'):
        return 'image'
    return 'file'


def validate_image_bytes(data, max_pixels=MAX_IMAGE_PIXELS):
    """Проверяет изображение целиком.

    Возвращает ``(format, width, height)``. Бросает ``ValidationError``, если
    файл не является изображением или слишком велик по числу пикселей.
    """
    try:
        # `verify()` проверяет файл полностью, но делает объект непригодным,
        # поэтому для чтения метаданных файл открывается заново.
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image_format = (image.format or '').upper()
            width, height = image.size
    except Image.DecompressionBombError as exc:
        raise ValidationError('Слишком большое изображение') from exc
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError('Файл не является валидным изображением') from exc

    if width * height > max_pixels:
        raise ValidationError('Слишком большое изображение')
    return image_format, width, height


def image_extension(image_format):
    """Безопасное расширение для формата Pillow; иначе — ``.bin``."""
    return IMAGE_EXTENSIONS.get((image_format or '').upper(), FALLBACK_EXTENSION)


def audio_extension_from_magic(data):
    for magic, extension in _AUDIO_MAGIC.items():
        if data.startswith(magic):
            return extension
    return '.ogg'


def safe_document_extension(filename):
    """Расширение документа из белого списка; иначе — ``.bin``."""
    extension = os.path.splitext(filename or '')[1].lower()
    if extension in SAFE_DOCUMENT_EXTENSIONS:
        return extension
    return FALLBACK_EXTENSION


def normalize_upload(uploaded_file, *, max_bytes=None, max_pixels=MAX_IMAGE_PIXELS):
    """Проверяет вложение и возвращает ``(attachment_type, extension)``.

    Расширение выводится из содержимого, поэтому сохранить ``.html`` под видом
    картинки или документа нельзя. Бросает ``ValidationError``.
    """
    limit = settings.FILE_UPLOAD_MAX_MEMORY_SIZE if max_bytes is None else max_bytes
    if uploaded_file.size > limit:
        raise ValidationError('Файл слишком большой')

    data = read_all(uploaded_file)
    declared = getattr(uploaded_file, 'content_type', '') or ''
    attachment_type = detect_attachment_type(data, declared)

    if attachment_type == 'image':
        image_format, _, _ = validate_image_bytes(data, max_pixels)
        if image_format not in IMAGE_EXTENSIONS:
            raise ValidationError('Неподдерживаемый формат изображения')
        return 'image', IMAGE_EXTENSIONS[image_format]

    if attachment_type == 'voice':
        extension = MEDIA_EXTENSIONS.get(declared.lower())
        if extension is None:
            extension = audio_extension_from_magic(data)
        return 'voice', extension

    return 'file', safe_document_extension(uploaded_file.name)


def normalize_avatar(uploaded_file, *, max_bytes=None, max_pixels=MAX_IMAGE_PIXELS):
    """Проверяет аватар и приводит его имя к безопасному виду.

    Возвращает исходное имя файла. Бросает ``ValidationError``.
    """
    original_name = uploaded_file.name
    limit = settings.FILE_UPLOAD_MAX_MEMORY_SIZE if max_bytes is None else max_bytes
    if uploaded_file.size > limit:
        raise ValidationError('Файл слишком большой')

    data = read_all(uploaded_file)
    try:
        image_format, _, _ = validate_image_bytes(data, max_pixels)
    except ValidationError as exc:
        reason = exc.messages[0] if exc.messages else 'не изображение'
        raise ValidationError(
            f'Аватар должен быть изображением (JPEG, PNG, GIF, WebP, BMP): {reason}'
        ) from exc

    extension = IMAGE_EXTENSIONS.get(image_format)
    if extension is None:
        raise ValidationError('Неподдерживаемый формат изображения')

    # Имя перезаписывается: сохранённое расширение не должно зависеть от того,
    # что прислал клиент.
    uploaded_file.name = f"avatar{extension}"
    return original_name


def _avatar_storage_path(subdir, instance):
    """Путь для аватара: расширение выводится из содержимого файла."""
    field_file = getattr(instance, 'avatar', None)
    image_format = ''
    if field_file is not None:
        try:
            data = field_file.read()
            field_file.seek(0)
            image_format, _, _ = validate_image_bytes(data)
        except Exception:
            # Не изображение — сохраняем с нейтральным расширением, чтобы файл
            # никогда не отдавался как разметка или скрипт.
            image_format = ''
    return os.path.join(subdir, f"{uuid.uuid4().hex}{image_extension(image_format)}")


def group_avatar_upload_to(instance, filename):
    """``upload_to`` для ``Group.avatar`` (см. П-3)."""
    return _avatar_storage_path('group_avatars', instance)


def channel_avatar_upload_to(instance, filename):
    """``upload_to`` для ``Channel.avatar`` (см. П-3)."""
    return _avatar_storage_path('channel_avatars', instance)

import hashlib
import os
import re
import json
from datetime import datetime
from django.conf import settings


# ==================== ХЕШИРОВАНИЕ ФАЙЛОВ ====================

def generate_file_hash(file, user_id, timestamp=None):
    """
    Генерирует уникальный хеш для файла на основе:
    - Содержимого файла
    - ID пользователя
    - Времени загрузки
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    hasher = hashlib.sha256()
    if hasattr(file, 'chunks'):
        for chunk in file.chunks():
            hasher.update(chunk)
    else:
        while True:
            chunk = file.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    file.seek(0)
    hasher.update(f"{user_id}{timestamp}".encode('utf-8'))
    return hasher.hexdigest()


def get_file_upload_path(instance, filename, file_hash=None):
    """
    Генерирует путь для сохранения файла:
    media/attachments/{first_2_chars}/{full_hash}_{original_ext}

    Пример: media/attachments/a3/a3f5d8e9..._document.pdf
    """
    if file_hash is None:
        file_hash = generate_file_hash(instance.attachment, instance.sender.id)

    # Берём первые 2 символа хеша для подпапки
    subdir = file_hash[:2]

    # Получаем расширение оригинального файла
    ext = os.path.splitext(filename)[1].lower()

    # Формируем имя файла
    new_filename = f"{file_hash}{ext}"

    return os.path.join('attachments', subdir, new_filename)


def get_file_hash_from_path(file_path):
    """
    Извлекает хеш из пути к файлу
    """
    filename = os.path.basename(file_path)
    file_hash = os.path.splitext(filename)[0]
    return file_hash


def get_original_filename_from_hash(file_hash, original_name):
    """
    Возвращает оригинальное имя файла для отображения
    (храним в БД, не в пути)
    """
    return original_name


# ==================== УПОМИНАНИЯ (@all, @username) ====================

def parse_mentions(content, group=None, receiver=None):
    """
    Находит все @упоминания в тексте и возвращает:
    - Обработанный текст с HTML-ссылками
    - Список ID упомянутых пользователей
    """
    mentioned_user_ids = []

    # Обработка @all (только для групп)
    if group and '@all' in content:
        from .models import GroupMember
        members = GroupMember.objects.filter(group=group).values_list('user_id', flat=True)
        mentioned_user_ids.extend(members)
        content = re.sub(
            r'@all\b',
            '<span class="mention mention-all">@all</span>',
            content
        )

    from django.contrib.auth import get_user_model
    from django.utils.html import format_html
    User = get_user_model()

    # Обработка @username
    pattern = r'@(\w+)'
    matches = re.findall(pattern, content)
    usernames = [m for m in matches if m != 'all']

    if usernames:
        users_map = {u.username: u for u in User.objects.filter(username__in=usernames)}
        for username in usernames:
            user = users_map.get(username)
            if user and user.id not in mentioned_user_ids:
                mentioned_user_ids.append(user.id)
                link = format_html(
                    '<a href="/user/{}/" class="mention" target="_blank">@{}</a>',
                    username, username
                )
                content = re.sub(
                    f'@{username}\\b',
                    str(link),
                    content
                )

    return content, list(set(mentioned_user_ids))


def format_mention_content(content):
    """
    Безопасно форматирует контент с упоминаниями для отображения
    """
    import html
    content = html.escape(content)

    # Но оставляем наши mention-теги
    content = re.sub(
        r'&lt;span class="mention.*?&gt;@all&lt;/span&gt;',
        '<span class="mention mention-all">@all</span>',
        content
    )
    content = re.sub(
        r'&lt;a href=".*?" class="mention".*?&gt;@(\w+)&lt;/a&gt;',
        r'<a href="\1" class="mention">@\1</a>',
        content
    )

    return content


# ==================== УВЕДОМЛЕНИЯ ====================

def create_notification(user, notification_type, title, message, url='', related_message=None):
    from users.models import Notification
    from django.db import transaction
    transaction.on_commit(lambda: Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url,
        related_message=related_message
    ))

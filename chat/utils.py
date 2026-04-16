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

    # Читаем содержимое файла
    file_content = file.read()
    file.seek(0)  # Возвращаем указатель в начало

    # Создаём хеш из содержимого + метаданных
    hash_input = f"{file_content.hex()}{user_id}{timestamp}".encode('utf-8')
    file_hash = hashlib.sha256(hash_input).hexdigest()

    return file_hash


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

    # 🔹 Обработка @all (только для групп)
    if group and '@all' in content:
        from .models import GroupMember
        members = GroupMember.objects.filter(group=group).values_list('user_id', flat=True)
        mentioned_user_ids.extend(members)
        # Заменяем @all на HTML
        content = re.sub(
            r'@all\b',
            '<span class="mention mention-all">@all</span>',
            content
        )

    # 🔹 Обработка @username
    pattern = r'@(\w+)'
    matches = re.findall(pattern, content)

    for username in matches:
        if username == 'all':
            continue  # Уже обработали

        from .models import User
        try:
            user = User.objects.get(username=username)
            if user.id not in mentioned_user_ids:
                mentioned_user_ids.append(user.id)

            # Заменяем @username на HTML с ссылкой
            content = re.sub(
                f'@{username}\\b',
                f'<a href="/user/{username}/" class="mention" target="_blank">@{username}</a>',
                content
            )
        except User.DoesNotExist:
            pass

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


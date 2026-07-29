import hashlib
import os
from datetime import datetime


def generate_file_hash(file, user_id, timestamp=None):
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
    if file_hash is None:
        file_hash = generate_file_hash(instance.attachment, instance.sender.id)
    subdir = file_hash[:2]
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f"{file_hash}{ext}"
    return os.path.join('attachments', subdir, new_filename)


def get_file_hash_from_path(file_path):
    filename = os.path.basename(file_path)
    file_hash = os.path.splitext(filename)[0]
    return file_hash


def get_original_filename_from_hash(file_hash, original_name):
    return original_name

from django.core.exceptions import ValidationError

NAME_MAX_LENGTH = 100


def normalize_conversation_name(value):
    name = (value or '').strip()
    if not name:
        raise ValidationError('Название не может быть пустым')
    if len(name) > NAME_MAX_LENGTH:
        raise ValidationError(
            f'Название не может быть длиннее {NAME_MAX_LENGTH} символов')
    return name

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class CustomAuthBackend(ModelBackend):
    """
    Кастомный бэкенд который НЕ проверяет is_active
    Чтобы мы могли показать экран бана
    """
    def user_can_authenticate(self, user):
        # Разрешаем вход даже неактивным пользователям
        # Проверку на бан делаем вручную во views
        return True
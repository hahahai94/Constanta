from django.contrib.auth.backends import ModelBackend


class CustomAuthBackend(ModelBackend):
    """Не пускает неактивные и забаненные аккаунты.

    Раньше проверялся только ``is_active``, поэтому бан (``banned_at``) не
    влиял ни на что: забаненный пользователь и входил, и продолжал работать
    (problems.md, П-4). Проверка живёт именно здесь, а не в отдельном
    бэкенде, потому что ``AUTHENTICATION_BACKENDS`` перебирает их по очереди:
    любой другой бэкенд с той же проверкой должен её разделять.
    """

    def user_can_authenticate(self, user):
        return bool(user.is_active and getattr(user, 'banned_at', None) is None)

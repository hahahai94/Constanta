from django.contrib.auth.backends import ModelBackend


class CustomAuthBackend(ModelBackend):
    def user_can_authenticate(self, user):
        return user.is_active

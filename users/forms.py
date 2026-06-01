from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from users.models import User


class RegistrationForm(UserCreationForm):
    nick = forms.CharField(max_length=50, required=False, label="Никнейм")

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')


class LoginForm(AuthenticationForm):
    pass


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['nick', 'bio', 'avatar']
        widgets = {
            'nick': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }


class ChangeUsernameForm(forms.Form):
    username = forms.CharField(max_length=150, label="Новый логин")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exclude(id=self.user.id).exists():
            raise forms.ValidationError("Этот логин уже занят")
        return username


class ChangePasswordForm(PasswordChangeForm):
    new_password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    new_password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )


class AddFriendForm(forms.Form):
    friend_username = forms.CharField(label="Никнейм или username", max_length=150)

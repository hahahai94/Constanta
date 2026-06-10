# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from users.models import User


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'nick', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Логин'
        self.fields['nick'].label = 'Никнейм'
        self.fields['nick'].required = False
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Повторите пароль'


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['nick', 'email', 'avatar', 'bio']
        widgets = {
            'nick': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
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

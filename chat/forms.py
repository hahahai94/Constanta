from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from .models import User, Message, Group, GroupMember


class RegistrationForm(UserCreationForm):
    nick = forms.CharField(max_length=50, required=False, label="Никнейм")

    class Meta:
        model = User
        fields = ("username", "nick", "email")


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


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 1,
                'placeholder': 'Сообщение...',
                'class': 'form-control',
                'id': 'message-content'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'id': 'message-attachment',
                'accept': 'image/*,audio/*,.pdf,.doc,.docx,.txt'
            }),
        }


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'description', 'avatar']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }


# 🔹 ДОБАВЬ ЭТУ ФОРМУ (после GroupForm)
class GroupEditForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'description', 'avatar']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }


class AddMemberForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label="Выберите пользователя",
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="── Выберите пользователя ──"
    )

    def __init__(self, *args, **kwargs):
        # 🔹 Извлекаем group из kwargs
        self.group = kwargs.pop('group', None)
        super().__init__(*args, **kwargs)

        # 🔹 Исключаем уже добавленных участников
        if self.group:
            member_ids = GroupMember.objects.filter(group=self.group).values_list('user_id', flat=True)
            self.fields['user'].queryset = User.objects.exclude(id__in=member_ids)


class ChangeMemberRoleForm(forms.Form):
    role = forms.ChoiceField(choices=GroupMember.ROLE_CHOICES)
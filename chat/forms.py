from django import forms
from django.contrib.auth import get_user_model
from chat.models import Message, Group, GroupMember

User = get_user_model()


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


GroupEditForm = GroupForm


class AddMemberForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label="Выберите пользователя",
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Выберите пользователя"
    )

    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop('group', None)
        super().__init__(*args, **kwargs)
        if self.group:
            member_ids = GroupMember.objects.filter(group=self.group).values_list('user_id', flat=True)
            self.fields['user'].queryset = User.objects.exclude(id__in=member_ids)


class ChangeMemberRoleForm(forms.Form):
    role = forms.ChoiceField(choices=GroupMember.ROLE_CHOICES)

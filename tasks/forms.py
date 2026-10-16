"""Формы приложения tasks.

Раньше вьюхи читали `request.POST` напрямую, поэтому `max_length` у `name` и
`title` не проверялся: Django не применяет его при `save()`, и произвольная
длина сохранялась на SQLite, но падала бы на PostgreSQL (problems.md, П-19).
"""

from django import forms

from tasks.models import Task, TaskList


class TaskListForm(forms.ModelForm):
    class Meta:
        model = TaskList
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

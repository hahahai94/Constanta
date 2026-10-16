from django.conf import settings
from django.db import models


class TaskList(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    description = models.TextField(blank=True, default='', verbose_name="Описание")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='task_lists', on_delete=models.CASCADE, verbose_name="Владелец")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        db_table = 'task_lists'
        ordering = ['-created_at']
        verbose_name = 'Список задач'
        verbose_name_plural = 'Списки задач'

    def __str__(self):
        return self.name

    # Счётчики читаются из аннотаций, если они есть: иначе на каждую строку
    # списка приходило несколько COUNT-запросов (problems.md, П-18).
    @property
    def task_count(self):
        annotated = getattr(self, '_task_count', None)
        return self.tasks.count() if annotated is None else annotated

    @property
    def done_count(self):
        annotated = getattr(self, '_done_count', None)
        return self.tasks.filter(is_done=True).count() if annotated is None else annotated


class Task(models.Model):
    task_list = models.ForeignKey(TaskList, related_name='tasks', on_delete=models.CASCADE, verbose_name="Список")
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    description = models.TextField(blank=True, default='', verbose_name="Описание")
    is_done = models.BooleanField(default=False, verbose_name="Выполнена")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='created_tasks', on_delete=models.CASCADE, verbose_name="Создал")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Выполнена")

    class Meta:
        db_table = 'tasks'
        ordering = ['is_done', '-created_at']
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'

    def __str__(self):
        return self.title

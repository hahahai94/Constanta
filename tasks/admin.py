from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from tasks.models import Task, TaskList


@admin.register(TaskList)
class TaskListAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'task_count', 'done_count', 'progress_bar', 'created_at')
    list_filter = ('created_at', 'owner')
    search_fields = ('name', 'description', 'owner__username')
    ordering = ('-created_at',)
    list_per_page = 50

    def get_queryset(self, request):
        # Раньше счётчики считались по строкам: четыре COUNT-запроса на
        # запись списка (problems.md, П-18).
        return super().get_queryset(request).annotate(
            _task_count=Count('tasks', distinct=True),
            _done_count=Count('tasks', filter=Q(tasks__is_done=True), distinct=True),
        )

    def task_count(self, obj):
        return getattr(obj, '_task_count', obj.task_count)

    task_count.short_description = "Задач"
    task_count.admin_order_field = '_task_count'

    def done_count(self, obj):
        return getattr(obj, '_done_count', obj.done_count)

    done_count.short_description = "Выполнено"
    done_count.admin_order_field = '_done_count'

    def progress_bar(self, obj):
        total = getattr(obj, '_task_count', None)
        done = getattr(obj, '_done_count', None)
        if total is None or done is None:
            total, done = obj.task_count, obj.done_count
        ratio = round(done / total * 100) if total else 0
        color = 'success' if ratio == 100 else ('warning' if ratio > 0 else 'secondary')
        return format_html(
            '<div class="progress" style="height: 16px; width: 120px;">'
            '<div class="progress-bar bg-{}" style="width: {}%;">{}/{}</div>'
            '</div>',
            color, ratio, done, total
        )

    progress_bar.short_description = "Прогресс"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'task_list', 'created_by', 'is_done', 'created_at', 'completed_at')
    list_filter = ('is_done', 'created_at', 'completed_at')
    search_fields = ('title', 'description', 'created_by__username')
    ordering = ('-created_at',)
    list_per_page = 50
    list_select_related = ('task_list', 'created_by')

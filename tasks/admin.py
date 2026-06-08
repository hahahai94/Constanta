from django.contrib import admin
from django.utils.html import format_html
from tasks.models import TaskList, Task


@admin.register(TaskList)
class TaskListAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'task_count', 'done_count', 'progress_bar', 'created_at')
    list_filter = ('created_at', 'owner')
    search_fields = ('name', 'description', 'owner__username')
    ordering = ('-created_at',)

    def progress_bar(self, obj):
        total = obj.task_count()
        done = obj.done_count()
        ratio = (done / total * 100) if total else 0
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
    list_display = ('title', 'task_list', 'created_by', 'assigned_to', 'is_done', 'created_at', 'completed_at')
    list_filter = ('is_done', 'created_at', 'completed_at')
    search_fields = ('title', 'description', 'created_by__username', 'assigned_to__username')
    ordering = ('-created_at',)
    list_select_related = ('task_list', 'created_by', 'assigned_to')

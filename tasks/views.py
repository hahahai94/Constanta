from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from tasks.forms import TaskForm, TaskListForm
from tasks.models import Task, TaskList
from users.ratelimit import html_429, rate_limit

TASK_LISTS_PER_PAGE = 20
TASKS_PER_PAGE = 30
DEFAULT_MAX_TASK_LISTS = 50
DEFAULT_MAX_TASKS_PER_LIST = 500


def _paginate(request, queryset, per_page):
    return Paginator(queryset, per_page).get_page(request.GET.get('page', 1))


def _first_error(form):
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return 'Некорректные данные'


def _parse_task_id(raw_value):
    """Возвращает int ID задачи или None при нечисловом вводе (П-68)."""
    text = (raw_value or '').strip()
    if not text.isdigit():
        return None
    val = int(text)
    return val if val > 0 else None


@login_required
def task_lists(request):
    # Аннотации вместо счётчиков по строкам: раньше на каждый список уходило
    # несколько COUNT-запросов (problems.md, П-18).
    # Сортировка задана явно: без неё пагинация аннотированного набора даёт
    # нестабильные страницы — запись может попасть на две или пропасть (П-82).
    lists = TaskList.objects.filter(owner=request.user).annotate(
        _task_count=Count('tasks', distinct=True),
        _done_count=Count('tasks', filter=Q(tasks__is_done=True), distinct=True),
    ).order_by('-created_at', '-id')
    return render(request, 'tasks/task_lists.html', {
        'lists': _paginate(request, lists, TASK_LISTS_PER_PAGE),
    })


@login_required
@rate_limit('task_action', limit=60, period=60, methods=('POST',), on_limited=html_429)
def task_list_detail(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id, owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_task':
            max_tasks = getattr(settings, 'MAX_TASKS_PER_LIST', DEFAULT_MAX_TASKS_PER_LIST)
            if task_list.tasks.count() >= max_tasks:
                messages.error(request, f'❌ Лимит задач в одном списке ({max_tasks})')
                return redirect('task_list_detail', list_id=list_id)
            form = TaskForm(request.POST)
            if form.is_valid():
                task = form.save(commit=False)
                task.task_list = task_list
                task.created_by = request.user
                task.save()
            else:
                messages.error(request, f'❌ {_first_error(form)}')

        elif action == 'toggle_task':
            task_id = _parse_task_id(request.POST.get('task_id'))
            if task_id is None:
                messages.error(request, 'Некорректный идентификатор задачи')
                return redirect('task_list_detail', list_id=list_id)
            task = get_object_or_404(Task, id=task_id, task_list=task_list)
            task.is_done = not task.is_done
            task.completed_at = timezone.now() if task.is_done else None
            task.save(update_fields=['is_done', 'completed_at', 'updated_at'])

        elif action == 'delete_task':
            task_id = _parse_task_id(request.POST.get('task_id'))
            if task_id is None:
                messages.error(request, 'Некорректный идентификатор задачи')
                return redirect('task_list_detail', list_id=list_id)
            Task.objects.filter(id=task_id, task_list=task_list).delete()

        elif action == 'edit_task':
            task_id = _parse_task_id(request.POST.get('task_id'))
            if task_id is None:
                messages.error(request, 'Некорректный идентификатор задачи')
                return redirect('task_list_detail', list_id=list_id)
            task = get_object_or_404(Task, id=task_id, task_list=task_list)
            form = TaskForm(request.POST, instance=task)
            if form.is_valid():
                form.save()
            else:
                messages.error(request, f'❌ {_first_error(form)}')

        else:
            messages.warning(request, 'Неизвестное действие')

        return redirect('task_list_detail', list_id=list_id)

    return render(request, 'tasks/task_list_detail.html', {
        'task_list': task_list,
        'tasks': _paginate(request, task_list.tasks.all(), TASKS_PER_PAGE),
    })


@login_required
@rate_limit('create_task_list', limit=20, period=300, methods=('POST',), on_limited=html_429)
def create_task_list(request):
    if request.method != 'POST':
        return redirect('task_lists')

    max_lists = getattr(settings, 'MAX_TASK_LISTS_PER_USER', DEFAULT_MAX_TASK_LISTS)
    if TaskList.objects.filter(owner=request.user).count() >= max_lists:
        messages.error(request, f'❌ Лимит списков задач ({max_lists})')
        return redirect('task_lists')

    form = TaskListForm(request.POST)
    if form.is_valid():
        task_list = form.save(commit=False)
        task_list.owner = request.user
        task_list.save()
    else:
        messages.error(request, f'❌ {_first_error(form)}')
    return redirect('task_lists')


@login_required
def edit_task_list(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id, owner=request.user)
    if request.method != 'POST':
        return redirect('task_lists')

    form = TaskListForm(request.POST, instance=task_list)
    if form.is_valid():
        form.save()
    else:
        messages.error(request, f'❌ {_first_error(form)}')
    return redirect('task_lists')


@login_required
def delete_task_list(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id, owner=request.user)
    if request.method == 'POST':
        task_list.delete()
    return redirect('task_lists')

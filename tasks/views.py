from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from tasks.forms import TaskForm, TaskListForm
from tasks.models import Task, TaskList

TASK_LISTS_PER_PAGE = 20
TASKS_PER_PAGE = 30


def _paginate(request, queryset, per_page):
    return Paginator(queryset, per_page).get_page(request.GET.get('page', 1))


def _first_error(form):
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return 'Некорректные данные'


@login_required
def task_lists(request):
    # Аннотации вместо счётчиков по строкам: раньше на каждый список уходило
    # несколько COUNT-запросов (problems.md, П-18).
    lists = TaskList.objects.filter(owner=request.user).annotate(
        _task_count=Count('tasks', distinct=True),
        _done_count=Count('tasks', filter=Q(tasks__is_done=True), distinct=True),
    )
    return render(request, 'tasks/task_lists.html', {
        'lists': _paginate(request, lists, TASK_LISTS_PER_PAGE),
    })


@login_required
def task_list_detail(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id, owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_task':
            form = TaskForm(request.POST)
            if form.is_valid():
                task = form.save(commit=False)
                task.task_list = task_list
                task.created_by = request.user
                task.save()
            else:
                messages.error(request, f'❌ {_first_error(form)}')

        elif action == 'toggle_task':
            task = get_object_or_404(
                Task, id=request.POST.get('task_id'), task_list=task_list)
            task.is_done = not task.is_done
            task.completed_at = timezone.now() if task.is_done else None
            task.save(update_fields=['is_done', 'completed_at', 'updated_at'])

        elif action == 'delete_task':
            Task.objects.filter(
                id=request.POST.get('task_id'), task_list=task_list).delete()

        elif action == 'edit_task':
            task = get_object_or_404(
                Task, id=request.POST.get('task_id'), task_list=task_list)
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
def create_task_list(request):
    if request.method != 'POST':
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

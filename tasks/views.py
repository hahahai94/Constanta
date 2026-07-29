from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from tasks.models import TaskList, Task


@login_required
def task_lists(request):
    lists = TaskList.objects.filter(owner=request.user)
    return render(request, 'tasks/task_lists.html', {'lists': lists})


@login_required
def task_list_detail(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id, owner=request.user)
    tasks = task_list.tasks.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_task':
            title = request.POST.get('title', '').strip()
            if title:
                Task.objects.create(
                    task_list=task_list,
                    title=title,
                    description=request.POST.get('description', '').strip(),
                    created_by=request.user,
                )
            return redirect('task_list_detail', list_id=list_id)

        elif action == 'toggle_task':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(Task, id=task_id, task_list=task_list)
            task.is_done = not task.is_done
            task.completed_at = timezone.now() if task.is_done else None
            task.save()
            return redirect('task_list_detail', list_id=list_id)

        elif action == 'delete_task':
            task_id = request.POST.get('task_id')
            Task.objects.filter(id=task_id, task_list=task_list).delete()
            return redirect('task_list_detail', list_id=list_id)

        elif action == 'edit_task':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(Task, id=task_id, task_list=task_list)
            title = request.POST.get('title', '').strip()
            if title:
                task.title = title
                task.description = request.POST.get('description', '').strip()
                task.save()
            return redirect('task_list_detail', list_id=list_id)

    return render(request, 'tasks/task_list_detail.html', {
        'task_list': task_list,
        'tasks': tasks,
    })


@login_required
def create_task_list(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            TaskList.objects.create(
                name=name,
                description=request.POST.get('description', '').strip(),
                owner=request.user,
            )
        return redirect('task_lists')
    return redirect('task_lists')


@login_required
def edit_task_list(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id, owner=request.user)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            task_list.name = name
            task_list.description = request.POST.get('description', '').strip()
            task_list.save()
        return redirect('task_lists')
    return redirect('task_lists')


@login_required
def delete_task_list(request, list_id):
    task_list = get_object_or_404(TaskList, id=list_id, owner=request.user)
    if request.method == 'POST':
        task_list.delete()
    return redirect('task_lists')

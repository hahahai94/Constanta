from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from chat.models import Group, GroupMember, Message

User = get_user_model()


@login_required
def groups_list(request):
    """Список групп пользователя"""
    memberships = GroupMember.objects.filter(
        user=request.user
    ).select_related('group').order_by('group__name')

    return render(request, 'groups.html', {'memberships': memberships})


@login_required
def group_chat(request, group_id):
    """Групповой чат"""
    group = get_object_or_404(Group, id=group_id)
    membership = GroupMember.objects.filter(group=group, user=request.user).first()

    if not membership:
        messages.error(request, 'Вы не участник этой группы')
        return redirect('groups')

    is_owner = group.owner == request.user
    is_admin = (membership.role == 'admin') or is_owner

    members = GroupMember.objects.filter(group=group).select_related('user').order_by(
        '-role', 'user__username'
    )
    messages_qs = Message.objects.filter(
        group=group, is_deleted=False
    ).order_by('created_at')[:50]

    return render(request, 'group_chat.html', {
        'group': group,
        'members': members,
        'messages': messages_qs,
        'is_owner': is_owner,
        'is_admin': is_admin,
    })


@login_required
def create_group(request):
    """Создание новой группы"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            group = Group.objects.create(name=name, owner=request.user)
            GroupMember.objects.create(group=group, user=request.user, role='owner')
            messages.success(request, f'✅ Группа "{name}" создана!')
            return redirect('group_chat', group_id=group.id)
    return redirect('groups')


@login_required
def edit_group(request, group_id):
    """Редактирование группы (только владелец)"""
    group = get_object_or_404(Group, id=group_id)
    if group.owner != request.user:
        return redirect('group_chat', group_id=group_id)

    if request.method == 'POST':
        group.name = request.POST.get('name', group.name).strip()
        group.description = request.POST.get('description', group.description).strip()
        if request.FILES.get('avatar'):
            group.avatar = request.FILES.get('avatar')
        group.save()
        messages.success(request, '✅ Группа обновлена')
    return redirect('group_chat', group_id=group_id)


@login_required
def add_member(request, group_id):
    """Добавление участника в группу"""
    group = get_object_or_404(Group, id=group_id)
    membership = GroupMember.objects.filter(group=group, user=request.user).first()
    if not membership or membership.role not in ['owner', 'admin']:
        return redirect('group_chat', group_id=group_id)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        try:
            user = User.objects.get(username=username)
            if not GroupMember.objects.filter(group=group, user=user).exists():
                GroupMember.objects.create(group=group, user=user, role='member')
                messages.success(request, f'✅ {user.get_display_name()} добавлен')
            else:
                messages.warning(request, '⚠️ Уже в группе')
        except User.DoesNotExist:
            messages.error(request, '❌ Пользователь не найден')
    return redirect('group_chat', group_id=group_id)


@login_required
def remove_member(request, group_id, user_id):
    """Удаление участника из группы"""
    group = get_object_or_404(Group, id=group_id)
    current = GroupMember.objects.filter(group=group, user=request.user).first()
    if not current or current.role not in ['owner', 'admin']:
        return redirect('group_chat', group_id=group_id)

    target = get_object_or_404(GroupMember, group=group, user_id=user_id)
    if target.role == 'owner':
        messages.error(request, '🚫 Нельзя удалить владельца')
    else:
        target.delete()
        messages.success(request, '✅ Участник удалён')
    return redirect('group_chat', group_id=group_id)


@login_required
def change_role(request, group_id, user_id, new_role):
    """Изменение роли участника (только владелец)"""
    group = get_object_or_404(Group, id=group_id)
    if group.owner != request.user:
        return redirect('group_chat', group_id=group_id)

    target = get_object_or_404(GroupMember, group=group, user_id=user_id)
    if new_role in ['member', 'admin']:
        target.role = new_role
        target.save()
        messages.success(request, f'✅ Роль изменена на {target.get_role_display()}')
    return redirect('group_chat', group_id=group_id)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from chat.models import Group, GroupMember, Message
from chat.utils import html_429, normalize_conversation_name, rate_limit
from chat.utils.history import (
    build_earlier_url, load_message_page, parse_before,
)
from chat.utils.uploads import normalize_avatar

User = get_user_model()


@login_required
def groups_list(request):
    """Список групп пользователя"""
    from django.core.paginator import Paginator
    memberships_qs = GroupMember.objects.filter(
        user=request.user
    ).select_related('group').order_by('group__name')
    paginator = Paginator(memberships_qs, 20)
    page_number = request.GET.get('page', 1)
    memberships = paginator.get_page(page_number)
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
    history = Message.objects.filter(group=group, is_deleted=False)
    messages_page, has_earlier = load_message_page(
        history, parse_before(request.GET.get('before')))
    earlier_url = build_earlier_url(request, messages_page, has_earlier)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('parts/group_message_list.html', {
            'messages': messages_page,
            'user': request.user,
            'request': request,
        })
        return JsonResponse({
            'html': html,
            'has_earlier': has_earlier,
            'earlier_url': earlier_url,
        })

    return render(request, 'group_chat.html', {
        'group': group,
        'members': members,
        'messages': messages_page,
        'has_earlier': has_earlier,
        'earlier_url': earlier_url,
        'is_owner': is_owner,
        'is_admin': is_admin,
    })


@login_required
@rate_limit('create_group', limit=10, period=300, on_limited=html_429)
def create_group(request):
    """Создание новой группы"""
    if request.method == 'POST':
        try:
            name = normalize_conversation_name(request.POST.get('name', ''))
        except ValidationError as exc:
            messages.error(request, f'❌ {exc.messages[0]}')
            return redirect('groups')
        if Group.objects.filter(owner=request.user).count() >= settings.MAX_GROUPS_PER_USER:
            messages.error(request, f'❌ Лимит групп ({settings.MAX_GROUPS_PER_USER})')
            return redirect('groups')
        group = Group.objects.create(name=name, owner=request.user)
        GroupMember.objects.create(group=group, user=request.user, role='owner')
        return redirect('group_chat', group_id=group.id)
    return redirect('groups')


@login_required
@rate_limit('edit_group', limit=20, period=300, on_limited=html_429)
def edit_group(request, group_id):
    """Редактирование группы (только владелец)"""
    group = get_object_or_404(Group, id=group_id)
    if group.owner != request.user:
        return redirect('group_chat', group_id=group_id)

    if request.method == 'POST':
        try:
            name = normalize_conversation_name(
                request.POST.get('name', group.name))
        except ValidationError as exc:
            messages.error(request, f'❌ {exc.messages[0]}')
            return redirect('group_chat', group_id=group_id)

        old_avatar = group.avatar
        old_avatar_name = old_avatar.name if old_avatar else ''
        old_avatar_storage = old_avatar.storage if old_avatar else None
        avatar = request.FILES.get('avatar')
        if avatar:
            # Проверяем до применения изменений, чтобы отклонённый файл не
            # оставил группу частично обновлённой (problems.md, П-3).
            try:
                normalize_avatar(avatar)
            except ValidationError as exc:
                message = exc.messages[0] if exc.messages else 'Недопустимый файл'
                messages.error(request, f'❌ {message}')
                return redirect('group_chat', group_id=group_id)

        group.name = name
        group.description = request.POST.get('description', group.description).strip()
        if avatar:
            group.avatar = avatar
        group.save()
        if (old_avatar_name and group.avatar
                and old_avatar_name != group.avatar.name):
            old_avatar_storage.delete(old_avatar_name)
    return redirect('group_chat', group_id=group_id)


@login_required
@rate_limit('add_member', limit=20, period=300, on_limited=html_429)
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
            else:
                messages.warning(request, '⚠️ Уже в группе')
        except User.DoesNotExist:
            messages.error(request, '❌ Пользователь не найден')
    return redirect('group_chat', group_id=group_id)


@login_required
@require_POST
def remove_member(request, group_id, user_id):
    """Удаление участника из группы.

    Только POST: GET-эндпоинт, меняющий состояние, уязвим к CSRF
    (problems.md, П-9).
    """
    group = get_object_or_404(Group, id=group_id)
    current = GroupMember.objects.filter(group=group, user=request.user).first()
    if not current or current.role not in ['owner', 'admin']:
        return redirect('group_chat', group_id=group_id)

    target = get_object_or_404(GroupMember, group=group, user_id=user_id)
    if target.role == 'owner':
        messages.error(request, '🚫 Нельзя удалить владельца')
    else:
        target.delete()
    return redirect('group_chat', group_id=group_id)


@login_required
@require_POST
def change_role(request, group_id, user_id, new_role):
    """Изменение роли участника (только владелец).

    Только POST: GET-эндпоинт, меняющий состояние, уязвим к CSRF
    (problems.md, П-9).
    """
    group = get_object_or_404(Group, id=group_id)
    if group.owner != request.user:
        return redirect('group_chat', group_id=group_id)

    target = get_object_or_404(GroupMember, group=group, user_id=user_id)
    if target.user == group.owner:
        messages.error(request, '🚫 Нельзя изменить роль владельца')
        return redirect('group_chat', group_id=group_id)
    if new_role in ['member', 'admin']:
        target.role = new_role
        target.save()
        messages.success(request, f'✅ Роль изменена на {target.get_role_display()}')
    return redirect('group_chat', group_id=group_id)
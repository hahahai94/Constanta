from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Max, Sum, Case, When, IntegerField, F
from django.utils import timezone
from datetime import datetime
from django.db import models
import uuid
import hashlib
import os
import json

from .models import User, Message, Friendship, Group, GroupMember, AdminLog, Notification  # ← ДОБАВИТЬ
from .forms import (
    RegistrationForm, LoginForm, ProfileForm, AddFriendForm,
    MessageForm, GroupForm, GroupEditForm, AddMemberForm, ChangeMemberRoleForm,
    ChangeUsernameForm, ChangePasswordForm
)
from .utils import parse_mentions, create_notification


# --- Технические ручки ---

def tech_check(request):
    return JsonResponse({"status": "ok"})


def tech_page(request):
    return render(request, 'tech.html', {
        'python_version': "3.13",
        'db_engine': "SQLite",
        'status': "Running",
        'users_count': User.objects.count(),
        'messages_count': Message.objects.count(),
        'groups_count': Group.objects.count(),
    })


# --- Авторизация и Регистрация ---

def reg_view(request):
    if request.user.is_authenticated:
        return redirect('main')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # 🔹 Указываем бэкенд явно!
            login(request, user, backend='chat.backends.CustomAuthBackend')
            return redirect('profile_edit')
    else:
        form = RegistrationForm()
    return render(request, 'auth.html', {'form': form, 'type': 'reg'})


def auth_view(request):
    if request.user.is_authenticated:
        return redirect('main')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                return render(request, 'banned.html', {'user': user})

            # 🔹 Указываем бэкенд явно!
            login(request, user, backend='chat.backends.CustomAuthBackend')
            return redirect('main')
        else:
            messages.error(request, 'Неверный логин или пароль')

    form = LoginForm()
    return render(request, 'auth.html', {'form': form, 'type': 'auth'})

def logout_view(request):
    logout(request)
    request.user.last_seen = None
    request.user.save(update_fields=['last_seen'])
    return redirect('auth')


# --- Профиль и Настройки ---

@login_required
def profile_view(request):
    return render(request, 'profile.html', {'user': request.user})


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'profile_edit.html', {'form': form})


@login_required
def group_edit(request, group_id):
    """Редактирование группы"""
    group = get_object_or_404(Group, id=group_id)

    # Только владелец может редактировать
    if not group.is_owner(request.user):
        messages.error(request, 'Только владелец может редактировать группу!')
        return redirect('group_chat', group_id=group_id)

    if request.method == 'POST':
        form = GroupEditForm(request.POST, request.FILES, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f'Группа "{group.name}" обновлена!')
            return redirect('group_chat', group_id=group_id)
    else:
        form = GroupEditForm(instance=group)

    return render(request, 'group_edit.html', {'form': form, 'group': group})

@login_required
def change_username(request):
    if request.method == 'POST':
        form = ChangeUsernameForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.username = form.cleaned_data['username']
            request.user.save()
            return redirect('profile')
    else:
        form = ChangeUsernameForm()
    return render(request, 'settings.html', {'form': form, 'type': 'username'})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return redirect('profile')
    else:
        form = ChangePasswordForm(request.user)
    return render(request, 'settings.html', {'form': form, 'type': 'password'})


# --- Каталог пользователей ---

@login_required
def users_catalog(request):
    search = request.GET.get('search', '')
    users = User.objects.exclude(id=request.user.id)
    if search:
        users = users.filter(Q(username__icontains=search) | Q(nick__icontains=search))
    friend_ids = Friendship.objects.filter(user=request.user).values_list('friend_id', flat=True)
    for user in users:
        user.is_friend = user.id in friend_ids
    return render(request, 'users_catalog.html', {'users': users, 'search': search})


@login_required
def user_detail(request, nick):
    target_user = get_object_or_404(User, Q(nick=nick) | Q(username=nick))
    is_friend = Friendship.objects.filter(user=request.user, friend=target_user).exists()
    messages_count = Message.objects.filter(
        Q(sender=request.user, receiver=target_user) |
        Q(sender=target_user, receiver=request.user)
    ).count()
    return render(request, 'user_detail.html', {
        'target_user': target_user,
        'is_friend': is_friend,
        'messages_count': messages_count,
    })


# --- Друзья ---

@login_required
def friends_list(request):
    friend_ids = Friendship.objects.filter(user=request.user).values_list('friend_id', flat=True)
    friends = User.objects.filter(id__in=friend_ids)
    return render(request, 'friends.html', {'friends': friends, 'add_form': AddFriendForm()})


@login_required
def friends_add(request):
    if request.method == 'POST':
        form = AddFriendForm(request.POST)
        if form.is_valid():
            nick = form.cleaned_data['friend_username']
            try:
                friend_user = User.objects.get(Q(username=nick) | Q(nick=nick))
                if friend_user != request.user:
                    Friendship.objects.get_or_create(user=request.user, friend=friend_user)
            except User.DoesNotExist:
                pass
    return redirect('friends')


@login_required
def friends_remove(request, friend_id):
    Friendship.objects.filter(user=request.user, friend_id=friend_id).delete()
    return redirect('friends')


@login_required
def friends_delete(request, friend_id):
    try:
        friend_user = get_object_or_404(User, id=friend_id)
        friendship = Friendship.objects.filter(user=request.user, friend=friend_user).first()
        if friendship:
            Message.objects.filter(
                Q(sender=request.user, receiver=friend_user) |
                Q(sender=friend_user, receiver=request.user)
            ).delete()
            friendship.delete()
    except Exception:
        pass
    return redirect('friends')


# --- Группы ---

@login_required
def groups_list(request):
    memberships = GroupMember.objects.filter(user=request.user).select_related('group')
    return render(request, 'groups.html', {'memberships': memberships, 'create_form': GroupForm()})


@login_required
def group_create(request):
    if request.method == 'POST':
        form = GroupForm(request.POST, request.FILES)
        if form.is_valid():
            group = form.save(commit=False)
            group.owner = request.user
            group.save()
            GroupMember.objects.create(group=group, user=request.user, role='owner')
            return redirect('group_chat', group_id=group.id)
    else:
        form = GroupForm()
    return render(request, 'group_create.html', {'form': form})


@login_required
def group_chat(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if not group.is_member(request.user):
        return redirect('groups')

    messages_qs = Message.objects.filter(group=group, is_deleted=False).order_by('created_at')[:100]
    members = GroupMember.objects.filter(group=group).select_related('user')

    is_owner = group.is_owner(request.user)
    is_admin = GroupMember.objects.filter(group=group, user=request.user, role='admin').exists()

    # 🔹 Доступные пользователи (не в группе)
    member_ids = GroupMember.objects.filter(group=group).values_list('user_id', flat=True)
    available_users = User.objects.exclude(id__in=member_ids).exclude(id=request.user.id)[:100]

    # Формы
    add_member_form = AddMemberForm(group=group)

    return render(request, 'group_chat.html', {
        'group': group,
        'messages': messages_qs,
        'members': members,
        'is_owner': is_owner,
        'is_admin': is_admin or is_owner,
        'message_form': MessageForm(),
        'add_member_form': add_member_form,
        'role_form': ChangeMemberRoleForm(),
        'available_users': available_users,  # ← ДОБАВИТЬ
        'my_user_id': request.user.id,
    })


@login_required
def group_add_member(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if not group.is_owner(request.user):
        messages.error(request, 'Только владелец может добавлять участников!')
        return redirect('group_chat', group_id=group_id)

    if request.method == 'POST':
        user_id = request.POST.get('user')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                if GroupMember.objects.filter(group=group, user=user).exists():
                    messages.warning(request, f'{user.get_display_name()} уже в группе')
                else:
                    GroupMember.objects.create(group=group, user=user, role='member')
                    messages.success(request, f'{user.get_display_name()} добавлен в группу!')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь не найден')

    return redirect('group_chat', group_id=group_id)


@login_required
def group_remove_member(request, group_id, user_id):
    group = get_object_or_404(Group, id=group_id)
    member = get_object_or_404(GroupMember, group=group, user_id=user_id)

    # Проверка прав: владелец может всех, админ только участников
    my_membership = GroupMember.objects.get(group=group, user=request.user)
    if my_membership.role not in ['owner', 'admin'] or member.role == 'owner':
        return redirect('group_chat', group_id=group_id)

    member.delete()
    return redirect('group_chat', group_id=group_id)


@login_required
def group_change_role(request, group_id, user_id):
    group = get_object_or_404(Group, id=group_id)
    target_member = get_object_or_404(GroupMember, group=group, user_id=user_id)

    # Только владелец может менять роли
    if not group.is_owner(request.user):
        return redirect('group_chat', group_id=group_id)

    if request.method == 'POST':
        form = ChangeMemberRoleForm(request.POST)
        if form.is_valid():
            target_member.role = form.cleaned_data['role']
            target_member.save()

    return redirect('group_chat', group_id=group_id)


@login_required
def group_leave(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    member = GroupMember.objects.filter(group=group, user=request.user).first()

    if member and member.role != 'owner':
        member.delete()

    return redirect('groups')


@login_required
def group_delete(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if group.is_owner(request.user):
        group.delete()

    return redirect('groups')


# --- Чат (Главная) ---

@login_required
@login_required
def main_chat(request):
    active_friend_id = request.GET.get('friend_id')
    active_friend = None
    chat_messages = []

    if active_friend_id:
        active_friend = get_object_or_404(User, id=active_friend_id)

        chat_messages = Message.objects.filter(
            Q(sender=request.user, receiver=active_friend) |
            Q(sender=active_friend, receiver=request.user),
            is_deleted=False
        ).order_by('created_at')

        # Помечаем сообщения как прочитанные
        Message.objects.filter(
            sender=active_friend,
            receiver=request.user,
            is_read=False
        ).update(is_read=True)

    # 🔹 1. Получаем всех друзей
    friend_ids = list(Friendship.objects.filter(user=request.user).values_list('friend_id', flat=True))

    # 🔹 2. Получаем всех с кем были сообщения
    conversations = Message.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        is_deleted=False
    ).values('sender', 'receiver').annotate(
        last_message=models.Max('created_at'),
        unread_count=models.Sum(
            models.Case(
                models.When(receiver=request.user, is_read=False, then=1),
                default=0,
                output_field=models.IntegerField()
            )
        )
    )

    # 🔹 3. Объединяем в один список уникальных пользователей
    all_user_ids = set(friend_ids)  # Начинаем с друзей

    for conv in conversations:
        if conv['sender'] == request.user.id:
            all_user_ids.add(conv['receiver'])
        else:
            all_user_ids.add(conv['sender'])

    # Удаляем себя из списка
    all_user_ids.discard(request.user.id)

    # 🔹 4. Собираем полную информацию по каждому пользователю
    conversations_list = []
    users = User.objects.filter(id__in=all_user_ids)

    for user in users:
        # Находим последнюю переписку с этим пользователем
        conv_data = next(
            (c for c in conversations if c['sender'] == user.id or c['receiver'] == user.id),
            None
        )

        is_friend = user.id in friend_ids

        conversations_list.append({
            'user': user,
            'last_message': conv_data['last_message'] if conv_data else None,
            'unread_count': conv_data['unread_count'] if conv_data else 0,
            'is_friend': is_friend,
        })

    # 🔹 5. Сортируем: сначала непрочитанные, потом по последнему сообщению
    conversations_list.sort(key=lambda x: (
        -x['unread_count'],
        x['last_message'] or timezone.make_aware(datetime.min)
    ))

    # Количество непрочитанных уведомлений
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    # Группы
    group_memberships = GroupMember.objects.filter(user=request.user).select_related('group')

    # 🔹 Проверяем является ли активный друг другом
    is_friend = False
    if active_friend:
        is_friend = Friendship.objects.filter(
            Q(user=request.user, friend=active_friend) |
            Q(user=active_friend, friend=request.user)
        ).exists()

    return render(request, 'index.html', {
        'conversations': conversations_list,
        'groups': group_memberships,
        'active_friend': active_friend,
        'messages': chat_messages,
        'message_form': MessageForm(),
        'my_user_id': request.user.id,
        'is_friend': is_friend,  # ← ДОЛЖНО БЫТЬ ЗДЕСЬ!
        'unread_notifications': unread_notifications,
    })


@login_required
def get_notifications(request):
    """Получить уведомления (API)"""
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:20]

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    data = []
    for notif in notifications:
        data.append({
            'id': str(notif.id),
            'type': notif.notification_type,
            'title': notif.title,
            'message': notif.message,
            'url': notif.url,
            'icon': notif.get_icon(),
            'time': notif.created_at.strftime('%H:%M'),
            'created_at': notif.created_at.isoformat(),
        })

    return JsonResponse({
        'notifications': data,
        'unread_count': unread_count,
    })


@login_required
def mark_notification_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'ok'})


@login_required
def mark_all_notifications_read(request):
    """Отметить все уведомления как прочитанные"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@login_required
def send_message(request):
    if request.method == 'POST':
        friend_id = request.POST.get('friend_id')
        group_id = request.POST.get('group_id')
        content = request.POST.get('content', '')

        attachment = request.FILES.get('attachment')
        attachment_type = 'none'
        attachment_size = 0
        attachment_hash = ''
        attachment_original_name = ''
        upload_path = None

        # 🔹 Обработка файла
        if attachment:
            # Проверка размера (50 МБ)
            if attachment.size > 50 * 1024 * 1024:
                return JsonResponse({'status': 'failed', 'error': 'Файл слишком большой (макс. 50 МБ)'}, status=400)

            # Генерация хеша
            import hashlib
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            file_content = attachment.read()
            hash_input = f"{file_content.hex()}{request.user.id}{timestamp}".encode('utf-8')
            attachment_hash = hashlib.sha256(hash_input).hexdigest()
            attachment.seek(0)

            # Определение типа
            if attachment.content_type and attachment.content_type.startswith('image/'):
                attachment_type = 'image'
            elif attachment.content_type and attachment.content_type.startswith('audio/'):
                attachment_type = 'voice'
            else:
                attachment_type = 'file'

            attachment_size = attachment.size
            attachment_original_name = attachment.name

            # Путь с хешем
            import os
            from django.conf import settings
            subdir = attachment_hash[:2]
            ext = os.path.splitext(attachment.name)[1].lower()
            new_filename = f"{attachment_hash}{ext}"
            upload_path = os.path.join('attachments', subdir, new_filename)

            # Сохранение файла
            from django.core.files.storage import default_storage
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'attachments', subdir), exist_ok=True)
            default_storage.save(upload_path, attachment)

        if not content and not attachment:
            return JsonResponse({'status': 'failed', 'error': 'Пустое сообщение'}, status=400)

        # 🔹 Обработка упоминаний
        parsed_content = content
        mentions_json = '[]'
        mentioned_ids = []

        if content:
            from .utils import parse_mentions
            if group_id:
                group = get_object_or_404(Group, id=group_id)
                parsed_content, mentioned_ids = parse_mentions(content, group=group)
            elif friend_id:
                parsed_content, mentioned_ids = parse_mentions(content, receiver=None)
            mentions_json = json.dumps(mentioned_ids)

        # 🔹 Создание сообщения (ИСПРАВЛЕНО - только именованные аргументы!)
        msg = None
        if friend_id:
            receiver = get_object_or_404(User, id=friend_id)
            msg = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                group=None,
                content=parsed_content,
                attachment=upload_path if upload_path else None,
                attachment_hash=attachment_hash,
                attachment_original_name=attachment_original_name,
                attachment_type=attachment_type,
                attachment_size=attachment_size,
                mentions=mentions_json
            )

            # 🔹 Уведомление получателю
            if receiver != request.user:
                from .utils import create_notification
                create_notification(
                    user=receiver,
                    notification_type='message',
                    title=f'Новое сообщение от {request.user.get_display_name()}',
                    message=content[:100] if content else '📎 Вложение',
                    url=f'/?friend_id={request.user.id}',
                    related_message=msg
                )

        elif group_id:
            group = get_object_or_404(Group, id=group_id)
            if group.is_member(request.user):
                msg = Message.objects.create(
                    sender=request.user,
                    receiver=None,
                    group=group,
                    content=parsed_content,
                    attachment=upload_path if upload_path else None,
                    attachment_hash=attachment_hash,
                    attachment_original_name=attachment_original_name,
                    attachment_type=attachment_type,
                    attachment_size=attachment_size,
                    mentions=mentions_json
                )

                # 🔹 Уведомления об упоминаниях
                if mentioned_ids:
                    from .utils import create_notification
                    for user_id in mentioned_ids:
                        if user_id != request.user.id:
                            try:
                                mentioned_user = User.objects.get(id=user_id)
                                create_notification(
                                    user=mentioned_user,
                                    notification_type='mention',
                                    title=f'Вас упомянули в чате',
                                    message=f'{request.user.get_display_name()} упомянул вас',
                                    url=f'/groups/{group_id}/',
                                    related_message=msg
                                )
                            except User.DoesNotExist:
                                pass

        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'failed'}, status=400)


@login_required
def fetch_messages(request):
    friend_id = request.GET.get('friend_id')
    group_id = request.GET.get('group_id')

    if friend_id:
        receiver = get_object_or_404(User, id=friend_id)
        msgs = Message.objects.filter(
            Q(sender=request.user, receiver=receiver) |
            Q(sender=receiver, receiver=request.user),
            is_deleted=False
        ).order_by('created_at')[:50]
    elif group_id:
        group = get_object_or_404(Group, id=group_id)
        msgs = Message.objects.filter(group=group, is_deleted=False).order_by('created_at')[:50]
    else:
        return JsonResponse({'messages': []})

    data = []
    for m in msgs:
        data.append({
            'id': str(m.id),
            'sender': m.sender.username,
            'sender_nick': m.sender.get_display_name(),
            'sender_avatar': m.sender.get_avatar_url(),
            'content': m.content,
            'is_mine': m.sender == request.user,
            'time': m.created_at.strftime('%H:%M'),
            # 🔹 Данные о вложениях
            'attachment_type': m.attachment_type,
            'attachment_url': m.get_attachment_url(),
            'attachment_name': m.get_attachment_name(),
            'attachment_size': m.attachment_size,
        })
    return JsonResponse({'messages': data})


@login_required
def chat_files(request, friend_id=None, group_id=None):
    """Отображение всех файлов чата"""
    files = []
    chat_name = ""
    chat_type = ""

    if friend_id:
        # Личный чат
        friend = get_object_or_404(User, id=friend_id)
        if not Friendship.objects.filter(
                Q(user=request.user, friend=friend) |
                Q(user=friend, friend=request.user)
        ).exists():
            return redirect('main')

        chat_name = friend.get_display_name()
        chat_type = "personal"

        files = Message.objects.filter(
            Q(sender=request.user, receiver=friend) |
            Q(sender=friend, receiver=request.user),
            attachment_type__in=['image', 'file', 'voice'],
            is_deleted=False
        ).order_by('-created_at')

    elif group_id:
        # Групповой чат
        group = get_object_or_404(Group, id=group_id)
        if not group.is_member(request.user):
            return redirect('groups')

        chat_name = group.name
        chat_type = "group"

        files = Message.objects.filter(
            group=group,
            attachment_type__in=['image', 'file', 'voice'],
            is_deleted=False
        ).order_by('-created_at')

    # Статистика
    images_count = files.filter(attachment_type='image').count()
    files_count = files.filter(attachment_type='file').count()
    voice_count = files.filter(attachment_type='voice').count()

    return render(request, 'chat_files.html', {
        'files': files,
        'chat_name': chat_name,
        'chat_type': chat_type,
        'friend_id': friend_id,
        'group_id': group_id,
        'images_count': images_count,
        'files_count': files_count,
        'voice_count': voice_count,
    })





@login_required
def delete_message(request, message_id):
    if request.method == 'POST':
        try:
            msg = Message.objects.get(id=message_id, sender=request.user)
            msg.is_deleted = True
            msg.content = "[Сообщение удалено]"
            msg.save()
            return JsonResponse({'status': 'ok'})
        except Message.DoesNotExist:
            return JsonResponse({'status': 'failed'}, status=403)
    return JsonResponse({'status': 'failed'}, status=400)



from django.utils import timezone

@login_required
def heartbeat(request):
    """Обновляет время последней активности"""
    request.user.last_seen = timezone.now()
    request.user.save(update_fields=['last_seen'])
    return JsonResponse({'status': 'ok'})



from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse


# --- СУПЕР АДМИНКА ---

@login_required
def superadmin_panel(request):
    if not request.user.is_superuser:
        return redirect('main')

    users = User.objects.all().order_by('-date_joined')
    logs = AdminLog.objects.all()[:50]

    # 🔹 Группы с подсчётом
    groups = Group.objects.all().order_by('-created_at')
    groups_data = []
    for group in groups:
        messages_count = group.messages.count()
        files_count = group.messages.exclude(attachment_type='none').exclude(attachment='').count()
        members_count = group.members.count()

        # Подсчёт размера файлов
        files_storage = group.messages.exclude(attachment_type='none').exclude(attachment='').aggregate(
            total=models.Sum('attachment_size')
        )['total'] or 0

        groups_data.append({
            'group': group,
            'messages_count': messages_count,
            'files_count': files_count,
            'members_count': members_count,
            'files_storage': files_storage,
        })

    # 🔹 Статистика по файлам
    total_files = Message.objects.exclude(attachment_type='none').exclude(attachment='')
    total_storage = total_files.aggregate(total=models.Sum('attachment_size'))['total'] or 0

    images_storage = Message.objects.filter(attachment_type='image').aggregate(
        total=models.Sum('attachment_size')
    )['total'] or 0
    files_storage = Message.objects.filter(attachment_type='file').aggregate(
        total=models.Sum('attachment_size')
    )['total'] or 0
    voice_storage = Message.objects.filter(attachment_type='voice').aggregate(
        total=models.Sum('attachment_size')
    )['total'] or 0

    return render(request, 'superadmin/panel.html', {
        'users': users,
        'logs': logs,
        'groups_data': groups_data,  # ← ГОТОВЫЕ ДАННЫЕ
        'stats': {
            'total_users': User.objects.count(),
            'total_messages': Message.objects.count(),
            'total_groups': Group.objects.count(),
            'total_storage': total_storage,
            'images_storage': images_storage,
            'files_storage': files_storage,
            'voice_storage': voice_storage,
        }
    })


@login_required
def superadmin_user_edit(request, user_id):
    """Редактирование профиля пользователя"""
    if not request.user.is_superuser:
        return redirect('main')

    target_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        # Проверка пароля админа
        admin_password = request.POST.get('admin_password')
        if not request.user.check_password(admin_password):
            messages.error(request, 'Неверный пароль администратора!')
            return redirect('superadmin_user_edit', user_id=user_id)

        # Изменение данных
        target_user.nick = request.POST.get('nick', target_user.nick)
        target_user.bio = request.POST.get('bio', target_user.bio)
        if request.FILES.get('avatar'):
            target_user.avatar = request.FILES.get('avatar')
        target_user.save()

        # Лог
        AdminLog.objects.create(
            admin=request.user,
            action='edit_profile',
            target_user=target_user,
            description=f'Изменён профиль: nick={target_user.nick}',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f'Профиль {target_user.username} обновлён!')
        return redirect('superadmin_user_edit', user_id=user_id)

    return render(request, 'superadmin/user_edit.html', {'target_user': target_user})


@login_required
def superadmin_delete_user(request, user_id):
    """Удаление пользователя (с подтверждением)"""
    if not request.user.is_superuser:
        return redirect('main')

    target_user = get_object_or_404(User, id=user_id)

    if target_user == request.user:
        messages.error(request, 'Нельзя удалить самого себя!')
        return redirect('superadmin_panel')

    if request.method == 'POST':
        admin_password = request.POST.get('admin_password')
        if not request.user.check_password(admin_password):
            messages.error(request, 'Неверный пароль администратора!')
            return redirect('superadmin_delete_user', user_id=user_id)

        username = target_user.username

        # Лог
        AdminLog.objects.create(
            admin=request.user,
            action='delete_user',
            target_user=target_user,
            description=f'Удалён пользователь {username}',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        target_user.delete()
        messages.success(request, f'Пользователь {username} удалён!')
        return redirect('superadmin_panel')

    return render(request, 'superadmin/user_delete.html', {'target_user': target_user})


@login_required
def superadmin_impersonate(request, user_id):
    """Вход под пользователем (от его лица)"""
    if not request.user.is_superuser:
        return redirect('main')

    target_user = get_object_or_404(User, id=user_id)

    if target_user == request.user:
        messages.warning(request, 'Вы уже под этим аккаунтом!')
        return redirect('main')

    # Сохраняем ID настоящего админа в сессии
    request.session['real_admin_id'] = request.user.id

    # Логинимся под пользователем
    from django.contrib.auth import login
    login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')

    # Лог
    AdminLog.objects.create(
        admin=request.user,
        action='impersonate',
        target_user=target_user,
        description=f'Вход под пользователем {target_user.username}',
        ip_address=request.META.get('REMOTE_ADDR')
    )

    messages.info(request, f'Теперь вы действуете от лица {target_user.username}. Выйдите, чтобы вернуться.')
    return redirect('main')


@login_required
def superadmin_exit_impersonate(request):
    """Выход из режима подмены"""
    real_admin_id = request.session.get('real_admin_id')
    if real_admin_id:
        from django.contrib.auth import login
        real_admin = get_object_or_404(User, id=real_admin_id)
        login(request, real_admin, backend='django.contrib.auth.backends.ModelBackend')
        del request.session['real_admin_id']
        messages.info(request, 'Вы вернулись в аккаунт создателя.')
    return redirect('superadmin_panel')


@login_required
def superadmin_edit_message(request, message_id):
    """Редактирование чужого сообщения"""
    if not request.user.is_superuser:
        return redirect('main')

    msg = get_object_or_404(Message, id=message_id)

    if request.method == 'POST':
        admin_password = request.POST.get('admin_password')
        if not request.user.check_password(admin_password):
            messages.error(request, 'Неверный пароль администратора!')
            return redirect('superadmin_edit_message', message_id=message_id)

        old_content = msg.content
        msg.content = request.POST.get('content')
        msg.save()

        AdminLog.objects.create(
            admin=request.user,
            action='edit_message',
            target_user=msg.sender,
            description=f'Сообщение изменено: "{old_content[:30]}" → "{msg.content[:30]}"',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, 'Сообщение изменено!')

        # Возврат в чат
        if msg.group:
            return redirect('group_chat', group_id=msg.group.id)
        elif msg.receiver:
            return redirect('main_chat')

    return render(request, 'superadmin/message_edit.html', {'msg': msg})


@login_required
def superadmin_ban_user(request, user_id):
    """Забанить пользователя"""
    if not request.user.is_superuser:
        return redirect('main')

    target_user = get_object_or_404(User, id=user_id)
    target_user.is_active = False
    target_user.save()

    AdminLog.objects.create(
        admin=request.user,
        action='ban_user',
        target_user=target_user,
        description=f'Пользователь забанен',
        ip_address=request.META.get('REMOTE_ADDR')
    )

    messages.success(request, f'{target_user.username} забанен!')
    return redirect('superadmin_panel')


@login_required
def superadmin_unban_user(request, user_id):
    """Разбанить пользователя"""
    if not request.user.is_superuser:
        return redirect('main')

    target_user = get_object_or_404(User, id=user_id)
    target_user.is_active = True
    target_user.save()

    AdminLog.objects.create(
        admin=request.user,
        action='unban_user',
        target_user=target_user,
        description=f'Пользователь разбанен',
        ip_address=request.META.get('REMOTE_ADDR')
    )

    messages.success(request, f'{target_user.username} разбанен!')
    return redirect('superadmin_panel')


@login_required
def superadmin_ban_user(request, user_id):
    """Забанить пользователя с причиной"""
    if not request.user.is_superuser:
        return redirect('main')

    target_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        reason = request.POST.get('ban_reason', 'Нарушение правил')
        target_user.is_active = False
        target_user.ban_reason = reason
        target_user.banned_at = timezone.now()
        target_user.banned_by = request.user
        target_user.save()

        AdminLog.objects.create(
            admin=request.user,
            action='ban_user',
            target_user=target_user,
            description=f'Пользователь забанен. Причина: {reason}',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f'{target_user.username} забанен!')
        return redirect('superadmin_panel')

    return render(request, 'superadmin/ban_confirm.html', {'target_user': target_user})


@login_required
def superadmin_delete_group(request, group_id):
    """Удаление группы суперпользователем"""
    if not request.user.is_superuser:
        return redirect('main')

    group = get_object_or_404(Group, id=group_id)

    if request.method == 'POST':
        admin_password = request.POST.get('admin_password')
        if not request.user.check_password(admin_password):
            messages.error(request, 'Неверный пароль администратора!')
            return redirect('superadmin_panel')

        group_name = group.name
        messages_count = group.messages.count()
        members_count = group.members.count()

        # Удаляем все сообщения группы (включая файлы)
        for msg in group.messages.all():
            if msg.attachment:
                import os
                from django.conf import settings
                file_path = os.path.join(settings.MEDIA_ROOT, msg.attachment.path)
                if os.path.exists(file_path):
                    os.remove(file_path)

        group.delete()

        AdminLog.objects.create(
            admin=request.user,
            action='delete_user',  # Можно добавить 'delete_group' в choices
            target_user=None,
            description=f'Удалена группа "{group_name}" ({messages_count} сообщений, {members_count} участников)',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f'Группа "{group_name}" удалена!')
        return redirect('superadmin_panel')

    return render(request, 'superadmin/group_delete.html', {'group': group})


@login_required
def superadmin_edit_group(request, group_id):
    """Редактирование группы суперпользователем"""
    if not request.user.is_superuser:
        return redirect('main')

    group = get_object_or_404(Group, id=group_id)

    if request.method == 'POST':
        admin_password = request.POST.get('admin_password')
        if not request.user.check_password(admin_password):
            messages.error(request, 'Неверный пароль администратора!')
            return redirect('superadmin_edit_group', group_id=group_id)

        group.name = request.POST.get('name', group.name)
        group.description = request.POST.get('description', group.description)
        if request.FILES.get('avatar'):
            group.avatar = request.FILES.get('avatar')
        group.save()

        AdminLog.objects.create(
            admin=request.user,
            action='edit_profile',
            target_user=group.owner,
            description=f'Изменена группа "{group.name}"',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f'Группа "{group.name}" обновлена!')
        return redirect('superadmin_panel')

    return render(request, 'superadmin/group_edit.html', {'group': group})
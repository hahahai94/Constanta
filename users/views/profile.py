# users/views/profile.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from users.models import User
from users.forms import ChangeUsernameForm, ChangePasswordForm


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        new_nick = request.POST.get('nick', '').strip()
        new_email = request.POST.get('email', '').strip()

        update_fields = []

        if new_nick and user.nick != new_nick:
            user.nick = new_nick
            update_fields.append('nick')

        if new_email and user.email != new_email:
            user.email = new_email
            update_fields.append('email')

        if request.FILES.get('avatar'):
            user.avatar = request.FILES['avatar']
            update_fields.append('avatar')

        if update_fields:
            user.save(update_fields=update_fields)
            messages.success(request, 'Профиль обновлён!')
        else:
            messages.info(request, 'Изменений не найдено')

        return redirect('profile')

    return render(request, 'profile.html', {'user': user})


@login_required
def users_catalog(request):
    from django.db.models import Q
    q = request.GET.get('q', '').strip()
    if q:
        users = User.objects.filter(
            Q(username__icontains=q) | Q(nick__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        ).exclude(id=request.user.id)
    else:
        users = User.objects.exclude(id=request.user.id)
    return render(request, 'users_catalog.html', {'users': users, 'query': q})


@login_required
def change_username(request):
    if request.method == 'POST':
        form = ChangeUsernameForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.username = form.cleaned_data['username']
            request.user.save()
            messages.success(request, 'Логин изменён')
            return redirect('profile')
    else:
        form = ChangeUsernameForm(user=request.user)
    return render(request, 'change_username.html', {'form': form})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Пароль изменён')
            return redirect('profile')
    else:
        form = ChangePasswordForm(request.user)
    return render(request, 'change_password.html', {'form': form})


def password_done(request):
    return render(request, 'password_done.html')

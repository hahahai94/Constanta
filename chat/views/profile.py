from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from chat.models import User
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from chat.forms import ChangeUsernameForm, ChangePasswordForm

@login_required
def profile_view(request):
    """Страница профиля"""
    user = request.user
    if request.method == 'POST':
        user.nick = request.POST.get('nick', user.nick).strip()
        user.email = request.POST.get('email', user.email).strip()
        if request.FILES.get('avatar'):
            user.avatar = request.FILES.get('avatar')
        user.save()
        messages.success(request, '✅ Профиль обновлён!')
        return redirect('profile')
    return render(request, 'profile.html', {'user': user})

@login_required
def users_catalog(request):
    """Каталог всех пользователей"""
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
            messages.success(request, '✅ Логин изменён')
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
            messages.success(request, '✅ Пароль изменён')
            return redirect('profile')
    else:
        form = ChangePasswordForm(request.user)
    return render(request, 'change_password.html', {'form': form})

def password_done(request):
    return render(request, 'password_done.html')
# users/views/profile.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from users.models import User
from users.forms import ChangeUsernameForm, ChangePasswordForm, ProfileForm


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлён!')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        return redirect('profile')

    return render(request, 'profile.html', {'user': request.user})


@login_required
def users_catalog(request):
    from django.db.models import Q
    from django.core.paginator import Paginator
    q = request.GET.get('q', '').strip()
    if q:
        users_qs = User.objects.filter(
            Q(username__icontains=q) | Q(nick__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        ).exclude(id=request.user.id).order_by('username')
    else:
        users_qs = User.objects.exclude(id=request.user.id).order_by('username')
    paginator = Paginator(users_qs, 20)
    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)
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


@login_required
def public_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    return render(request, 'public_profile.html', {'profile_user': profile_user})

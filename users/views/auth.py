# users/views/auth.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from users.forms import RegistrationForm


def _rate_limit(request, key_prefix, limit=5, period=300):
    """Простой rate limiter через кеш (по умолчанию: 5 попыток за 5 минут)"""
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f"ratelimit:{key_prefix}:{ip}"
    attempts = cache.get(key, 0)
    if attempts >= limit:
        return True, None
    cache.set(key, attempts + 1, period)
    return False, limit - attempts - 1


def auth_view(request):
    mode = request.GET.get('mode', 'login')

    if request.method == 'POST':
        blocked, remaining = _rate_limit(request, 'auth')
        if blocked:
            messages.error(request, '❌ Слишком много попыток. Подождите 5 минут.')
            return render(request, 'auth.html', {'form': AuthenticationForm(), 'type': mode})

        if mode == 'reg' or 'register' in request.POST:
            form = RegistrationForm(request.POST)
            if form.is_valid():
                cache.delete(f"ratelimit:auth:{request.META.get('REMOTE_ADDR', 'unknown')}")
                user = form.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f'✅ Добро пожаловать, {user.username}!')
                return redirect('main')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
                mode = 'reg'
        else:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    cache.delete(f"ratelimit:auth:{request.META.get('REMOTE_ADDR', 'unknown')}")
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    messages.success(request, f'✅ С возвращением, {username}!')
                    return redirect('main')
                else:
                    messages.error(request, '❌ Неверный логин или пароль')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

    if mode == 'reg':
        form = RegistrationForm()
    else:
        form = AuthenticationForm()

    return render(request, 'auth.html', {
        'form': form,
        'type': mode
    })


@login_required
def logout_view(request):
    logout(request)
    return redirect('auth')

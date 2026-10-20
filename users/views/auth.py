# users/views/auth.py
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from users.forms import RegistrationForm
from users.ratelimit import clear, hit, peek
from users.utils import form_error_messages, get_client_ip

User = get_user_model()

# Лимиты подобраны так, чтобы ограничивать подбор пароля, но не мешать
# нормальному входу. Ключевое отличие от прежней схемы: счётчики больше не
# сбрасываются успешным входом или регистрацией (problems.md, П-7).
LOGIN_USER_LIMIT = 5
LOGIN_USER_PERIOD = 900      # 5 неудач на аккаунт за 15 минут
LOGIN_IP_LIMIT = 20
LOGIN_IP_PERIOD = 300        # 20 неудач с одного адреса за 5 минут
REGISTER_IP_LIMIT = 5
REGISTER_IP_PERIOD = 3600    # 5 регистраций с одного адреса за час


def _login_keys(request, username):
    ip = get_client_ip(request) or 'unknown'
    return (
        (f'login_user:{(username or "").strip().lower()}', LOGIN_USER_LIMIT, LOGIN_USER_PERIOD),
        (f'login_ip:{ip}', LOGIN_IP_LIMIT, LOGIN_IP_PERIOD),
    )


def _login_limited(request, username):
    """Проверяет лимиты, не увеличивая счётчики."""
    return not all(peek(key, limit) for key, limit, _ in _login_keys(request, username))


def _record_login_failure(request, username):
    """Учитывает только неудачную попытку.

    Раньше счётчик увеличивался на каждом POST и обнулялся при успехе, из-за
    чего четыре догадки плюс регистрация давали бесконечный подбор.
    """
    for key, limit, period in _login_keys(request, username):
        hit(key, limit, period)


def _register_limit_key(request):
    return f'register_ip:{get_client_ip(request) or "unknown"}'


def _register_limited(request):
    return not peek(_register_limit_key(request), REGISTER_IP_LIMIT)


def _banned_user_with_valid_password(request):
    """Забаненный пользователь, предъявивший верный пароль.

    Проверяем пароль, чтобы сообщение о блокировке не превратилось в способ
    узнать, какие логины существуют.
    """
    username = request.POST.get('username', '')
    password = request.POST.get('password', '')
    user = User.objects.filter(username=username).first()
    if user and user.banned_at and user.check_password(password):
        return user
    return None


def auth_view(request):
    mode = request.GET.get('mode', 'login')

    if request.method == 'POST':
        if mode == 'reg' or 'register' in request.POST:
            if _register_limited(request):
                messages.error(request, '❌ Слишком много попыток регистрации. Попробуйте позже.')
                return render(request, 'auth.html', {'form': RegistrationForm(), 'type': 'reg'})

            hit(_register_limit_key(request), REGISTER_IP_LIMIT, REGISTER_IP_PERIOD)
            form = RegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()
                user.backend = settings.AUTHENTICATION_BACKENDS[0]
                login(request, user)
                return redirect('main')
            for error in form_error_messages(form):
                messages.error(request, error)
            mode = 'reg'
        else:
            username = request.POST.get('username', '')
            if _login_limited(request, username):
                messages.error(
                    request,
                    '❌ Слишком много попыток входа. Подождите и попробуйте снова.',
                )
                return render(request, 'auth.html',
                              {'form': AuthenticationForm(), 'type': 'login'})

            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = authenticate(
                    request,
                    username=form.cleaned_data.get('username'),
                    password=form.cleaned_data.get('password'),
                )
                if user is not None:
                    # Сбрасываем только счётчик этого аккаунта: пароль доказан,
                    # подобрать его это не помогает. Лимит по IP не трогаем.
                    clear(f'login_user:{username.strip().lower()}')
                    login(request, user)
                    return redirect('main')

                _record_login_failure(request, username)
                messages.error(request, '❌ Неверный логин или пароль')
            else:
                _record_login_failure(request, username)
                banned = _banned_user_with_valid_password(request)
                if banned is not None:
                    messages.error(
                        request,
                        f'🚫 Аккаунт заблокирован: {banned.ban_reason or "без указания причины"}',
                    )
                else:
                    for error in form_error_messages(form):
                        messages.error(request, error)

    if mode == 'reg':
        form = RegistrationForm()
    else:
        form = AuthenticationForm()

    return render(request, 'auth.html', {
        'form': form,
        'type': mode
    })


@login_required
@require_POST
def logout_view(request):
    """Выход из аккаунта.

    Только POST: выход через GET уязвим к CSRF — сторонний сайт мог бы
    разлогинить пользователя (problems.md, П-9).
    """
    logout(request)
    return redirect('auth')

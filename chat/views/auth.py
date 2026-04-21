# chat/views/auth.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from chat.forms import RegistrationForm, LoginForm


def auth_view(request):
    # По умолчанию вход. Переключение через ?mode=reg
    mode = request.GET.get('mode', 'login')

    if request.method == 'POST':
        # Если явно запрошена регистрация
        if mode == 'reg' or 'register' in request.POST:
            form = RegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user,backend='chat.backends.CustomAuthBackend')
                return redirect('main')
        else:
            # Вход
            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect('main')  # 302 (тест проходит)
            else:
                messages.error(request, '❌ Неверный логин или пароль')
                mode = 'login'  # При ошибке возвращаемся ко входу

    # GET или ошибка → рендерим нужную форму
    if mode == 'reg':
        form = RegistrationForm()
    else:
        form = LoginForm()  # Показываем вход по умолчанию

    return render(request, 'auth.html', {'form': form, 'type': mode})


@login_required
def logout_view(request):
    logout(request)
    return redirect('auth')
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from chat.forms import RegistrationForm

def auth_view(request):
    # Режим по умолчанию: вход
    mode = request.GET.get('mode', 'login')

    if request.method == 'POST':
        # 🔹 РЕГИСТРАЦИЯ
        if mode == 'reg' or 'register' in request.POST:
            form = RegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('main')
            else:
                mode = 'reg'  # Остаться на форме регистрации при ошибках
        # 🔹 ВХОД
        else:
            form = AuthenticationForm(request.POST)
            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('main')
            else:
                messages.error(request, '❌ Неверный логин или пароль')
                mode = 'login'

    # 🔹 GET-запрос или возврат после ошибки
    if mode == 'reg':
        form = RegistrationForm()
    else:
        form = AuthenticationForm()

    return render(request, 'auth.html', {
        'form': form,
        'type': mode  # Передаёт 'login' или 'reg' в шаблон
    })

@login_required
def logout_view(request):
    logout(request)
    return redirect('auth')
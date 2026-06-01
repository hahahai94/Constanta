# users/views/auth.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from users.forms import RegistrationForm


def auth_view(request):
    mode = request.GET.get('mode', 'login')

    if request.method == 'POST':
        if mode == 'reg' or 'register' in request.POST:
            form = RegistrationForm(request.POST)
            if form.is_valid():
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
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    messages.success(request, f'✅ С возвращением, {username}!')
                    return redirect('main')
                else:
                    messages.error(request, '❌ Неверный логин или пароль')
            else:
                messages.error(request, '❌ Проверьте правильность ввода')

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

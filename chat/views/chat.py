# chat/views/chat.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from chat.models import User, Message


@login_required
def main_chat(request):
    """Главная страница личных сообщений"""
    user = request.user
    friend_id = request.GET.get('friend_id')

    # Активный собеседник (если выбран в URL)
    active_friend = get_object_or_404(User, id=friend_id) if friend_id else None

    # Список всех пользователей для сайдбара (кроме себя)
    # Если позже добавишь модель друзей/чатов, замени этот запрос на неё
    conversations = User.objects.exclude(id=user.id).order_by('username')

    # Загрузка сообщений с активным собеседником
    messages = []
    if active_friend:
        messages = Message.objects.filter(
            Q(sender=user, receiver=active_friend) |
            Q(sender=active_friend, receiver=user)
        ).order_by('created_at')[:100]  # последние 100 сообщений

    return render(request, 'index.html', {
        'conversations': conversations,
        'active_friend': active_friend,
        'messages': messages,
    })
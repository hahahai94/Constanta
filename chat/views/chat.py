# chat/views/chat.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from chat.models import User, Message


def main_chat(request):
    user = request.user

    # 🔹 ПОКАЗЫВАЕМ ТОЛЬКО ТЕХ, С КЕМ ЕСТЬ СООБЩЕНИЯ
    conversations = User.objects.filter(
        Q(sent_messages__receiver=user) | Q(received_messages__sender=user)
    ).exclude(id=user.id).distinct()

    # ИЛИ если хочешь показывать ВСЕХ пользователей (раскомментируй):
    # conversations = User.objects.exclude(id=user.id)

    friend_id = request.GET.get('friend_id')
    active_friend = None
    messages_list = []

    if friend_id:
        try:
            active_friend = User.objects.get(id=friend_id)
            # Загружаем сообщения
            messages_list = Message.objects.filter(
                Q(sender=user, receiver=active_friend) |
                Q(sender=active_friend, receiver=user)
            ).order_by('created_at')
        except User.DoesNotExist:
            pass

    return render(request, 'index.html', {
        'conversations': conversations,
        'active_friend': active_friend,
        'messages': messages_list,
    })
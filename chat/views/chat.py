# chat/views/chat.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from chat.models import User, Message


@login_required
def main_chat(request):
    user = request.user

    # 1️⃣ Получаем пользователей, с кем была переписка
    conversations = User.objects.filter(
        Q(sent_messages__receiver=user) | Q(received_messages__sender=user)
    ).exclude(id=user.id).distinct()

    # 2️⃣ Формируем структуру, которую ждёт шаблон: {'friend': user, 'last_message': msg}
    chats = []
    for friend in conversations:
        last_msg = Message.objects.filter(
            Q(sender=user, receiver=friend) |
            Q(sender=friend, receiver=user)
        ).order_by('-created_at').first()

        chats.append({
            'friend': friend,
            'last_message': last_msg
        })

    friend_id = request.GET.get('friend_id')
    active_friend = None
    messages_list = []

    if friend_id:
        active_friend = get_object_or_404(User, id=friend_id)
        messages_list = Message.objects.filter(
            Q(sender=user, receiver=active_friend) |
            Q(sender=active_friend, receiver=user)
        ).order_by('created_at')

    return render(request, 'index.html', {
        'chats': chats,  # ✅ Теперь здесь список словарей
        'active_friend': active_friend,
        'messages': messages_list,
        'active_group': None,
    })
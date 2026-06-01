# chat/views/chat.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import get_user_model
from chat.models import Message

User = get_user_model()


@login_required
def main_chat(request):
    user = request.user

    from django.db.models import OuterRef, Subquery

    last_msg_subq = Message.objects.filter(
        Q(sender=user, receiver=OuterRef('id')) |
        Q(sender=OuterRef('id'), receiver=user)
    ).order_by('-created_at').values('id')[:1]

    chat_users = User.objects.filter(
        Q(sent_messages__receiver=user) | Q(received_messages__sender=user)
    ).exclude(id=user.id).distinct().annotate(
        last_msg_id=Subquery(last_msg_subq)
    )

    last_msg_ids = [u.last_msg_id for u in chat_users if u.last_msg_id]
    last_messages = {m.id: m for m in Message.objects.filter(id__in=last_msg_ids)}

    chats = [{'friend': u, 'last_message': last_messages.get(u.last_msg_id)} for u in chat_users]

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
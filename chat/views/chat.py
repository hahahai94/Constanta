from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, OuterRef, Subquery
from django.contrib.auth import get_user_model
from chat.models import Message

User = get_user_model()


@login_required
def main_chat(request):
    user = request.user

    last_msg_subq = Message.objects.filter(
        Q(sender=user, receiver=OuterRef('id')) |
        Q(sender=OuterRef('id'), receiver=user),
        is_deleted=False,
    ).order_by('-created_at').values('id')[:1]

    # Удалённые сообщения не должны ни создавать чат, ни попадать в превью
    # списка слева (problems.md, П-20).
    chat_users = User.objects.filter(
        Q(sent_messages__receiver=user, sent_messages__is_deleted=False) |
        Q(received_messages__sender=user, received_messages__is_deleted=False)
    ).exclude(id=user.id).distinct().annotate(
        last_msg_id=Subquery(last_msg_subq)
    )[:100]

    last_msg_ids = [u.last_msg_id for u in chat_users if u.last_msg_id]
    last_messages = {m.id: m for m in Message.objects.filter(id__in=last_msg_ids)}

    chats = [{'user': u, 'last_message': last_messages.get(u.last_msg_id)} for u in chat_users]

    user_id = request.GET.get('user_id')
    active_user = None
    messages = []

    if user_id:
        active_user = get_object_or_404(User, id=user_id)
        # Вся переписка отдаётся сразу: страница прокручивается к последнему
        # сообщению. Постраничная подгрузка «Загрузить ещё» только мешала.
        messages = Message.objects.filter(
            Q(sender=user, receiver=active_user) |
            Q(sender=active_user, receiver=user),
            is_deleted=False,
        ).order_by('created_at')

    return render(request, 'index.html', {
        'chats': chats,
        'active_user': active_user,
        'messages': messages,
        'active_group': None,
    })

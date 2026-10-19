from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, OuterRef, Subquery
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from chat.models import Message
from chat.utils.history import (
    build_earlier_url, load_message_page, parse_before,
)

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
    has_earlier = False
    earlier_url = ''

    if user_id:
        if not str(user_id).isdigit():
            return redirect('main')
        active_user = get_object_or_404(User, id=user_id)
        history = Message.objects.filter(
            Q(sender=user, receiver=active_user) |
            Q(sender=active_user, receiver=user),
            is_deleted=False,
        )
        messages, has_earlier = load_message_page(
            history, parse_before(request.GET.get('before')))
        earlier_url = build_earlier_url(request, messages, has_earlier)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('parts/message_list.html', {
                'messages': messages,
                'user': request.user,
                'request': request,
            })
            return JsonResponse({
                'html': html,
                'has_earlier': has_earlier,
                'earlier_url': earlier_url,
            })

    return render(request, 'index.html', {
        'chats': chats,
        'active_user': active_user,
        'messages': messages,
        'has_earlier': has_earlier,
        'earlier_url': earlier_url,
        'active_group': None,
    })

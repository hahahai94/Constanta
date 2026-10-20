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
from chat.utils.notifications import mark_conversation_read, message_unread_counts

User = get_user_model()


def build_chat_list(user):
    """Личные чаты, отсортированные по последнему сообщению."""
    last_msg_subq = Message.objects.filter(
        Q(sender=user, receiver=OuterRef('id')) |
        Q(sender=OuterRef('id'), receiver=user),
        is_deleted=False,
    ).order_by('-created_at')

    # Удалённые сообщения не должны ни создавать чат, ни попадать в превью
    # списка слева (problems.md, П-20).
    chat_users = User.objects.filter(
        Q(sent_messages__receiver=user, sent_messages__is_deleted=False) |
        Q(received_messages__sender=user, received_messages__is_deleted=False)
    ).exclude(id=user.id).distinct().annotate(
        last_msg_id=Subquery(last_msg_subq.values('id')[:1]),
        last_msg_at=Subquery(last_msg_subq.values('created_at')[:1]),
    ).order_by('-last_msg_at', 'username')[:100]

    last_msg_ids = [u.last_msg_id for u in chat_users if u.last_msg_id]
    last_messages = {
        m.id: m for m in Message.objects.filter(id__in=last_msg_ids)
    }
    unread_counts = message_unread_counts(user)

    return [
        {
            'user': chat_user,
            'last_message': last_messages.get(chat_user.last_msg_id),
            'unread_count': unread_counts.get(
                f'direct:{chat_user.id}', 0),
        }
        for chat_user in chat_users
    ]


@login_required
def main_chat(request):
    user = request.user
    user_id = request.GET.get('user_id')
    active_user = None
    active_chat_id = ''
    messages = []
    has_earlier = False
    earlier_url = ''

    if user_id:
        if not str(user_id).isdigit():
            return redirect('main')
        active_user = get_object_or_404(User, id=user_id)
        active_chat_id = str(active_user.id)
        mark_conversation_read(user, f'direct:{active_user.id}')
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

    chats = build_chat_list(user)
    return render(request, 'index.html', {
        'chats': chats,
        'active_user': active_user,
        'active_chat_id': active_chat_id,
        'active_conversation_key': (
            f'direct:{active_user.id}' if active_user else ''),
        'messages': messages,
        'has_earlier': has_earlier,
        'earlier_url': earlier_url,
        'active_group': None,
    })


@login_required
def chat_list_api(request):
    active_chat_id = request.GET.get('active_user_id', '')
    chats = build_chat_list(request.user)
    html = render_to_string('parts/chat_list.html', {
        'chats': chats,
        'active_chat_id': active_chat_id,
        'request': request,
    }, request=request)
    return JsonResponse({
        'html': html,
        'unread_total': sum(chat['unread_count'] for chat in chats),
    })

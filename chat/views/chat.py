from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, OuterRef, Subquery
from django.contrib.auth import get_user_model
from chat.models import Message

User = get_user_model()

MESSAGES_PER_PAGE = 30


@login_required
def main_chat(request):
    user = request.user

    last_msg_subq = Message.objects.filter(
        Q(sender=user, receiver=OuterRef('id')) |
        Q(sender=OuterRef('id'), receiver=user)
    ).order_by('-created_at').values('id')[:1]

    chat_users = User.objects.filter(
        Q(sent_messages__receiver=user) | Q(received_messages__sender=user)
    ).exclude(id=user.id).distinct().annotate(
        last_msg_id=Subquery(last_msg_subq)
    )[:100]

    last_msg_ids = [u.last_msg_id for u in chat_users if u.last_msg_id]
    last_messages = {m.id: m for m in Message.objects.filter(id__in=last_msg_ids)}

    chats = [{'friend': u, 'last_message': last_messages.get(u.last_msg_id)} for u in chat_users]

    friend_id = request.GET.get('friend_id')
    active_friend = None
    messages_page = None

    if friend_id:
        active_friend = get_object_or_404(User, id=friend_id)
        messages_qs = Message.objects.filter(
            Q(sender=user, receiver=active_friend) |
            Q(sender=active_friend, receiver=user)
        ).order_by('created_at')
        paginator = Paginator(messages_qs, MESSAGES_PER_PAGE)
        page_number = request.GET.get('page', paginator.num_pages)
        messages_page = paginator.get_page(page_number)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and 'page' in request.GET and messages_page:
        from django.template.loader import render_to_string
        html = render_to_string('parts/message_list.html', {
            'messages': messages_page,
            'request': request,
            'user': request.user,
        })
        from django.http import JsonResponse
        return JsonResponse({
            'html': html,
            'has_previous': messages_page.has_previous(),
            'page': messages_page.number,
        })

    return render(request, 'index.html', {
        'chats': chats,
        'active_friend': active_friend,
        'messages': messages_page.object_list if messages_page else [],
        'messages_page': messages_page,
        'active_group': None,
    })

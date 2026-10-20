import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_POST
from chat.models import Channel, ChannelMember, Message
from chat.utils import html_429, normalize_conversation_name, rate_limit
from chat.utils.uploads import normalize_avatar

POSTS_PER_PAGE = 30
CHANNEL_LIST_LIMIT = 100
DISCOVER_LIST_LIMIT = 60


@login_required
def channel_list(request):
    """Список каналов пользователя.

    Списки ограничены: раньше страница рендерила все подписки и все публичные
    каналы разом (problems.md, П-28).
    """
    memberships = ChannelMember.objects.filter(
        user=request.user
    ).select_related('channel').order_by('channel__name')[:CHANNEL_LIST_LIMIT]
    subscribed_ids = ChannelMember.objects.filter(
        user=request.user).values_list('channel_id', flat=True)
    discover_channels = Channel.objects.filter(
        is_private=False
    ).exclude(id__in=subscribed_ids).order_by('name')[:DISCOVER_LIST_LIMIT]
    return render(request, 'channels.html', {
        'memberships': memberships,
        'discover_channels': discover_channels,
    })


@login_required
def channel_view(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    membership = ChannelMember.objects.filter(channel=channel, user=request.user).first()
    if not membership:
        messages.error(request, 'Вы не подписаны на этот канал')
        return redirect('channel_list')
    can_post = membership.role in ['owner', 'admin']
    invite_url = ''
    if can_post:
        invite_url = request.build_absolute_uri(reverse('channel_invite', args=[channel.invite_token]))
    posts_qs = Message.objects.filter(
        channel=channel, is_deleted=False
    ).select_related('sender').order_by('-created_at')
    paginator = Paginator(posts_qs, POSTS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    posts_page = paginator.get_page(page_number)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and 'page' in request.GET:
        from django.template.loader import render_to_string
        html = render_to_string('parts/channel_post_list.html', {
            'posts': posts_page,
            'request': request,
        })
        from django.http import JsonResponse
        return JsonResponse({
            'html': html,
            'has_next': posts_page.has_next(),
            'page': posts_page.number,
        })

    return render(request, 'channel_view.html', {
        'channel': channel,
        'posts': posts_page.object_list,
        'posts_page': posts_page,
        'can_post': can_post,
        'invite_url': invite_url,
        'membership': membership,
    })


@login_required
@rate_limit('create_channel', limit=10, period=300, on_limited=html_429)
def create_channel(request):
    if request.method == 'POST':
        try:
            name = normalize_conversation_name(request.POST.get('name', ''))
        except ValidationError as exc:
            messages.error(request, f'❌ {exc.messages[0]}')
            return redirect('channel_list')
        if Channel.objects.filter(owner=request.user).count() >= settings.MAX_CHANNELS_PER_USER:
            # раньше каналы не ограничивались вовсе, в отличие от групп (П-28)
            messages.error(
                request, f'❌ Лимит каналов ({settings.MAX_CHANNELS_PER_USER})')
            return redirect('channel_list')
        is_private = request.POST.get('is_private') == '1'
        channel = Channel.objects.create(name=name, owner=request.user, is_private=is_private)
        ChannelMember.objects.create(channel=channel, user=request.user, role='owner')
        return redirect('channel_view', channel_id=channel.id)
    return redirect('channel_list')


@login_required
@rate_limit('edit_channel', limit=20, period=300, on_limited=html_429)
def edit_channel(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    if not channel.is_admin(request.user):
        messages.error(request, 'Нет прав')
        return redirect('channel_view', channel_id=channel_id)
    if request.method == 'POST':
        try:
            name = normalize_conversation_name(
                request.POST.get('name', channel.name))
        except ValidationError as exc:
            messages.error(request, f'❌ {exc.messages[0]}')
            return redirect('channel_view', channel_id=channel_id)

        old_avatar = channel.avatar
        old_avatar_name = old_avatar.name if old_avatar else ''
        old_avatar_storage = old_avatar.storage if old_avatar else None
        avatar = request.FILES.get('avatar')
        if avatar:
            # Проверяем до применения изменений (problems.md, П-3).
            try:
                normalize_avatar(avatar)
            except ValidationError as exc:
                message = exc.messages[0] if exc.messages else 'Недопустимый файл'
                messages.error(request, f'❌ {message}')
                return redirect('channel_view', channel_id=channel_id)

        channel.name = name
        channel.description = request.POST.get('description', channel.description).strip()
        channel.is_private = request.POST.get('is_private') == '1'
        if avatar:
            channel.avatar = avatar
        channel.save()
        if (old_avatar_name and channel.avatar
                and old_avatar_name != channel.avatar.name):
            old_avatar_storage.delete(old_avatar_name)
        return redirect('channel_view', channel_id=channel_id)
    membership = ChannelMember.objects.filter(channel=channel, user=request.user).first()
    posts_qs = Message.objects.filter(
        channel=channel, is_deleted=False
    ).select_related('sender').order_by('-created_at')
    paginator = Paginator(posts_qs, POSTS_PER_PAGE)
    posts_page = paginator.get_page(1)
    return render(request, 'channel_view.html', {
        'channel': channel, 'posts': posts_page.object_list,
        'posts_page': posts_page, 'can_post': True,
        'membership': membership, 'edit_mode': True,
    })


@login_required
def delete_channel(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    if channel.owner != request.user:
        messages.error(request, 'Только владелец может удалить канал')
        return redirect('channel_view', channel_id=channel_id)
    if request.method == 'POST':
        channel.delete()
    return redirect('channel_list')


@login_required
@require_POST
def join_channel(request, channel_id):
    """Подписка на публичный канал. Только POST (problems.md, П-9)."""
    channel = get_object_or_404(Channel, id=channel_id)
    if channel.is_private:
        messages.error(request, 'Это приватный канал — подписка только по приглашению')
        return redirect('channel_list')
    if ChannelMember.objects.filter(channel=channel, user=request.user).exists():
        messages.warning(request, 'Вы уже подписаны')
    else:
        ChannelMember.objects.create(channel=channel, user=request.user, role='subscriber')
        messages.success(request, f'Вы подписались на {channel.name}')
    return redirect('channel_view', channel_id=channel_id)


@login_required
@require_POST
def leave_channel(request, channel_id):
    """Отписка от канала. Только POST (problems.md, П-9)."""
    channel = get_object_or_404(Channel, id=channel_id)
    if channel.owner == request.user:
        messages.error(request, 'Владелец не может отписаться')
        return redirect('channel_view', channel_id=channel_id)
    ChannelMember.objects.filter(channel=channel, user=request.user).delete()
    messages.success(request, 'Вы отписались от канала')
    return redirect('channel_list')


@login_required
def channel_invite(request, token):
    """Подписка по ссылке-приглашению (работает и для приватных каналов)."""
    channel = get_object_or_404(Channel, invite_token=token)
    if ChannelMember.objects.filter(channel=channel, user=request.user).exists():
        messages.info(request, 'Вы уже подписаны на этот канал')
        return redirect('channel_view', channel_id=channel.id)

    if request.method == 'POST':
        ChannelMember.objects.create(channel=channel, user=request.user, role='subscriber')
        messages.success(request, f'Вы подписались на {channel.name}')
        return redirect('channel_view', channel_id=channel.id)

    return render(request, 'channel_invite.html', {'channel': channel})


@login_required
def regenerate_invite(request, channel_id):
    """Пересоздание ссылки-приглашения (только владелец)."""
    channel = get_object_or_404(Channel, id=channel_id)
    if channel.owner != request.user:
        messages.error(request, 'Нет прав')
        return redirect('channel_view', channel_id=channel_id)
    if request.method == 'POST':
        channel.invite_token = uuid.uuid4()
        channel.save(update_fields=['invite_token'])
        messages.success(request, 'Ссылка-приглашение обновлена')
    return redirect('channel_view', channel_id=channel_id)

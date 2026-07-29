from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
from chat.models import Channel, ChannelMember, Message

POSTS_PER_PAGE = 30


@login_required
def channel_list(request):
    memberships = ChannelMember.objects.filter(user=request.user).select_related('channel').order_by('channel__name')
    subscribed_ids = memberships.values_list('channel_id', flat=True)
    discover_channels = Channel.objects.filter(is_private=False).exclude(id__in=subscribed_ids).order_by('name')
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
    posts_qs = Message.objects.filter(channel=channel, is_deleted=False).order_by('-created_at')
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
        'membership': membership,
    })


@login_required
def create_channel(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            channel = Channel.objects.create(name=name, owner=request.user)
            ChannelMember.objects.create(channel=channel, user=request.user, role='owner')
            return redirect('channel_view', channel_id=channel.id)
    return redirect('channel_list')


@login_required
def edit_channel(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    if not channel.is_admin(request.user):
        messages.error(request, 'Нет прав')
        return redirect('channel_view', channel_id=channel_id)
    if request.method == 'POST':
        channel.name = request.POST.get('name', channel.name).strip()
        channel.description = request.POST.get('description', channel.description).strip()
        if request.FILES.get('avatar'):
            channel.avatar = request.FILES['avatar']
        channel.save()
        return redirect('channel_view', channel_id=channel_id)
    membership = ChannelMember.objects.filter(channel=channel, user=request.user).first()
    posts_qs = Message.objects.filter(channel=channel, is_deleted=False).order_by('-created_at')
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
def join_channel(request, channel_id):
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
def leave_channel(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    if channel.owner == request.user:
        messages.error(request, 'Владелец не может отписаться')
        return redirect('channel_view', channel_id=channel_id)
    ChannelMember.objects.filter(channel=channel, user=request.user).delete()
    messages.success(request, 'Вы отписались от канала')
    return redirect('channel_list')

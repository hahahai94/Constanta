import re


def parse_mentions(content, group=None, receiver=None):
    mentioned_user_ids = []

    if group and '@all' in content:
        from chat.models import GroupMember
        members = GroupMember.objects.filter(group=group).values_list('user_id', flat=True)
        mentioned_user_ids.extend(members)
        content = re.sub(
            r'@all\b',
            '<span class="mention mention-all">@all</span>',
            content
        )

    from django.contrib.auth import get_user_model
    from django.utils.html import format_html
    User = get_user_model()

    pattern = r'@(\w+)'
    matches = re.findall(pattern, content)
    usernames = [m for m in matches if m != 'all']

    if usernames:
        users_map = {u.username: u for u in User.objects.filter(username__in=usernames)}
        for username in usernames:
            user = users_map.get(username)
            if user and user.id not in mentioned_user_ids:
                mentioned_user_ids.append(user.id)
                link = format_html(
                    '<a href="/user/{}/" class="mention" target="_blank">@{}</a>',
                    username, username
                )
                content = re.sub(
                    f'@{username}\\b',
                    str(link),
                    content
                )

    return content, list(set(mentioned_user_ids))

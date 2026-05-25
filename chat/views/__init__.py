from .auth import auth_view, logout_view
from .chat import main_chat
from .group import (
    groups_list, group_chat, create_group, edit_group,
    add_member, remove_member, change_role
)
from .api import send_message, api_heartbeat, download_attachment, api_set_role, api_remove_member, api_add_member, api_update_group
from .profile import profile_view, users_catalog, change_username, change_password, password_done

__all__ = [
    'auth_view', 'logout_view', 'main_chat',
    'groups_list', 'group_chat', 'create_group', 'edit_group',
    'add_member', 'remove_member', 'change_role',
    'send_message', 'api_heartbeat',
    'profile_view', 'users_catalog', 'change_username', 'change_password', 'password_done',
]
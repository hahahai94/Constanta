from django.urls import path
from . import views\


# В начале файла определи секретный ключ
SUPERADMIN_KEY = 'django'  # ← Поменяй на свой!

urlpatterns = [
    path('', views.main_chat, name='main'),
    path('tech/', views.tech_page, name='tech'),
    path('tech/check', views.tech_check, name='tech_check'),
    path('reg/', views.reg_view, name='reg'),
    path('auth/', views.auth_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('chat/files/friend/<int:friend_id>/', views.chat_files, name='chat_files_friend'),
    path('chat/files/group/<uuid:group_id>/', views.chat_files, name='chat_files_group'),
    path('api/heartbeat/', views.heartbeat, name='api_heartbeat'),

    # Профиль и настройки
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/username/', views.change_username, name='change_username'),
    path('profile/password/', views.change_password, name='change_password'),

    # Пользователи
    path('user/<str:nick>/', views.user_detail, name='user_detail'),
    path('users/', views.users_catalog, name='users_catalog'),

    # Друзья
    path('friends/', views.friends_list, name='friends'),
    path('friends/add/', views.friends_add, name='friends_add'),
    path('friends/remove/<int:friend_id>/', views.friends_remove, name='friends_remove'),
    path('friends/delete/<int:friend_id>/', views.friends_delete, name='friends_delete'),

    # Группы
    path('groups/', views.groups_list, name='groups'),
    path('groups/create/', views.group_create, name='group_create'),
    path('groups/create/', views.create_group, name='create_group'),
    path('groups/<uuid:group_id>/', views.group_chat, name='group_chat'),
    path('groups/<uuid:group_id>/add/', views.group_add_member, name='group_add_member'),
    path('groups/<uuid:group_id>/remove/<int:user_id>/', views.group_remove_member, name='group_remove_member'),
    path('groups/<uuid:group_id>/role/<int:user_id>/', views.group_change_role, name='group_change_role'),
    path('groups/<uuid:group_id>/leave/', views.group_leave, name='group_leave'),
    path('groups/<uuid:group_id>/delete/', views.group_delete, name='group_delete'),
    path('groups/<uuid:group_id>/edit/', views.group_edit, name='group_edit'),
    path('group/<uuid:group_id>/edit/', views.edit_group, name='edit_group'),
    path('group/<uuid:group_id>/add-member/', views.add_member, name='add_member'),
    path('group/<uuid:group_id>/remove-member/<int:user_id>/', views.remove_member, name='remove_member'),
    path('group/<uuid:group_id>/change-role/<int:user_id>/<str:new_role>/', views.change_role, name='change_role'),

    # API
    path('api/send/', views.send_message, name='api_send'),
    path('api/fetch/', views.fetch_messages, name='api_fetch'),
    path('api/message/delete/<uuid:message_id>/', views.delete_message, name='delete_message'),

    # Уведомления
    path('api/notifications/', views.get_notifications, name='api_notifications'),
    path('api/notifications/<uuid:notification_id>/read/', views.mark_notification_read, name='api_notification_read'),
    path('api/notifications/read-all/', views.mark_all_notifications_read, name='api_notifications_read_all'),

    # СУПЕР АДМИНКА (с секретным ключом)
    path(f'superadmin/{SUPERADMIN_KEY}/', views.superadmin_panel, name='superadmin_panel'),
    path(f'superadmin/{SUPERADMIN_KEY}/user/<int:user_id>/edit/', views.superadmin_user_edit,
         name='superadmin_user_edit'),
    path(f'superadmin/{SUPERADMIN_KEY}/user/<int:user_id>/delete/', views.superadmin_delete_user,
         name='superadmin_delete_user'),
    path(f'superadmin/{SUPERADMIN_KEY}/user/<int:user_id>/impersonate/', views.superadmin_impersonate,
         name='superadmin_impersonate'),
    path(f'superadmin/{SUPERADMIN_KEY}/user/<int:user_id>/ban/', views.superadmin_ban_user, name='superadmin_ban_user'),
    path(f'superadmin/{SUPERADMIN_KEY}/user/<int:user_id>/unban/', views.superadmin_unban_user,
         name='superadmin_unban_user'),
    path(f'superadmin/{SUPERADMIN_KEY}/message/<uuid:message_id>/edit/', views.superadmin_edit_message,
         name='superadmin_edit_message'),
    path(f'superadmin/{SUPERADMIN_KEY}/exit/', views.superadmin_exit_impersonate, name='superadmin_exit_impersonate'),
    path(f'superadmin/{SUPERADMIN_KEY}/group/<uuid:group_id>/delete/', views.superadmin_delete_group, name='superadmin_delete_group'),
    path(f'superadmin/{SUPERADMIN_KEY}/group/<uuid:group_id>/edit/', views.superadmin_edit_group, name='superadmin_edit_group'),
]
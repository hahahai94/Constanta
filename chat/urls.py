from django.urls import path
from . import views

urlpatterns = [
    path('', views.main_chat, name='main'),

    path('groups/', views.groups_list, name='groups'),
    path('groups/create/', views.create_group, name='create_group'),
    path('group/<uuid:group_id>/', views.group_chat, name='group_chat'),
    path('group/<uuid:group_id>/edit/', views.edit_group, name='edit_group'),
    path('group/<uuid:group_id>/add-member/', views.add_member, name='add_member'),
    path('group/<uuid:group_id>/remove-member/<int:user_id>/', views.remove_member, name='remove_member'),
    path('group/<uuid:group_id>/change-role/<int:user_id>/<str:new_role>/', views.change_role, name='change_role'),

    path('channels/', views.channel_list, name='channel_list'),
    path('channel/<uuid:channel_id>/', views.channel_view, name='channel_view'),
    path('channel/create/', views.create_channel, name='create_channel'),
    path('channel/<uuid:channel_id>/edit/', views.edit_channel, name='edit_channel'),
    path('channel/<uuid:channel_id>/delete/', views.delete_channel, name='delete_channel'),
    path('channel/<uuid:channel_id>/join/', views.join_channel, name='join_channel'),
    path('channel/<uuid:channel_id>/leave/', views.leave_channel, name='leave_channel'),

    path('api/send/', views.send_message, name='api_send'),
    path('api/heartbeat/', views.api_heartbeat, name='api_heartbeat'),
    path('api/channel/<uuid:channel_id>/post/', views.api_channel_post, name='api_channel_post'),
    path('download/<uuid:message_id>/', views.download_attachment, name='download_attachment'),
    path('api/set-role/', views.api_set_role, name='api_set_role'),
    path('api/remove-member/', views.api_remove_member, name='api_remove_member'),
    path('api/add-member/', views.api_add_member, name='api_add_member'),
    path('groups/<uuid:group_id>/settings/', views.api_update_group, name='api_update_group'),
]
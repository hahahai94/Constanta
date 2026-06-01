from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
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

    path('api/send/', views.send_message, name='api_send'),
    path('api/heartbeat/', views.api_heartbeat, name='api_heartbeat'),
    path('download/<uuid:message_id>/', views.download_attachment, name='download_attachment'),
    path('api/set-role/', views.api_set_role, name='api_set_role'),
    path('api/remove-member/', views.api_remove_member, name='api_remove_member'),
    path('api/add-member/', views.api_add_member, name='api_add_member'),
    path('groups/<uuid:group_id>/settings/', views.api_update_group, name='api_update_group'),
]

# 🔹 Раздача медиа (только для разработки)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
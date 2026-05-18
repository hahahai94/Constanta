from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # 🔐 Авторизация
    path('auth/', views.auth_view, name='auth'),
    path('logout/', views.logout_view, name='logout'),

    # 💬 Личный чат
    path('', views.main_chat, name='main'),

    # 👤 Профиль и настройки
    path('profile/', views.profile_view, name='profile'),
    path('profile/change-username/', views.change_username, name='change_username'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/password-done/', views.password_done, name='password_done'),

    # 👥 Каталог
    path('users/', views.users_catalog, name='users_catalog'),

    # 📁 Группы
    path('groups/', views.groups_list, name='groups'),
    path('groups/create/', views.create_group, name='create_group'),
    path('group/<uuid:group_id>/', views.group_chat, name='group_chat'),
    path('group/<uuid:group_id>/edit/', views.edit_group, name='edit_group'),
    path('group/<uuid:group_id>/add-member/', views.add_member, name='add_member'),
    path('group/<uuid:group_id>/remove-member/<int:user_id>/', views.remove_member, name='remove_member'),
    path('group/<uuid:group_id>/change-role/<int:user_id>/<str:new_role>/', views.change_role, name='change_role'),

    # ⚡ API
    path('api/send/', views.send_message, name='api_send'),
    path('api/heartbeat/', views.api_heartbeat, name='api_heartbeat'),
]

# 🔹 Раздача медиа (только для разработки)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
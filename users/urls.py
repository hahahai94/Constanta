from django.urls import path
from users import views

urlpatterns = [
    path('auth/', views.auth_view, name='auth'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/change-username/', views.change_username, name='change_username'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/password-done/', views.password_done, name='password_done'),
    path('users/', views.users_catalog, name='users_catalog'),
    path('users/<str:username>/', views.public_profile, name='public_profile'),
]

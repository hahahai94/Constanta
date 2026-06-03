from django.urls import path
from tasks import views

urlpatterns = [
    path('', views.task_lists, name='task_lists'),
    path('create/', views.create_task_list, name='create_task_list'),
    path('<int:list_id>/', views.task_list_detail, name='task_list_detail'),
    path('<int:list_id>/edit/', views.edit_task_list, name='edit_task_list'),
    path('<int:list_id>/delete/', views.delete_task_list, name='delete_task_list'),
]

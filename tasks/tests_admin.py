from django.test import TestCase
from django.contrib.auth import get_user_model
from tasks.models import TaskList, Task

User = get_user_model()


class TaskAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='taskadmin', password='123')
        self.client.login(username='taskadmin', password='123')
        self.task_list = TaskList.objects.create(name='Admin List', owner=self.admin)

    def test_admin_tasklist_list(self):
        response = self.client.get('/admin/tasks/tasklist/')
        self.assertEqual(response.status_code, 200)

    def test_admin_task_list(self):
        Task.objects.create(task_list=self.task_list, title='Admin Task', created_by=self.admin)
        response = self.client.get('/admin/tasks/task/')
        self.assertEqual(response.status_code, 200)

    def test_progress_bar(self):
        Task.objects.create(task_list=self.task_list, title='Done', created_by=self.admin, is_done=True)
        Task.objects.create(task_list=self.task_list, title='Not done', created_by=self.admin)
        response = self.client.get('/admin/tasks/tasklist/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'progress-bar')

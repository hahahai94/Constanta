from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from tasks.models import TaskList, Task

User = get_user_model()


class TaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass1234')

    def test_create_task_list(self):
        lst = TaskList.objects.create(name='Test List', owner=self.user)
        self.assertEqual(str(lst), 'Test List')
        self.assertEqual(lst.task_count(), 0)
        self.assertEqual(lst.done_count(), 0)

    def test_create_task(self):
        lst = TaskList.objects.create(name='Test List', owner=self.user)
        task = Task.objects.create(
            task_list=lst,
            title='Test Task',
            created_by=self.user,
        )
        self.assertEqual(str(task), 'Test Task')
        self.assertFalse(task.is_done)
        self.assertIsNone(task.completed_at)

    def test_task_ordering(self):
        lst = TaskList.objects.create(name='Test List', owner=self.user)
        t1 = Task.objects.create(task_list=lst, title='A', created_by=self.user, is_done=False)
        t2 = Task.objects.create(task_list=lst, title='B', created_by=self.user, is_done=True)
        tasks = lst.tasks.all()
        self.assertEqual(tasks[0], t1)  # not done first
        self.assertEqual(tasks[1], t2)  # done second

    def test_task_counters(self):
        lst = TaskList.objects.create(name='Test List', owner=self.user)
        Task.objects.create(task_list=lst, title='A', created_by=self.user, is_done=True)
        Task.objects.create(task_list=lst, title='B', created_by=self.user, is_done=False)
        self.assertEqual(lst.task_count(), 2)
        self.assertEqual(lst.done_count(), 1)


class TaskViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.list = TaskList.objects.create(name='My List', owner=self.user)

    def test_task_lists_redirect_anonymous(self):
        response = self.client.get(reverse('task_lists'))
        self.assertNotEqual(response.status_code, 200)

    def test_task_lists_authenticated(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('task_lists'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My List')

    def test_create_task_list_post(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(reverse('create_task_list'), {'name': 'New List'})
        self.assertRedirects(response, reverse('task_lists'))
        self.assertEqual(TaskList.objects.filter(name='New List').count(), 1)

    def test_task_list_detail(self):
        self.client.login(username='testuser', password='pass1234')
        Task.objects.create(task_list=self.list, title='My Task', created_by=self.user)
        response = self.client.get(reverse('task_list_detail', args=[self.list.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Task')

    def test_add_task(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(reverse('task_list_detail', args=[self.list.id]), {
            'action': 'add_task',
            'title': 'New Task',
        })
        self.assertRedirects(response, reverse('task_list_detail', args=[self.list.id]))
        self.assertEqual(Task.objects.count(), 1)

    def test_toggle_task(self):
        self.client.login(username='testuser', password='pass1234')
        task = Task.objects.create(task_list=self.list, title='Task', created_by=self.user)
        self.client.post(reverse('task_list_detail', args=[self.list.id]), {
            'action': 'toggle_task',
            'task_id': task.id,
        })
        task.refresh_from_db()
        self.assertTrue(task.is_done)

    def test_delete_task(self):
        self.client.login(username='testuser', password='pass1234')
        task = Task.objects.create(task_list=self.list, title='Task', created_by=self.user)
        self.client.post(reverse('task_list_detail', args=[self.list.id]), {
            'action': 'delete_task',
            'task_id': task.id,
        })
        self.assertEqual(Task.objects.count(), 0)

    def test_edit_task(self):
        self.client.login(username='testuser', password='pass1234')
        task = Task.objects.create(task_list=self.list, title='Old', created_by=self.user)
        self.client.post(reverse('task_list_detail', args=[self.list.id]), {
            'action': 'edit_task',
            'task_id': task.id,
            'title': 'Updated',
        })
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated')

    def test_delete_task_list(self):
        self.client.login(username='testuser', password='pass1234')
        self.client.post(reverse('delete_task_list', args=[self.list.id]))
        self.assertEqual(TaskList.objects.count(), 0)

    def test_cannot_access_other_users_list(self):
        other = User.objects.create_user(username='other', password='pass1234')
        other_list = TaskList.objects.create(name='Other', owner=other)
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('task_list_detail', args=[other_list.id]))
        self.assertEqual(response.status_code, 404)

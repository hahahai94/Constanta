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
        self.assertEqual(lst.task_count, 0)
        self.assertEqual(lst.done_count, 0)

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
        self.assertEqual(lst.task_count, 2)
        self.assertEqual(lst.done_count, 1)

    def test_counters_use_annotations_when_present(self):
        """П-18: аннотированные значения не должны вызывать новых запросов."""
        from django.db.models import Count, Q
        lst = TaskList.objects.create(name='Annotated', owner=self.user)
        Task.objects.create(task_list=lst, title='A', created_by=self.user, is_done=True)
        Task.objects.create(task_list=lst, title='B', created_by=self.user, is_done=False)

        annotated = TaskList.objects.annotate(
            _task_count=Count('tasks', distinct=True),
            _done_count=Count('tasks', filter=Q(tasks__is_done=True), distinct=True),
        ).get(pk=lst.pk)
        with self.assertNumQueries(0):
            self.assertEqual(annotated.task_count, 2)
            self.assertEqual(annotated.done_count, 1)


class TaskValidationTests(TestCase):
    """П-19: длина проверяется формой, а не «как получится»."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='valid_user', password='pass1234')
        self.client.login(username='valid_user', password='pass1234')
        self.task_list = TaskList.objects.create(name='List', owner=self.user)

    def test_overlong_list_name_rejected(self):
        self.client.post(reverse('create_task_list'), {'name': 'x' * 101, 'description': ''})
        self.assertFalse(TaskList.objects.filter(name='x' * 101).exists())

    def test_overlong_task_title_rejected(self):
        self.client.post(reverse('task_list_detail', args=[self.task_list.id]), {
            'action': 'add_task', 'title': 'x' * 201, 'description': '',
        })
        self.assertFalse(Task.objects.filter(task_list=self.task_list).exists())

    def test_boundary_length_accepted(self):
        self.client.post(reverse('task_list_detail', args=[self.task_list.id]), {
            'action': 'add_task', 'title': 'x' * 200, 'description': '',
        })
        self.assertTrue(Task.objects.filter(title='x' * 200).exists())


class TaskPaginationTests(TestCase):
    """П-18: и списки, и задачи выводятся постранично."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='page_user', password='pass1234')
        self.client.login(username='page_user', password='pass1234')

    def test_task_lists_pagination(self):
        for index in range(25):
            TaskList.objects.create(name=f'List {index}', owner=self.user)

        first = self.client.get(reverse('task_lists'))
        self.assertEqual(len(first.context['lists']), 20)

        second = self.client.get(reverse('task_lists'), {'page': 2})
        self.assertEqual(len(second.context['lists']), 5)

    def test_tasks_pagination(self):
        task_list = TaskList.objects.create(name='Big', owner=self.user)
        for index in range(35):
            Task.objects.create(
                task_list=task_list, title=f'Task {index}', created_by=self.user)

        response = self.client.get(reverse('task_list_detail', args=[task_list.id]))
        self.assertEqual(len(response.context['tasks']), 30)


class CompletedAtTests(TestCase):
    """П-40: completed_at выставляется и снимается вместе с флагом."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='done_user', password='pass1234')
        self.client.login(username='done_user', password='pass1234')
        self.task_list = TaskList.objects.create(name='L', owner=self.user)
        self.task = Task.objects.create(
            task_list=self.task_list, title='T', created_by=self.user)

    def _toggle(self):
        return self.client.post(reverse('task_list_detail', args=[self.task_list.id]), {
            'action': 'toggle_task', 'task_id': self.task.id,
        })

    def test_completed_at_set_and_cleared(self):
        self._toggle()
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)
        self.assertIsNotNone(self.task.completed_at)

        self._toggle()
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_done)
        self.assertIsNone(self.task.completed_at)


class UnknownActionTests(TestCase):
    """П-19: неизвестное действие не должно молча ничего не делать."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='action_user', password='pass1234')
        self.client.login(username='action_user', password='pass1234')
        self.task_list = TaskList.objects.create(name='L', owner=self.user)

    def test_unknown_action_redirects_without_changes(self):
        response = self.client.post(reverse('task_list_detail', args=[self.task_list.id]), {
            'action': 'drop_database',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TaskList.objects.filter(pk=self.task_list.pk).exists())


class TaskViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.list = TaskList.objects.create(name='My List', owner=self.user)

    def test_task_lists_redirect_anonymous(self):
        response = self.client.get(reverse('task_lists'))
        self.assertEqual(response.status_code, 302)

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

    def test_delete_task_list_get_redirect(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('delete_task_list', args=[self.list.id]))
        self.assertRedirects(response, reverse('task_lists'))
        self.assertEqual(TaskList.objects.count(), 1)

    def test_cannot_access_other_users_list(self):
        other = User.objects.create_user(username='other', password='pass1234')
        other_list = TaskList.objects.create(name='Other', owner=other)
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('task_list_detail', args=[other_list.id]))
        self.assertEqual(response.status_code, 404)

    def test_create_task_list_get(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('create_task_list'))
        self.assertRedirects(response, reverse('task_lists'))

    def test_edit_task_list_get(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('edit_task_list', args=[self.list.id]))
        self.assertRedirects(response, reverse('task_lists'))

    def test_edit_task_list_post(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(reverse('edit_task_list', args=[self.list.id]), {
            'name': 'Updated Name'
        })
        self.assertRedirects(response, reverse('task_lists'))
        self.list.refresh_from_db()
        self.assertEqual(self.list.name, 'Updated Name')

    def test_edit_task_list_post_empty_name(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(reverse('edit_task_list', args=[self.list.id]), {
            'name': ''
        })
        self.assertRedirects(response, reverse('task_lists'))
        self.list.refresh_from_db()
        self.assertEqual(self.list.name, 'My List')

    def test_add_task_empty_title(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(reverse('task_list_detail', args=[self.list.id]), {
            'action': 'add_task',
            'title': '',
        })
        self.assertRedirects(response, reverse('task_list_detail', args=[self.list.id]))
        self.assertEqual(Task.objects.count(), 0)

    def test_edit_task_empty_title(self):
        self.client.login(username='testuser', password='pass1234')
        task = Task.objects.create(task_list=self.list, title='Old', created_by=self.user)
        response = self.client.post(reverse('task_list_detail', args=[self.list.id]), {
            'action': 'edit_task',
            'task_id': task.id,
            'title': '',
        })
        self.assertRedirects(response, reverse('task_list_detail', args=[self.list.id]))
        task.refresh_from_db()
        self.assertEqual(task.title, 'Old')

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from tasks.models import STATUS_CHOICES, TaskHistory, User, Task
from datetime import date


class APIReadTestCases(TestCase):
    """Test read operations on API"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="bruce_wayne", email="bruce@wayne.org")
        self.user.set_password("i_am_batman")
        self.user.save()

    def test_task_list(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        response = self.client.get("/api/v1/task/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_instance(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        task = Task.objects.create(
            title="Buy Milk!",
            description="From Milk shop",
            priority=10,
            completed=False,
            status=STATUS_CHOICES[0][0],
            user=self.user,
        )
        task.save()
        response = self.client.get(f"/api/v1/task/{task.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_history_list(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        task = Task.objects.create(
            title="Buy Milk!",
            description="From Milk shop",
            priority=10,
            completed=False,
            status=STATUS_CHOICES[0][0],
            user=self.user,
        )
        task.save()
        response = self.client.get(f"/api/v1/task/{task.id}/history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_history_instance(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        task = Task.objects.create(
            title="Buy Milk!",
            description="From Milk shop",
            priority=10,
            completed=False,
            status=STATUS_CHOICES[0][0],
            user=self.user,
        )
        task.save()
        task.status = STATUS_CHOICES[1][0]
        task.save()
        history = TaskHistory.objects.filter(task__pk=task.id).first()
        response = self.client.get(f"/api/v1/task/{task.id}/history/{history.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test Filter
        today = date.today()
        response = self.client.get(
            f"/api/v1/task/{task.id}/history/{history.id}/?updated_date={today.year}-{today.month}-{today.day}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class APITestCases(TestCase):
    """Test create, delete and update operations on API"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="bruce_wayne", email="bruce@wayne.org")
        self.user.set_password("i_am_batman")
        self.user.save()

    def test_task_create(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        response = self.client.post(
            "/api/v1/task/",
            {
                "title": "Buy Milk!",
                "description": "From Milk shop",
                "priority": 10,
                "completed": False,
                "status": STATUS_CHOICES[0][0],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_task_delete(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        task = Task.objects.create(
            title="Buy Milk!",
            description="From Milk shop",
            priority=10,
            completed=False,
            status=STATUS_CHOICES[0][0],
            user=self.user,
        )
        task.save()
        response = self.client.delete(f"/api/v1/task/{task.id}/")
        self.assertFalse(Task.objects.filter(user=self.user))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_task_update(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        task = Task.objects.create(
            title="Buy Milk!",
            description="From Milk shop",
            priority=10,
            completed=False,
            status=STATUS_CHOICES[0][0],
            user=self.user,
        )
        task.save()
        response = self.client.patch(
            f"/api/v1/task/{task.id}/",
            {
                "title": "Buy Milk Sweets!",
                "description": "From Milk shop",
                "priority": 10,
                "completed": False,
                "status": STATUS_CHOICES[0][0],
            },
        )
        self.assertEqual(
            Task.objects.filter(id=task.id).first().title, "Buy Milk Sweets!"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

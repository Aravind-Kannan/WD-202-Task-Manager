from datetime import datetime
from multiprocessing.connection import wait
from time import sleep
from django.contrib.auth.models import AnonymousUser
from django.test import LiveServerTestCase, RequestFactory, TestCase
from rest_framework import status
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from tasks.models import STATUS_CHOICES, EmailTaskReport, Task, User
from tasks.tasks import send_email_reminder
from tasks.views import (
    EmailTaskReportForm,
    GenericAllTaskView,
    GenericCompletedTaskView,
    GenericPendingTaskView,
    TaskCreateForm,
)

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class ViewTestCases(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(username="bruce_wayne", email="bruce@wayne.org")
        self.user.set_password("i_am_batman")
        self.user.save()

    def test_view_user_login(self):
        response = self.client.get("/user/login/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_view_user_signup(self):
        response = self.client.get("/user/signup/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_view_pending_tasks_no_access(self):
        request = self.factory.get("/tasks/")
        request.user = AnonymousUser()
        response = GenericPendingTaskView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response.url, "/user/login?next=/tasks/")

    def test_view_pending_tasks(self):
        request = self.factory.get("/tasks/")
        request.user = self.user
        response = GenericPendingTaskView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_view_all_tasks(self):
        request = self.factory.get("/all-tasks/")
        request.user = self.user
        response = GenericAllTaskView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_view_completed_tasks(self):
        request = self.factory.get("/completed-tasks/")
        request.user = self.user
        response = GenericCompletedTaskView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_session_storage(self):
        response = self.client.get("/sessiontest/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_task_create_view(self):
        """Checks priority logic as well"""
        self.client.login(username="bruce_wayne", password="i_am_batman")
        response = self.client.post(
            "/create-task/",
            {
                "title": "Buy Milk!",
                "description": "From Milk shop",
                "priority": 10,
                "completed": False,
                "status": STATUS_CHOICES[0][0],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        response = self.client.post(
            "/create-task/",
            {
                "title": "Buy Veggies!",
                "description": "From Market",
                "priority": 10,
                "completed": False,
                "status": STATUS_CHOICES[0][0],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(Task.objects.get(priority=11).title, "Buy Milk!")
        self.assertEqual(Task.objects.get(priority=10).title, "Buy Veggies!")

    def test_task_update_view(self):
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
        response = self.client.post(
            f"/update-task/{task.id}/",
            {
                "title": "Buy Milk!",
                "description": "From Milk shop",
                "priority": 11,
                "completed": False,
                "status": STATUS_CHOICES[1][0],
            },
        )
        task = Task.objects.get(id=task.id)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(task.status, STATUS_CHOICES[1][0])
        self.assertEqual(task.priority, 11)

    def test_task_detail_view(self):
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
        response = self.client.get(f"/detail-task/{task.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_task_delete_view(self):
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
        response = self.client.delete(f"/delete-task/{task.pk}/")
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_mail_settings(self):
        self.client.login(username="bruce_wayne", password="i_am_batman")
        response = self.client.get(f"/mail-settings/{self.user.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FormTestCases(TestCase):
    def test_user_create_form(self):
        form = TaskCreateForm(
            data={
                "title": "123",
                "description": "From Milk shop",
                "priority": 10,
                "completed": False,
                "status": STATUS_CHOICES[1][0],
            }
        )

        self.assertEqual(form.errors["title"], ["Data too small"])

    def test_email_form(self):
        form = EmailTaskReportForm(
            data={"send_time": "2022-02-14 07:25:00+00:00", "time_zone": "UTC"}
        )

        # self.client.login(username="bruce_wayne", password="i_am_batman")
        # response = self.client.post(
        #     f"/mail-settings/{self.user.id}/",
        #     data={"send_time": "2022-02-14 07:25:00+00:00", "time_zone": "UTC"},
        # )
        # self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertTrue(form.is_valid())


class CeleryTestCases(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(username="bruce_wayne", email="bruce@wayne.org")
        self.user.set_password("i_am_batman")
        self.user.save()

    def test_send_email_reminder(self):
        EmailTaskReport.objects.create(
            user=self.user, send_time=datetime.now(), time_zone="UTC"
        )
        Task.objects.create(
            title="Buy Milk!",
            description="From Milk shop",
            priority=10,
            completed=False,
            status=STATUS_CHOICES[0][0],
            user=self.user,
        ).save()
        send_email_reminder.apply()


# Trying Selenium
# class HostTestCases(LiveServerTestCase):
#     def setUp(self):
#         self.user = User.objects.create(username="bruce_wayne", email="bruce@wayne.org")
#         self.user.set_password("i_am_batman")
#         self.user.save()

#     def test_userlogin_page(self):
#         driver = webdriver.Chrome()

#         driver.get("http://127.0.0.1:8000/user/login/")
#         username = driver.find_element_by_id("id_username")
#         password = driver.find_element_by_id("id_password")
#         submit = driver.find_element_by_xpath("/html/body/div/div/form/button")

#         username.send_keys("bruce_wayne")
#         password.send_keys("i_am_batman")
#         submit.send_keys(Keys.RETURN)

#         self.assertEqual(Task.objects.filter(user=self.user).count(), 0)

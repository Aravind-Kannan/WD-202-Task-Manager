# Celery - Tasks
from datetime import datetime, timedelta

from celery.decorators import periodic_task
from django.core.mail import send_mail
from pytz import timezone
from task_manager.celery import app

from tasks.models import STATUS_CHOICES, EmailTaskReport, Task, User


@periodic_task(run_every=timedelta(seconds=10))
def send_email_reminder():
    print("Starting to process Emails")
    now_utc = datetime.now(timezone("UTC"))

    for email_report in EmailTaskReport.objects.filter(send_time__lt=now_utc):
        user = User.objects.get(id=email_report.user.id)

        # Create content and subject
        subject = user.username + "'s report"

        all_tasks = Task.objects.filter(deleted=False, user=user)
        content = "Task report:\n\n\n"
        for i in range(len(STATUS_CHOICES) - 1):
            tasks = all_tasks.filter(status=STATUS_CHOICES[i][0])
            content += f"{STATUS_CHOICES[i][0].title()} :  {str(tasks.count())}\n"
            for i in range(len(tasks)):
                content += f"{i + 1}. {tasks[i]}\n"
            content += "\n\n"

        # Send mail
        send_mail(
            subject,
            content,
            "tasks@task_manager.org",
            [user.email],
        )
        email_report.send_time = email_report.send_time + timedelta(days=1)
        email_report.save()
        print("Email sent!")
        print(f"Completed Processing User {user.id} to user email: {user.email}")

from django.contrib import admin

# Register your models here.
# * Registering `Task` model to acces from `admin.sites.site`
from task_manager.tasks.models import Task

admin.sites.site.register(Task)

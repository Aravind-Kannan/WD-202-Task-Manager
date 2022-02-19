from datetime import datetime

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.forms import ModelForm, ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from pytz import timezone

from tasks.models import EmailTaskReport, Task, User


class UserForm(UserCreationForm):
    """Provide a view for creating users with only the requisite fields."""

    class Meta:
        model = User
        # Note that password is taken care of for us by auth's UserCreationForm.
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields["email"].required = True


# ! User Views
# * Traditional Signup Page: Form consists of `username`, `password` and `confirm password` to create a new user in the `task_manager`
class UserCreateView(CreateView):
    form_class = UserForm
    template_name = "user/signup.html"
    success_url = "/user/login"


# * Traditional Login Page: Form consists of `username` and `password` to authenticate into the `task_manager`
class UserLoginView(LoginView):
    template_name = "user/login.html"


# ! Additional Views
# * Learning Cookies: Simple view counter tied with each session
def session_storage_view(request):
    total_views = request.session.get("total_views", 0)
    request.session["total_views"] = total_views + 1
    return HttpResponse(f"Total views is {total_views} and user is {request.user}")


# ! Pre-requisite Mixins and functions
# * Authorisation (Combined Mixin): To allow access only to users who are 'logged in' and allow them only to view their respective 'tasks'
class AuthorisedTaskManager(LoginRequiredMixin):
    def get_queryset(self):
        return Task.objects.filter(deleted=False, user=self.request.user)


# * Task Counter (Mixin): Creates context variables and count the completed tasks in `count_completed` and total number of tasks in `count_total`
# ? Refer: https://docs.djangoproject.com/en/4.0/ref/class-based-views/generic-display/
class TaskCounterMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["count_completed"] = Task.objects.filter(
            completed=True, deleted=False, user=self.request.user
        ).count()
        context["count_total"] = Task.objects.filter(
            deleted=False, user=self.request.user
        ).count()
        return context


# * Priority Casacade Logic (Database Transaction Function): Lifted up for model logic in `GenericTaskCreateView` and `GenericTaskUpdateView`
def priority_cascade_logic(form, user):
    conflicting_priority = form.cleaned_data["priority"]
    tasks = list()
    with transaction.atomic():
        while True:
            # ? Refer: https://docs.djangoproject.com/en/4.0/ref/models/querysets/#get
            try:
                task = Task.objects.select_for_update().get(
                    deleted=False,
                    completed=False,
                    user=user,
                    priority=conflicting_priority,
                )
                conflicting_priority += 1
                task.priority += 1
                tasks.append(task)
            except:
                break
        Task.objects.bulk_update(tasks, ["priority"])


# ! Task Views
# * Task Create Form: Customizing contents of `ModelForm`
class TaskCreateForm(ModelForm):

    # ? clean_<attribute>: access to cleaning that <attribute>
    # * Cleaning Title Attribute: Access contents of Form from `cleaned_data` dictionary
    def clean_title(self):
        title = self.cleaned_data["title"]
        if len(title) < 5:
            raise ValidationError("Data too small")
        return title

    # ? Meta data for `TaskCreateForm` provided inside
    class Meta:
        model = Task
        fields = ["title", "description", "completed", "priority", "status"]


# ! CRUD with Task Model
# * Create Task Page: Form consisting of `Task` attributes to create a new record in the database
class GenericTaskCreateView(CreateView):
    form_class = TaskCreateForm
    template_name = "task/create.html"
    success_url = "/tasks"

    # * Priority Casacade Logic: For new `Task` object - run everytime
    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        if form.cleaned_data["completed"] == False:
            priority_cascade_logic(form, self.request.user)

        # * Save newly created object
        self.object = form.save()
        self.object.user = self.request.user
        self.object.save()

        return HttpResponseRedirect(self.get_success_url())


# * Update Task Page: Form consisting of `Task` attributes with their pre-existing data
class GenericTaskUpdateView(AuthorisedTaskManager, UpdateView):
    form_class = TaskCreateForm
    template_name = "task/update.html"
    success_url = "/all-tasks"

    # * Priority Casacade Logic: For `Task` object that changes `priority`, run only once
    # * TO find if it has changed, we use `Form.has_changed()` and `Form.changed_data`
    # ? Refer: https://docs.djangoproject.com/en/4.0/ref/forms/api/#django.forms.Form.has_changed
    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        if form.has_changed() and (
            "priority" in form.changed_data
            or (
                "completed" in form.changed_data
                and form.cleaned_data["completed"] == False
            )
        ):
            priority_cascade_logic(form, self.request.user)

        # * Save updated object
        self.object = form.save()

        return HttpResponseRedirect(self.get_success_url())


# * Delete Task Page: Form consists of `confirm`ation button with POST to be a safe-method as soft-deletion of `Task` causes side-effect
class GenericTaskDeleteView(AuthorisedTaskManager, DeleteView):
    model = Task
    template_name = "task/delete.html"
    success_url = "/all-tasks"


# * Detail Task Page: Details of specific `Task` model with context-variable as `object`
class GenericTaskDetailView(AuthorisedTaskManager, DetailView):
    model = Task
    template_name = "task/detail.html"


# ! Landing
# * List Pending Tasks Page: `ListView` of all pending `Task` records available in the database
class GenericPendingTaskView(TaskCounterMixin, LoginRequiredMixin, ListView):
    queryset = Task.objects.filter(completed=False, deleted=False).order_by("-priority")
    template_name = "task/tasks.html"
    context_object_name = "tasks"
    # * Pagination Feature using `paginator`
    paginate_by = 5

    def get_queryset(self):
        return Task.objects.filter(
            completed=False, deleted=False, user=self.request.user
        ).order_by("priority")


# * List All Tasks Page: `ListView` of all `Task` records available in the database
class GenericAllTaskView(TaskCounterMixin, LoginRequiredMixin, ListView):
    queryset = Task.objects.filter(deleted=False).order_by("-priority")
    template_name = "task/all.html"
    context_object_name = "tasks"
    # * Pagination Feature using `paginator`
    paginate_by = 5

    def get_queryset(self):
        return Task.objects.filter(deleted=False, user=self.request.user).order_by(
            "priority"
        )


# * List Completed Tasks Page: `ListView` of all completed `Task` records available in the database
class GenericCompletedTaskView(TaskCounterMixin, LoginRequiredMixin, ListView):
    queryset = Task.objects.filter(completed=True, deleted=False).order_by("-priority")
    template_name = "task/completed.html"
    context_object_name = "tasks"
    # * Pagination Feature using `paginator`
    paginate_by = 5

    def get_queryset(self):
        return Task.objects.filter(
            completed=True, deleted=False, user=self.request.user
        ).order_by("priority")


class EmailTaskReportForm(ModelForm):
    class Meta:
        model = EmailTaskReport
        fields = ["send_time", "time_zone"]

    def clean(self):
        # * Render Form: Convert UTC to Local
        send_time = self.cleaned_data["send_time"]
        time_zone = self.cleaned_data["time_zone"]
        send_time = send_time.replace(tzinfo=None)
        local_time = timezone(time_zone).localize(send_time)
        print({"send_time": send_time, "time_zone": time_zone})
        send_time = local_time.astimezone(timezone("UTC"))
        print("local_time:", self.cleaned_data["send_time"], "\nsend time:", send_time)
        print("UTC:", datetime.utcnow())
        return {"send_time": send_time, "time_zone": time_zone}

    def __init__(self, *args, **kwargs):
        super(EmailTaskReportForm, self).__init__(*args, **kwargs)

        # * Render Form: Convert UTC to Local
        send_time = str(self.instance.send_time).split("+")[0]
        if str(self.instance.send_time).find(".") != -1:
            time_str = datetime.strptime(send_time, "%Y-%m-%d %H:%M:%S.%f")
        else:
            time_str = datetime.strptime(send_time, "%Y-%m-%d %H:%M:%S")

        local_time = time_str.astimezone(timezone(self.instance.time_zone))
        print(time_str, local_time)
        self.instance.send_time = str(local_time)
        # self.fields["send_time"] = local_time
        # print(utc_time, local_time)
        # self.instance.send_time = local_time.strftime("%H:%M:%S")
        # self.instance.time_zone = "UTC"

        kwargs["instance"] = self.instance
        super(EmailTaskReportForm, self).__init__(*args, **kwargs)


class GenericEmailTaskReportUpdateView(LoginRequiredMixin, UpdateView):
    form_class = EmailTaskReportForm
    template_name = "mail_settings.html"
    success_url = "/all-tasks"

    def get_queryset(self):
        return EmailTaskReport.objects.filter(user=self.request.user)

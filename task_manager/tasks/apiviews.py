from django.contrib.auth.models import User
from django_filters.rest_framework import (
    BooleanFilter,
    CharFilter,
    ChoiceFilter,
    DateFilter,
    DjangoFilterBackend,
    FilterSet,
)
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ModelSerializer
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from task_manager.tasks.models import STATUS_CHOICES, Task, TaskHistory


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "username")


class TaskSerializer(ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Task
        fields = ["title", "description", "completed", "status", "user"]


class TaskFilter(FilterSet):
    title = CharFilter(lookup_expr="icontains")
    status = ChoiceFilter(choices=STATUS_CHOICES)
    # * https://django-filter.readthedocs.io/en/stable/guide/tips.html#solution-1-using-a-booleanfilter-with-isnull
    completed = BooleanFilter()


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer

    permission_classes = (IsAuthenticated,)

    filter_backends = (DjangoFilterBackend,)
    filterset_class = TaskFilter

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user, deleted=False)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TaskHistorySerializer(ModelSerializer):
    task = TaskSerializer(read_only=True)

    class Meta:
        model = TaskHistory
        fields = ["id", "old_status", "new_status", "updated_date", "task"]


class TaskHistoryFilter(FilterSet):
    old_status = ChoiceFilter(choices=STATUS_CHOICES)
    new_status = ChoiceFilter(choices=STATUS_CHOICES)
    # * https://django-filter.readthedocs.io/en/stable/ref/filters.html#method
    updated_date = DateFilter(method="filter_using_date")

    def filter_using_date(self, queryset, name, value):
        return queryset.filter(
            updated_date__year=value.year,
            updated_date__month=value.month,
            updated_date__day=value.day,
        )


class TaskHistoryViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    queryset = TaskHistory.objects.all()
    serializer_class = TaskHistorySerializer

    permission_classes = (IsAuthenticated,)

    filter_backends = (DjangoFilterBackend,)
    filterset_class = TaskHistoryFilter

    def get_queryset(self):
        # append .query to view RAW SQL
        return TaskHistory.objects.filter(
            task__pk=self.kwargs["task_pk"],
            task__user=self.request.user,
        )

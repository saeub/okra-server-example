import random
import string
import uuid
from functools import partial

from django.db import models
from django.utils import timezone

from okra_server.exceptions import NoTasksAvailable


def _random_key(length: int):
    chars = string.ascii_letters + string.digits
    key = "".join(random.choice(chars) for _ in range(length))
    return key


class Participant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    device_key = models.CharField(max_length=24, null=True)
    registration_key = models.CharField(
        max_length=24, null=True, default=partial(_random_key, 24)
    )

    def __str__(self):
        registered = self.device_key is not None
        return (
            f'{"Registered" if registered else "Unregistered"} Participant "{self.id}"'
        )

    @property
    def experiments(self) -> models.QuerySet:
        experiments = Experiment.objects.filter(
            tasks__assignments__participant=self,
        )
        return experiments

    def unregister(self):
        self.device_key = None
        self.registration_key = _random_key(24)

    def register(self):
        self.device_key = _random_key(24)
        self.registration_key = None


class TaskType(models.TextChoices):
    CLOZE = "cloze", "Cloze test"
    LEXICAL_DECISION = "lexical-decision", "Lexical decision"
    PICTURE_NAMING = "picture-naming", "Picture-naming"
    QUESTION_ANSWERING = "question-answering", "Question answering"


class Experiment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    task_type = models.CharField(max_length=50, choices=TaskType.choices)
    title = models.CharField(max_length=100)
    cover_image_url = models.URLField(null=True)
    instructions = models.TextField()

    def __str__(self):
        return f'Experiment "{self.title}" ({self.task_type})'

    def get_n_tasks(self, participant: Participant) -> int:
        return TaskAssignment.objects.filter(
            participant=participant,
            task__in=self.tasks.all(),
        ).count()

    def get_n_tasks_done(self, participant: Participant) -> int:
        return TaskAssignment.objects.filter(
            participant=participant,
            task__in=self.tasks.all(),
            started_time__isnull=False,
        ).count()

    def start_task(self, participant: Participant) -> "Task":
        assignment = TaskAssignment.objects.filter(
            participant=participant,
            started_time__isnull=True,
        ).first()
        if assignment is None:
            raise NoTasksAvailable()
        assignment.start()
        return assignment.task


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    data = models.JSONField()

    def __str__(self):
        return f'Task "{self.id}" of {self.experiment}'

    def finish(self, participant: Participant, results: dict):
        self.assignments.get(
            participant=participant,
            finished_time__isnull=True,
        ).finish(results)


class TaskAssignment(models.Model):
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    results = models.JSONField(null=True)
    started_time = models.DateTimeField(null=True)
    finished_time = models.DateTimeField(null=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "task"],
                name="unique_assignment",
            ),
        ]

    def start(self):
        self.started_time = timezone.now()
        self.save()

    def finish(self, results: dict):
        self.results = results
        self.finished_time = timezone.now()
        self.save()

    def __str__(self):
        return f"Assignment of {self.task} to {self.participant}"


class TaskRatingType(models.TextChoices):
    EMOTICON = "emoticon", "Emoticons"
    RADIO = "radio", "Radio buttons"
    SLIDER = "slider", "Slider"


class TaskRating(models.Model):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    question = models.TextField()
    rating_type = models.CharField(
        max_length=50,
        choices=TaskRatingType.choices,
    )
    low_extreme = models.TextField(null=True)
    high_extreme = models.TextField(null=True)

import pytest
from django.template.defaultfilters import escapejs

from okra_server import models


@pytest.fixture
def experiments(registered_participant):
    pt = models.Task.objects.create(
        data={"practice": "task"},
    )
    e1 = models.Experiment.objects.create(
        task_type=models.TaskType.QUESTION_ANSWERING,
        title="Test experiment",
        instructions="Read the text and answer the questions.",
        practice_task=pt,
    )
    t1 = models.Task.objects.create(
        experiment=e1,
        data={},
    )
    models.TaskAssignment.objects.create(
        participant=registered_participant,
        task=t1,
    )
    e2 = models.Experiment.objects.create(
        task_type=models.TaskType.QUESTION_ANSWERING,
        title="Test experiment",
        instructions="Read the text and answer the questions.",
    )
    t2 = models.Task.objects.create(
        experiment=e2,
        data={},
    )
    models.TaskAssignment.objects.create(
        participant=registered_participant,
        task=t2,
    )
    models.TaskRating.objects.create(
        experiment=e2,
        question="Rating",
        rating_type="slider",
    )
    return [e1, e2]


@pytest.fixture
def public_urls(unregistered_participant):
    return [
        f"/registration/{unregistered_participant.id}",
    ]


@pytest.fixture
def private_urls(experiments):
    return [
        "/experiments",
        "/experiments/new",
        f"/experiments/{experiments[0].id}",
        "/participants",
    ]


def test_get_registration_detail(authenticated_client, unregistered_participant):
    response = authenticated_client.get(f"/registration/{unregistered_participant.id}")
    assert response.status_code == 200, response.content
    assert str(unregistered_participant.id) in response.content.decode()
    assert unregistered_participant.registration_key in response.content.decode()


def test_get_registration_detail_already_registered(
    authenticated_client, registered_participant
):
    response = authenticated_client.get(f"/registration/{registered_participant.id}")
    assert response.status_code == 404, response.content
    assert "already registered" in response.content.decode()


def test_unauthenticated(client, public_urls, private_urls):
    for url in public_urls:
        response = client.get(url)
        assert client.get(url).status_code == 200, response.content
    for url in private_urls:
        response = client.get(url)
        assert response.status_code == 302, response.content
        assert response.url == f"/login?next={url}"


def test_authenticated(authenticated_client, public_urls, private_urls):
    for url in public_urls:
        response = authenticated_client.get(url)
        assert response.status_code == 200, response.content
    for url in private_urls:
        response = authenticated_client.get(url)
        assert response.status_code == 200, response.content


def test_get_experiment_list(authenticated_client, experiments):
    response = authenticated_client.get("/experiments")
    assert response.status_code == 200, response.content
    for experiment in experiments:
        assert str(experiment.id) in response.content.decode()


def test_get_experiment_detail(authenticated_client, experiments):
    for experiment in experiments:
        response = authenticated_client.get(f"/experiments/{experiment.id}")
        assert response.status_code == 200, response.content
        for task in experiment.tasks.all():
            assert escapejs(str(task.id)) in response.content.decode()
        for rating in experiment.ratings.all():
            assert escapejs(str(rating.id)) in response.content.decode()


def test_post_experiment_detail(authenticated_client, experiments):
    for experiment in experiments:
        data = {
            "taskType": "cloze",
            "title": "New title",
            "instructions": "New instructions",
            "practiceTask": {
                "id": str(experiment.practice_task.id),
                "label": "New practice task",
                "data": {"new": "practice data"},
            }
            if experiment.practice_task is not None
            else None,
            "tasks": [
                {
                    "id": str(task.id),
                    "label": "New label",
                    "data": {"new": "data"},
                }
                for task in experiment.tasks.all()
            ],
            "ratings": [
                {
                    "id": str(rating.id),
                    "question": "New rating",
                    "type": "emoticon",
                    "lowExtreme": "New low extreme",
                    "highExtreme": "New high extreme",
                }
                for rating in experiment.ratings.all()
            ],
            "assignments": [
                {
                    "participant": str(participant.id),
                    "tasks": [
                        {"id": str(task.id), "started": False}
                        for task in experiment.tasks.all()
                    ],
                }
                for participant in models.Participant.objects.all()
            ],
        }
        task_count_before = experiment.tasks.count()
        rating_count_before = experiment.ratings.count()
        response = authenticated_client.post(
            f"/experiments/{experiment.id}", data, content_type="application/json"
        )
        assert response.status_code == 200, response.content
        experiment.refresh_from_db()
        assert experiment.task_type == "cloze"
        assert experiment.title == "New title"
        assert experiment.instructions == "New instructions"
        if experiment.practice_task is not None:
            assert experiment.practice_task.label == "New practice task"
            assert experiment.practice_task.data == {"new": "practice data"}
        assert experiment.tasks.count() == task_count_before
        for task in experiment.tasks.all():
            assert task.label == "New label"
            assert task.data == {"new": "data"}
        assert experiment.ratings.count() == rating_count_before
        for rating in experiment.ratings.all():
            assert rating.question == "New rating"
            assert rating.rating_type == "emoticon"
            assert rating.low_extreme == "New low extreme"
            assert rating.high_extreme == "New high extreme"
        for participant in models.Participant.objects.all():
            assert (
                experiment.get_assignments(participant).count()
                == experiment.tasks.count()
            )


def test_post_experiment_detail_delete_tasks_ratings(authenticated_client, experiments):
    for experiment in experiments:
        data = {
            "taskType": "cloze",
            "title": "New title",
            "instructions": "New instructions",
            "practiceTask": None,
            "tasks": [],
            "ratings": [],
            "assignments": [],
        }
        response = authenticated_client.post(
            f"/experiments/{experiment.id}", data, content_type="application/json"
        )
        assert response.status_code == 200, response.content
        experiment.refresh_from_db()
        assert experiment.practice_task is None
        assert experiment.tasks.count() == 0
        assert experiment.ratings.count() == 0
        for participant in models.Participant.objects.all():
            assert experiment.get_assignments(participant).count() == 0


def test_get_participant_list(
    authenticated_client, unregistered_participant, registered_participant
):
    response = authenticated_client.get("/participants")
    assert response.status_code == 200, response.content
    assert str(unregistered_participant.id) in response.content.decode()
    assert str(registered_participant.id) in response.content.decode()

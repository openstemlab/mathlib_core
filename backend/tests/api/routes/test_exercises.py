import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import ExerciseTag
from tests.utils.exercise import create_random_exercise
from tests.utils.tags import create_random_tag


def test_create_exercise(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "source_name": "SourceA",
        "source_id": "001",
        "text": "What is 2 + 2?",
        "solution": "4",
    }
    response = client.post(
        f"{settings.API_V1_STR}/exercises/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["source_name"] == data["source_name"]
    assert content["source_id"] == data["source_id"]
    assert content["text"] == data["text"]
    assert content["solution"] == data["solution"]
    assert "id" in content


def create_exercise_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {
        "source_name": "SourceA",
        "source_id": "001",
        "text": "What is 2 + 2?",
        "solution": "4",
    }
    response = client.post(
        f"{settings.API_V1_STR}/exercises/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_read_exercise(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    exercise = create_random_exercise(db)
    tag = create_random_tag(db)

    exercise_tag = ExerciseTag(exercise_id=exercise.id, tag_id=tag.id)
    db.add(exercise_tag)
    db.commit()
    db.refresh(exercise)

    response = client.get(
        f"{settings.API_V1_STR}/exercises/{exercise.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["source_name"] == exercise.source_name
    assert content["source_id"] == exercise.source_id
    assert content["text"] == exercise.text
    assert content["solution"] == exercise.solution
    assert content["id"] == str(exercise.id)
    assert len(content["tags"]) > 0
    assert content["tags"][0]["id"] == str(tag.id)
    assert content["tags"][0]["name"] == tag.name


def test_read_exercise_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/exercises/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Exercise not found"


def test_read_exercises(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    create_random_exercise(db)
    create_random_exercise(db)
    response = client.get(
        f"{settings.API_V1_STR}/exercises/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


def test_update_exercise(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    exercise = create_random_exercise(db)
    tag1 = create_random_tag(db)
    tag2 = create_random_tag(db)

    tags = [
        {"id": tag1.id, "name": tag1.name, "description": tag1.description},
        {"id": tag2.id, "name": tag2.name, "description": tag2.description},
    ]
    data = {
        "source_name": "UpdatedSource",
        "source_id": "002",
        "text": "What is 3 + 3?",
        "solution": "6",
        "tags": tags,
    }
    response = client.put(
        f"{settings.API_V1_STR}/exercises/{str(exercise.id)}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["source_name"] == data["source_name"]
    assert content["source_id"] == data["source_id"]
    assert content["text"] == data["text"]
    assert content["solution"] == data["solution"]
    assert content["id"] == str(exercise.id)
    assert content["tags"] == data["tags"]
    assert len(content["tags"]) >= 2


def test_update_exercise_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    tag1 = create_random_tag(db)
    tag2 = create_random_tag(db)
    tags = [
        {"id": tag1.id, "name": tag1.name, "description": tag1.description},
        {"id": tag2.id, "name": tag2.name, "description": tag2.description},
    ]
    data = {
        "source_name": "UpdatedSource",
        "source_id": "002",
        "text": "What is 3 + 3?",
        "solution": "6",
        "tags": tags,
    }
    response = client.put(
        f"{settings.API_V1_STR}/exercises/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Exercise not found"


def test_update_exercise_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    exercise = create_random_exercise(db)
    tag1 = create_random_tag(db)

    tag2 = create_random_tag(db)
    tags = [
        {"id": tag1.id, "name": tag1.name, "description": tag1.description},
        {"id": tag2.id, "name": tag2.name, "description": tag2.description},
    ]
    data = {
        "source_name": "UpdatedSource",
        "source_id": "002",
        "text": "What is 3 + 3?",
        "solution": "6",
        "tags": tags,
    }
    response = client.put(
        f"{settings.API_V1_STR}/exercises/{exercise.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_delete_exercise(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    exercise = create_random_exercise(db)
    response = client.delete(
        f"{settings.API_V1_STR}/exercises/{exercise.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Exercise deleted successfully"


def test_delete_exercise_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/exercises/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Exercise not found"


def test_delete_exercise_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    exercise = create_random_exercise(db)
    response = client.delete(
        f"{settings.API_V1_STR}/exercises/{exercise.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"

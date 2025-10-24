import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.tags import create_random_tag
from tests.utils.exercise import create_random_exercise
from tests.utils.utils import random_lower_string
from app.models import TagPublic, ExercisePublic


def test_create_tag(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    data = {
        "id": str(uuid.uuid4()),
        "name": random_lower_string(),
        "description": random_lower_string(),
    }
    response = client.post(
        f"{settings.API_V1_STR}/tags/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content


def test_create_tag_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": "Algebra", "description": "Algebra related exercises"}
    response = client.post(
        f"{settings.API_V1_STR}/tags/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_read_tag(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    tag = create_random_tag(db)
    response = client.get(
        f"{settings.API_V1_STR}/tags/{tag.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == tag.name
    assert content["description"] == tag.description
    assert content["id"] == str(tag.id)


def test_read_tag_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/tags/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Tag not found"


def test_read_tags(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    # Create multiple tags
    num_tags = 5
    for _ in range(num_tags):
        create_random_tag(db)

    response = client.get(
        f"{settings.API_V1_STR}/tags/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert "count" in content
    assert content["count"] >= num_tags
    assert len(content["data"]) >= num_tags


def test_update_tag(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    tag = create_random_tag(db)
    tag_data = TagPublic.model_validate(tag).model_dump()
    exercise = create_random_exercise(db)
    exercise_data = ExercisePublic.model_validate(exercise).model_dump()
    tag_name = random_lower_string()
    update_data = {
        "name": tag_name,
        "description": "Updated description",
        "exercises": [
            exercise_data,
        ],
    }
    response = client.put(
        f"{settings.API_V1_STR}/tags/{tag_data["id"]}",
        headers=superuser_token_headers,
        json=update_data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == update_data["name"]
    assert content["description"] == update_data["description"]
    assert content["id"] == tag.id

    def test_update_tag_not_found(
        client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        update_data = {"name": "UpdatedTagName", "description": "Updated description"}
        response = client.put(
            f"{settings.API_V1_STR}/tags/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json=update_data,
        )
        assert response.status_code == 404
        content = response.json()
        assert content["detail"] == "Tag not found"


def test_update_tag_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    tag = create_random_tag(db)
    update_data = {"name": "UpdatedTagName", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/tags/{tag.id}",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_delete_tag(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    tag = create_random_tag(db)
    response = client.delete(
        f"{settings.API_V1_STR}/tags/{tag.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Tag deleted successfully"


def test_delete_tag_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/tags/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Tag not found"


def test_delete_tag_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    tag = create_random_tag(db)
    response = client.delete(
        f"{settings.API_V1_STR}/tags/{tag.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"

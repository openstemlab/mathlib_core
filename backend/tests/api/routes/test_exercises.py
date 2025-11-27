import pytest
import asyncio
import httpx
from uuid_extensions import uuid7str

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from tests.utils.exercise import create_random_exercise
from tests.utils.utils import random_lower_string


pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_create_exercise(
    client_with_test_db: httpx.AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    """Checks if exercise is created properly."""

    data = {
        "source_name": "SourceA",
        "source_id": "001",
        "text": "What is 2 + 2?",
        "solution": "4",
    }
    response = await client_with_test_db.post(
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


async def test_create_exercise_not_enough_permissions(
    client_with_test_db: httpx.AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Checks that exercise cant be created by normal user."""

    data = {
        "source_name": "SourceA",
        "source_id": "001",
        "text": "What is 2 + 2?",
        "solution": "4",
    }
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/exercises/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


async def test_read_exercise(
    client_with_test_db: httpx.AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    """Checks if exercise is read properly."""

    exercise = await create_random_exercise(db)

    response = await client_with_test_db.get(
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
    assert content["tags"] == exercise.tags


async def test_read_exercise_not_found(
    client_with_test_db: httpx.AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Checks that nonexistant exercise returns 404."""

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/exercises/{uuid7str()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Exercise not found"


async def test_read_exercises(
    client_with_test_db: httpx.AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    """Checks if list of exercises is returned properly."""

    await create_random_exercise(db)
    await create_random_exercise(db)
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/exercises/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


async def test_update_exercise(
    client_with_test_db: httpx.AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    """Checks if exercise is updated properly."""

    exercise = await create_random_exercise(db)

    tags = [
        random_lower_string(),
        random_lower_string(),
    ]
    data = {
        "source_name": "UpdatedSource",
        "source_id": "002",
        "text": "What is 3 + 3?",
        "solution": "6",
        "tags": tags,
    }
    response = await client_with_test_db.put(
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
    assert isinstance(content["tags"], list)
    assert content["tags"] == data["tags"]


async def test_update_exercise_not_found(
    client_with_test_db: httpx.AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Checks that nonexistent exercise cant be updated and returns 404."""

    tags = [
        random_lower_string(),
        random_lower_string(),
    ]
    data = {
        "source_name": "UpdatedSource",
        "source_id": "002",
        "text": "What is 3 + 3?",
        "solution": "6",
        "tags": tags,
    }
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/exercises/{uuid7str()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Exercise not found"


async def test_update_exercise_not_enough_permissions(
    client_with_test_db: httpx.AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    """Checks that normal users cant change exercises."""

    exercise = await create_random_exercise(db)
    tags = [
        random_lower_string(),
        random_lower_string(),
    ]
    data = {
        "source_name": "UpdatedSource",
        "source_id": "002",
        "text": "What is 3 + 3?",
        "solution": "6",
        "tags": tags,
    }
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/exercises/{exercise.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


async def test_delete_exercise(
    client_with_test_db: httpx.AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    """Checks that exercises can be deleted properly."""

    exercise = await create_random_exercise(db)
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/exercises/{exercise.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Exercise deleted successfully"


async def test_delete_exercise_not_found(
    client_with_test_db: httpx.AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    """Checks that nonexistent exercise cant be deleted."""

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/exercises/{uuid7str()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Exercise not found"


async def test_delete_exercise_not_enough_permissions(
    client_with_test_db: httpx.AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    """Checks that normal users cant delete exercises."""

    exercise = await create_random_exercise(db)
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/exercises/{exercise.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"

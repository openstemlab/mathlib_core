import pytest
import asyncio
from httpx import AsyncClient
from uuid_extensions import uuid7str

from sqlmodel import Session

from app.core.config import settings
from tests.utils.item import create_random_item


pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_create_item(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"title": "Foo", "description": "Fighters"}
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert "owner_id" in content


async def test_read_item(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = await create_random_item(db)
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == item.title
    assert content["description"] == item.description
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


async def test_read_item_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/items/{uuid7str()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


async def test_read_item_not_enough_permissions(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = await create_random_item(db)
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"


async def test_read_items(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    await create_random_item(db)
    await create_random_item(db)
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


async def test_update_item(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = await create_random_item(db)
    data = {"title": "Updated title", "description": "Updated description"}
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


async def test_update_item_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"title": "Updated title", "description": "Updated description"}
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/items/{uuid7str()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


async def test_update_item_not_enough_permissions(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = await create_random_item(db)
    data = {"title": "Updated title", "description": "Updated description"}
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"


async def test_delete_item(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = await create_random_item(db)
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Item deleted successfully"


async def test_delete_item_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/items/{uuid7str()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


async def test_delete_item_not_enough_permissions(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = await create_random_item(db)
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"

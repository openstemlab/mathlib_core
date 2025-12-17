# mathlib_core/backend/tests/api/routes/test_attachments.py

from uuid_extensions import uuid7str
import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import Attachment, Module, User, Course
from tests.utils.user import create_random_user, user_authentication_headers


pytestmark = pytest.mark.asyncio()


async def test_create_attachment_standalone(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    """
    Test creating an attachment without module_id.
    """
    data = {
        "title": "Standalone Attachment",
        "file_url": "https://example.com/file.pdf",
        "type": "pdf",
    }

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/attachments/",
        json=data,
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["file_url"] == data["file_url"]
    assert content["type"] == data["type"]
    assert content["order"] == 0  # auto-assigned
    assert content["module_id"] is None


async def test_create_attachment_with_module(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    normal_user_token_headers: dict[str, str],
    create_module: Module,
):
    """
    Test creating attachment with valid module_id → order should be auto-assigned.
    """

    data = {
        "title": "Module Attachment",
        "file_url": "https://example.com/attach.pdf",
        "type": "pdf",
        "module_id": str(create_module.id),
    }

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/attachments/",
        json=data,
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["module_id"] == str(create_module.id)
    assert content["order"] == 1  # first in module → order = 0 + 1


async def test_create_attachment_with_module_multiple(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    normal_user_token_headers: dict[str, str],
    create_module: Module,
):
    """
    Test multiple attachments in same module get incremental order.
    """
    titles = ["First", "Second", "Third"]

    for i, title in enumerate(titles):
        data = {
            "title": title,
            "file_url": f"https://ex.com/{i}.pdf",
            "type": "pdf",
            "module_id": str(create_module.id),
        }
        response = await client_with_test_db.post(
            f"{settings.API_V1_STR}/attachments/",
            json=data,
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200
        content = response.json()
        assert content["order"] == i + 1  # 1, 2, 3...


async def test_create_attachment_module_not_found(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    """
    Test error when module_id is invalid.
    """
    data = {
        "title": "Bogus Module Attach",
        "file_url": "https://ex.com/x.pdf",
        "type": "pdf",
        "module_id": uuid7str(),
    }

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/attachments/",
        json=data,
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Module not found."


async def test_read_attachments_pagination(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
    create_module: Module,
):
    """
    Test listing attachments with pagination.
    """
    module = create_module
    att1 = Attachment(
        title="Attach 1",
        file_url="https://ex.com/1.pdf",
        type="pdf",
        order=1,
        module_id=module.id,
    )
    att2 = Attachment(
        title="Attach 2",
        file_url="https://ex.com/2.pdf",
        type="pdf",
        order=0,
        module_id=module.id,
    )
    db.add_all([att1, att2])
    await db.flush()
    await db.refresh(att1)
    await db.refresh(att2)

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/attachments/",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["count"] >= 2
    assert len(content["data"]) >= 2
    titles = {a["title"] for a in content["data"]}
    assert "Attach 1" in titles
    assert "Attach 2" in titles


async def test_read_attachments_empty_list(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    """
    Test empty attachments list. Assumes no attachments in DB which might not be true.
    """

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/attachments/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 0
    assert content["data"] == []


async def test_read_attachment_by_id(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    """
    Test reading a single attachment.
    """
    attachment = Attachment(
        title="Detail Attach",
        file_url="https://ex.com/d.pdf",
        type="pdf",
        order=0,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/attachments/{attachment.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(attachment.id)
    assert content["title"] == attachment.title
    assert content["file_url"] == attachment.file_url
    assert content["module_id"] is None


async def test_read_attachment_not_found(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    """
    Test 404 when attachment doesn't exist.
    """
    fake_id = uuid7str()
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/attachments/{fake_id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Attachment not found."


async def test_update_attachment_change_title(
    client_with_test_db: AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
):
    """
    Superuser updates attachment title (no module_id change).
    """
    attachment = Attachment(
        title="Old Title",
        file_url="https://old.com",
        type="pdf",
        order=0,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)

    update_data = {"title": "Updated Title"}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/attachments/{attachment.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Updated Title"


async def test_update_attachment_change_module(
    client_with_test_db: AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
    create_module: Module,
):
    """
    Superuser moves attachment to a new module → order auto-assigned.
    """

    attachment = Attachment(
        title="Move Me",
        file_url="https://ex.com/move.pdf",
        type="pdf",
        order=5,
        module_id=create_module.id,
    )
    db.add(attachment)
    await db.flush()
    user = await create_random_user(db)
    course = Course(title="Physics 101", author_id=user.id)
    db.add(course)
    await db.flush()

    module2 = Module(
        title="Mechanics",
        content="Newton's laws",
        course=course,
        order=1,
        author_id=user.id,
    )
    db.add(module2)
    await db.flush()
    await db.refresh(module2)

    # First attachment in module2 → order = 1
    update_data = {"module_id": module2.id}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/attachments/{attachment.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["module_id"] == update_data["module_id"]
    assert content["order"] == 1  # auto-incremented


async def test_update_attachment_module_not_found(
    client_with_test_db: AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
):
    """
    Try to assign to non-existent module.
    """
    attachment = Attachment(
        title="No Module",
        file_url="https://ex.com",
        type="pdf",
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)

    update_data = {"module_id": uuid7str()}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/attachments/{attachment.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Module not found."


async def test_update_attachment_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
):
    """
    Update non-existent attachment.
    """
    fake_id = uuid7str()
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/attachments/{fake_id}",
        json={"title": "Nope"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Attachment not found."


async def test_delete_attachment_as_superuser(
    client_with_test_db: AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
):
    """
    Superuser deletes attachment.
    """
    attachment = Attachment(
        title="ToDelete",
        file_url="https://del.com",
        type="pdf",
    )
    db.add(attachment)
    await db.flush()
    attachment_id = attachment.id

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/attachments/{attachment_id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Attachment deleted successfully."

    # Confirm deletion
    in_db = await db.get(Attachment, attachment_id)
    assert in_db is None


async def test_delete_attachment_forbidden_for_non_superuser(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    """
    Regular user tries to delete attachment → forbidden.
    """
    attachment = Attachment(
        title="Protected",
        file_url="https://ex.com",
        type="pdf",
    )
    db.add(attachment)
    await db.flush()

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/attachments/{attachment.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No permission."


async def test_delete_attachment_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
):
    """
    Delete non-existent attachment.
    """
    fake_id = uuid7str()
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/attachments/{fake_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Attachment not found."


async def test_reorder_attachments_in_module(
    client_with_test_db: AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
    create_module: Module,
):
    """
    Test reordering attachments in a module.
    """

    # Create 3 attachments
    att1 = Attachment(
        title="A1", file_url="1.pdf", type="pdf", module_id=create_module.id, order=1
    )
    att2 = Attachment(
        title="A2", file_url="2.pdf", type="pdf", module_id=create_module.id, order=2
    )
    att3 = Attachment(
        title="A3", file_url="3.pdf", type="pdf", module_id=create_module.id, order=3
    )
    db.add_all([att1, att2, att3])
    await db.flush()
    await db.refresh(att1)
    await db.refresh(att2)
    await db.refresh(att3)

    # New order: att3, att1, att2
    order_list = [att3.id, att1.id, att2.id]

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/attachments/{create_module.id}/reorder",
        json={"order_list": order_list},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Attachments reordered."

    # Verify order in DB
    result = await db.exec(
        select(Attachment)
        .where(Attachment.module_id == create_module.id)
        .order_by(Attachment.order)
    )
    ordered = result.all()
    assert ordered[0].id == att3.id
    assert ordered[1].id == att1.id
    assert ordered[2].id == att2.id
    assert ordered[0].order == 0
    assert ordered[1].order == 1
    assert ordered[2].order == 2


async def test_reorder_attachments_module_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
):
    """
    Reorder with invalid module_id.
    """
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/attachments/{uuid7str()}/reorder",
        json={"order_list": []},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Module not found."


async def test_reorder_attachments_some_not_found(
    client_with_test_db: AsyncClient,
    superuser_token_headers: dict[str, str],
    db: AsyncSession,
    create_module: Module,
):
    """
    Reorder list contains non-existent attachment IDs.
    """

    valid_id = uuid7str()  # doesn't exist
    fake_id = uuid7str()

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/attachments/{create_module.id}/reorder",
        json={"order_list": [valid_id, fake_id]},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Some attachments not found."

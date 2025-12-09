from uuid_extensions import uuid7str
import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import Module, Course, User, Attachment, Quiz
from tests.utils.user import create_random_user, user_authentication_headers


pytestmark = pytest.mark.asyncio()


async def test_create_module_success(
    client_with_test_db: AsyncClient, db: AsyncSession
):
    # Arrange: Create author and course
    author = await create_random_user(db)
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=author.email, password="testpass"
    )

    course = Course(title="Math 101", author_id=author.id)
    db.add(course)
    await db.flush()
    await db.refresh(course)

    # Create attachment and quiz for relationships
    attachment = Attachment(
        title="Attachment title",
        file_url="https://example.com/file.pdf", 
        order=1,
        type="pdf",)
    quiz = Quiz(
        title="Test Quiz",
        owner_id=user.id,
        )

    db.add(attachment)
    db.add(quiz)
    await db.flush()

    data = {
        "title": "Introduction to Algebra",
        "content": "Basic algebraic expressions.",
        "order": 1,
        "is_draft": False,
        "course_id": str(course.id),
        "attachments": [str(attachment.id)],
        "quizzes": [str(quiz.id)],
    }

    # Act
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/modules/",
        json=data,
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["content"] == data["content"]
    assert content["order"] == data["order"]
    assert content["is_draft"] == data["is_draft"]
    assert content["course_id"] == str(course.id)
    assert str(attachment.id) in content["attachments"]
    assert str(quiz.id) in content["quizzes"]


async def test_create_module_course_not_found(
    client_with_test_db: AsyncClient, db: AsyncSession
):
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    fake_course_id = uuid7str()
    data = {
        "title": "No Course Module",
        "content": "This should fail.",
        "order": 1,
        "course_id": fake_course_id,
    }

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/modules/",
        json=data,
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found."


async def test_create_module_unauthenticated(client_with_test_db: AsyncClient):
    data = {
        "title": "Public Module?",
        "content": "Trying without login",
        "course_id": uuid7str(),
    }

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/modules/",
        json=data,
    )
    assert response.status_code == 401


async def test_read_modules_pagination(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str], db: AsyncSession
):
    # Arrange
    user = await create_random_user(db)
    course = Course(title="Physics 101", author_id=user.id)
    db.add(course)
    await db.flush()

    module = Module(
        title="Mechanics", 
        content="Newton's laws", 
        course=course, 
        order=1,
        author_id=user.id,
        )
    db.add(module)
    await db.flush()
    await db.refresh(module)

    # Act
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/modules/", headers=normal_user_token_headers
    )

    # Assert
    assert response.status_code == 200
    content = response.json()
    assert content["count"] >= 1
    assert len(content["data"]) >= 1
    assert any(m["id"] == str(module.id) for m in content["data"])


async def test_read_modules_empty_list(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/modules/", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 0
    assert content["data"] == []


async def test_read_module_by_id(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str], db: AsyncSession
):
    # Arrange
    user = await create_random_user(db)
    course = Course(title="CS 101", author_id=user.id)
    module = Module(
        title="Variables", 
        content="int x = 5;", 
        course=course, 
        order=1,
        author_id=user.id,
        )

    db.add(module)
    await db.flush()
    await db.refresh(module)

    # Act
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/modules/{module.id}",
        headers=normal_user_token_headers,
    )

    # Assert
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(module.id)
    assert content["title"] == module.title
    assert content["content"] == module.content
    assert content["course_id"] == str(course.id)


async def test_read_module_not_found(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    fake_id = uuid7str()
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/modules/{fake_id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Module not found."


async def test_update_module_as_superuser(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str], db: AsyncSession
):
    # Arrange: Superuser can edit any module
    author = await create_random_user(db)
    course = Course(title="Biology", author_id=author.id)
    module = Module(
        title="Old Module", 
        content="Old content", 
        course=course, 
        order=1,
        author_id=author.id,
        )

    db.add(module)
    await db.flush()
    await db.refresh(module)

    update_data = {
        "title": "Updated Module",
        "content": "New content",
        "is_draft": True,
    }

    # Act
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/modules/{module.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    # Assert
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Updated Module"
    assert content["content"] == "New content"
    assert content["is_draft"] is True


async def test_update_module_as_author(
    client_with_test_db: AsyncClient, db: AsyncSession
):
    author = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=author.email, password="testpass"
    )

    course = Course(title="Geography", author_id=author.id)
    module = Module(
        title="Maps", 
        content="Map reading", 
        course=course, 
        order=1,
        author_id=author.id,
        )
    
    db.add(module)
    await db.flush()

    update_data = {
        "title": "Updated Maps",
        "content": "Advanced map reading",
    }

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/modules/{module.id}",
        json=update_data,
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json() 
    assert content["title"] == "Updated Maps"
    assert content["content"] == "Advanced map reading"

async def test_update_module_attachments_and_quizzes(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str], db: AsyncSession
):
    # Arrange
    author = await create_random_user(db)
    course = Course(title="Chemistry", author_id=author.id)
    module = Module(
        title="Reactions", 
        content="...", 
        course=course, 
        order=1,
        author_id=author.id,
        )

    attachment1 = Attachment(file_url="a1.pdf", type="pdf", title="Attachment 1",)
    attachment2 = Attachment(file_url="a2.pdf", type="pdf", title="Attachment 2",)
    quiz1 = Quiz(title="Periodic Table", owner_id=author.id)

    db.add_all([attachment1, attachment2, quiz1])
    db.add(module)
    await db.flush()
    await db.refresh(attachment1)
    await db.refresh(attachment2)
    await db.refresh(quiz1)

    update_data = {
        "title": "Updated with rels",
        "attachments": [str(attachment1.id), str(attachment2.id)],
        "quizzes": [str(quiz1.id)],
    }

    # Act
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/modules/{module.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    # Assert
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Updated with rels"
    assert sorted(content["attachments"]) == sorted([str(attachment1.id), str(attachment2.id)])
    assert content["quizzes"] == [str(quiz1.id)]


async def test_update_module_forbidden_for_non_superuser(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str], db: AsyncSession
):
    # Arrange: Regular user tries to update
    user = await create_random_user(db)
    course = Course(title="History", author_id=user.id)
    module = Module(
        title="Ancient Rome", 
        content="...", 
        course=course, 
        order=1,
        author_id=user.id,
        )

    db.add(module)
    await db.flush()

    update_data = {"title": "Hacked Title"}

    # Act
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/modules/{module.id}",
        json=update_data,
        headers=normal_user_token_headers,
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["detail"] == "No permission."


async def test_update_module_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
):
    fake_id = uuid7str()
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/modules/{fake_id}",
        json={"title": "No module"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Module not found."


async def test_delete_module_as_superuser(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str], db: AsyncSession
):
    # Arrange
    author = await create_random_user(db)
    course = Course(title="Art", author_id=author.id)
    module = Module(
        title="Color Theory", 
        content="", 
        course=course, 
        order=1,
        author_id=author.id,
        )

    db.add(module)
    await db.flush()
    module_id = module.id

    # Act
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/modules/{module_id}",
        headers=superuser_token_headers,
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == "Module deleted successfully."

    # Confirm deletion
    module_in_db = await db.get(Module, module_id)
    assert module_in_db is None


async def test_delete_module_as_author(
    client_with_test_db: AsyncClient, db: AsyncSession
):
    author = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=author.email, password="testpass"
    )
    course = Course(title="Art", author_id=author.id)
    module = Module(
        title="Color Theory", 
        content="", 
        course=course, 
        order=1,
        author_id=author.id,
        )
    db.add(module)
    await db.flush()
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/modules/{module.id}",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Module deleted successfully."


async def test_delete_module_not_found(
    client_with_test_db: AsyncClient, superuser_token_headers: dict[str, str]
):
    fake_id = uuid7str()
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/modules/{fake_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Module not found."


async def test_delete_module_forbidden_for_non_superuser(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str], db: AsyncSession
):
    # Arrange
    user = await create_random_user(db)
    course = Course(title="Music", author_id=user.id)
    module = Module(
        title="Notes", 
        course=course, 
        order=1, 
        content="Do re mi...",
        author_id=user.id,
        )

    db.add(module)
    await db.flush()

    # Act
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/modules/{module.id}",
        headers=normal_user_token_headers,
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["detail"] == "No permission."
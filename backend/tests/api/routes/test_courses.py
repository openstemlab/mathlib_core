from uuid_extensions import uuid7str
import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import Course, User
from tests.utils.user import create_random_user, user_authentication_headers


pytestmark = pytest.mark.asyncio()


async def test_create_course(client_with_test_db: AsyncClient, db: AsyncSession):
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    data = {"title": "Math 101", "description": "Intro to Mathematics"}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/",
        json=data,
        headers=headers,
    )
    assert response.status_code == 201
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert content["author_id"] == str(user.id)


async def test_create_course_missing_fields(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    data = {"description": "No title provided"}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/",
        json=data,
        headers=normal_user_token_headers,
    )
    assert response.status_code == 422  # Unprocessable Entity due to validation error


async def test_create_course_with_modules(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    data = {
        "title": "Physics 101",
        "description": "Intro to Physics",
        "modules": [
            {"title": "Module 1", "content": "Content 1", "order": 1},
            {"title": "Module 2", "content": "Content 2", "order": 2},
        ],
    }
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/",
        json=data,
        headers=normal_user_token_headers,
    )
    assert response.status_code == 201


async def test_create_course_invalid_module_data(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    data = {
        "title": "Biology 101",
        "description": "Intro to Biology",
        "modules": [
            {"title": "", "content": "Content 1", "order": 1},
            {"title": "Module 2", "content": "", "order": 2},
            {
                "title": "Module 3",
                "content": "Content 3",
                "order": 2,
            },  # Invalid: duplicate order
            {
                "title": "Module 4",
                "content": "Content 4",
                "order": 0,
            },  # Invalid: order < 1
        ],
    }

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/",
        json=data,
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    content = response.json()
    assert (
        content["detail"]["message"]
        == "Course creation failed due to invalid module data."
    )
    assert len(content["detail"]["errors"]) == 2


async def test_create_course_unauthenticated(client_with_test_db: AsyncClient):
    data = {"title": "Chemistry 101", "description": "Intro to Chemistry"}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/",
        json=data,
    )
    assert response.status_code == 401


async def test_read_courses_pagination(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    # Create a course first
    user = await create_random_user(db)
    course = Course(title="Test Course", author_id=user.id)
    db.add(course)
    await db.flush()
    await db.refresh(course)

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/courses/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] >= 1
    assert len(content["data"]) >= 1
    assert course.id in [c["id"] for c in content["data"]]


async def test_read_course_by_id(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    user = await create_random_user(db)
    course = Course(title="Advanced Math", author_id=user.id)
    db.add(course)
    await db.flush()
    await db.refresh(course)

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/courses/{course.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(course.id)
    assert content["title"] == "Advanced Math"


async def test_read_course_not_found(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    fake_id = uuid7str()
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/courses/{fake_id}", headers=normal_user_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"


async def test_update_course_as_author(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    course = Course(title="Old Title", description="Old Desc", author_id=user.id)
    db.add(course)
    await db.flush()
    await db.refresh(course)

    update_data = {"title": "Updated Title", "description": "Updated description"}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/courses/{course.id}",
        json=update_data,
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Updated Title"
    assert content["description"] == "Updated description"


async def test_update_course_as_non_author(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    user = await create_random_user(db)
    course = Course(title="My Course", author_id=user.id)
    db.add(course)
    await db.flush()
    await db.refresh(course)

    update_data = {"title": "Hacked Title"}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/courses/{course.id}",
        json=update_data,
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


async def test_delete_course_as_author(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    user_response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers
    )
    user_id = user_response.json()["id"]

    course = Course(title="To Delete", author_id=user_id)
    db.add(course)
    await db.flush()

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/courses/{course.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Course deleted successfully"

    # Confirm deletion
    course_in_db = await db.get(Course, course.id)
    assert course_in_db is None


async def test_delete_course_not_found(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    fake_id = uuid7str()
    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/courses/{fake_id}", headers=normal_user_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"


async def test_delete_course_not_author(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    user = await create_random_user(db)
    course = Course(title="Protected", author_id=user.id)  # Not current user
    db.add(course)
    await db.flush()

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/courses/{course.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


async def test_enroll_in_course(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    # Create course
    author = await create_random_user(db)
    course = Course(title="Enrollable Course", author_id=author.id)
    db.add(course)
    await db.flush()
    await db.refresh(course)

    # Get current user
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    # Enroll
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/{course.id}/enroll",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User enrolled in course successfully"

    # Reload from DB
    await db.refresh(user)
    await db.refresh(course)

    assert str(course.id) in [str(c.id) for c in user.enrolled_courses]
    assert str(user.id) in [str(u.id) for u in course.attendants]


async def test_enroll_already_enrolled(
    client_with_test_db: AsyncClient,
    normal_user_token_headers: dict[str, str],
    db: AsyncSession,
):
    # Create course
    author = await create_random_user(db)
    user = await create_random_user(db)
    db.add(author)
    db.add(user)

    course = Course(title="Repeatable Course", author_id=author.id, attendants=[user])
    db.add(course)
    await db.flush()
    await db.refresh(course)

    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    # Try to re-enroll
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/{course.id}/enroll",
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User already enrolled in this course"


async def test_enroll_course_not_found(
    client_with_test_db: AsyncClient, normal_user_token_headers: dict[str, str]
):
    fake_id = uuid7str()
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/{fake_id}/enroll",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"

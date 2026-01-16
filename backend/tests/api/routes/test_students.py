"""
Tests for the student grades endpoint.
"""

import pytest
from uuid_extensions import uuid7str
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.quiz import create_random_quiz
from app.models import Quiz, QuizStatusChoices, StudentGrades, QuizGrade


pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_get_student_grades_success(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test retrieving grades for a student with submitted quizzes.

    Verifies that:
    - Response status is 200
    - Correct student_id and name are returned
    - Grades list contains expected quiz data
    - Each grade includes quiz_id, title, submitted_at, and score
    """
    # Arrange: Create student and quizzes
    student = await create_random_user(db)

    # Create two quizzes with final scores and submitted_at
    quiz1 = await create_random_quiz(db, owner_id=student.id)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == quiz1.id)
        .values(
            status=QuizStatusChoices.SUBMITTED.value,
            final_score=85.0,
            submitted_at=datetime.now(timezone.utc),
        )
    )

    quiz2 = await create_random_quiz(db, owner_id=student.id)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == quiz2.id)
        .values(
            status=QuizStatusChoices.SUBMITTED.value,
            final_score=92.5,
            submitted_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()
    await db.refresh(student)

    headers = await user_authentication_headers(
        client=client_with_test_db, email=student.email, password="testpass"
    )

    # Act
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/students/{student.id}/grades",
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    content = response.json()
    assert content["user_id"] == str(student.id)
    assert content["user_name"] == student.full_name or "Unknown"

    grades = content["grades"]
    assert len(grades) == 2

    # Check first quiz (most recent)
    assert grades[0]["quiz_id"] == str(quiz2.id)
    assert grades[0]["title"] == quiz2.title
    assert grades[0]["score"] == 92.5

    assert grades[1]["quiz_id"] == str(quiz1.id)
    assert grades[1]["title"] == quiz1.title
    assert grades[1]["score"] == 85.0


async def test_get_student_grades_no_quizzes(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test retrieving grades for a student with no quizzes.

    Expects a 404 error with appropriate detail message.
    """
    student = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=student.email, password="testpass"
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/students/{student.id}/grades",
        headers=headers,
    )

    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "No quizzes found for this student."


async def test_get_student_grades_submitted_only(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test that only quizzes with submitted_at are included (e.g., ignore active/in_progress).
    """
    student = await create_random_user(db)

    # Create a submitted quiz
    submitted_quiz = await create_random_quiz(db, owner_id=student.id)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == submitted_quiz.id)
        .values(
            status=QuizStatusChoices.SUBMITTED.value,
            final_score=75.0,
            submitted_at=datetime.now(timezone.utc),
        )
    )

    # Create an active quiz (should not appear in grades)
    active_quiz = await create_random_quiz(db, owner_id=student.id)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == active_quiz.id)
        .values(
            status=QuizStatusChoices.ACTIVE.value,
            final_score=None,
            submitted_at=None,
        )
    )
    await db.flush()
    await db.refresh(student)

    headers = await user_authentication_headers(
        client=client_with_test_db, email=student.email, password="testpass"
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/students/{student.id}/grades",
        headers=headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert len(content["grades"]) == 1
    assert content["grades"][0]["quiz_id"] == str(submitted_quiz.id)
    assert content["grades"][0]["score"] == 75.0


async def test_get_student_grades_owner_name_fallback(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test that if the owner has no full_name, 'Unknown' is used as fallback.
    """
    student = await create_random_user(db)
    student.full_name = None
    db.add(student)
    await db.flush()
    await db.refresh(student)

    quiz = await create_random_quiz(db, owner_id=student.id)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == quiz.id)
        .values(
            status=QuizStatusChoices.SUBMITTED.value,
            final_score=80.0,
            submitted_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()

    headers = await user_authentication_headers(
        client=client_with_test_db, email=student.email, password="testpass"
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/students/{student.id}/grades",
        headers=headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["user_name"] == "Unknown"


async def test_get_student_grades_quiz_without_title(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test that quizzes without titles are handled gracefully (title can be None).
    """
    student = await create_random_user(db)

    quiz = await create_random_quiz(db, owner_id=student.id)
    quiz.title = None
    await db.exec(
        update(Quiz)
        .where(Quiz.id == quiz.id)
        .values(
            title=None,
            status=QuizStatusChoices.SUBMITTED.value,
            final_score=88.0,
            submitted_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    headers = await user_authentication_headers(
        client=client_with_test_db, email=student.email, password="testpass"
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/students/{student.id}/grades",
        headers=headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["grades"][0]["title"] is None


async def test_get_student_grades_sorting(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test that quizzes are sorted by submitted_at in descending order.
    """
    student = await create_random_user(db)

    now = datetime.now(timezone.utc)

    quiz1 = await create_random_quiz(db, owner_id=student.id)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == quiz1.id)
        .values(
            status=QuizStatusChoices.SUBMITTED.value,
            final_score=70.0,
            submitted_at=now,
        )
    )

    quiz2 = await create_random_quiz(db, owner_id=student.id)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == quiz2.id)
        .values(
            status=QuizStatusChoices.SUBMITTED.value,
            final_score=90.0,
            submitted_at=now.replace(year=now.year - 1),  # older
        )
    )
    await db.flush()
    await db.refresh(student)

    headers = await user_authentication_headers(
        client=client_with_test_db, email=student.email, password="testpass"
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/students/{student.id}/grades",
        headers=headers,
    )

    assert response.status_code == 200
    content = response.json()
    grades = content["grades"]

    # Most recent first
    assert grades[0]["score"] == 70.0  # newer
    assert grades[1]["score"] == 90.0  # older

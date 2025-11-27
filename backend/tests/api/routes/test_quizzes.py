"""
Tests for testing tests.
"""

import pytest
from unittest.mock import ANY, Mock, AsyncMock, patch
from uuid_extensions import uuid7str

from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import update
from sqlalchemy.orm import joinedload

from app.core.config import settings
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.quiz import create_random_quiz
from tests.utils.exercise import create_random_exercise
from app.models import (
    ExercisePublic,
    Quiz,
    QuizCreate,
    QuizPublic,
    QuizStatusChoices,
    QuizExerciseData,
    QuizExerciseDataPublic,
    User,
    StartQuizRequest,
    SubmitAnswer,
)


pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_create_quiz(client_with_test_db: AsyncClient, db: AsyncSession) -> None:
    """
    Test quiz creation for an authenticated user.

    Verifies that a user can create a quiz with specified parameters and that
    the response contains the correct owner ID, quiz status, and empty exercises list.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    exercises = [(await create_random_exercise(db)) for _ in range(3)]
    exercise_positions = [
        QuizExerciseData.model_validate({"exercise": ex, "position": i})
        for i, ex in enumerate(exercises)
    ]
    quiz_in = QuizCreate(
        status="new",
        exercise_positions=exercise_positions,
    )

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/",
        headers=headers,
        json=quiz_in.model_dump(),
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Quiz created successfully"


async def test_create_quiz_for_other_user(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test quiz creation for unauthorized user access.

    Ensures that a user cannot create a quiz for another user and receives
    a 403 Forbidden response with appropriate error message.
    """
    user1 = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user1.email, password="testpass"
    )
    user2 = await create_random_user(db)
    quiz_in = QuizCreate(status="new", exercise_positions=[])
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user2.id}/quizzes/",
        headers=headers,
        json=quiz_in.model_dump(),
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "You cant save a quiz for someone else."


async def test_read_quizzes(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test retrieving a list of quizzes for an authenticated user.

    Validates that the endpoint returns a 200 status code and includes
    both 'data' and 'count' fields in the response.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/",
        headers=headers,
    )

    assert response.status_code == 200
    assert "data" in response.json()
    assert "count" in response.json()


async def test_read_quizzes_no_permission(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test unauthorized access to another user's quizzes.

    Confirms that attempting to read quizzes for another user
    results in a 403 Forbidden error with permission denial message.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    random_user_id = uuid7str()

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{random_user_id}/quizzes/",
        headers=headers,
    )

    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "You do not have permission to access this resource."


async def test_read_quiz(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test retrieving a specific quiz by ID for the owner user.

    Verifies that the quiz data including exercises is correctly returned
    with a 200 status code and matches the stored quiz information.
    """
    quiz = await create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = (await db.exec(statement)).first()
    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=user.email,
        password="testpass",
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}",
        headers=headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert all(key in content for key in ["id", "owner_id", "status", "exercises"])
    assert quiz.id == content["id"]
    assert quiz.owner_id == content["owner_id"]
    assert quiz.status == content["status"]

    assert len(content["exercises"]) == len(quiz.exercises)
    for response_ex, quiz_ex in zip(content["exercises"], quiz.exercises):
        assert response_ex["id"] == quiz_ex.id
        assert response_ex["text"] == quiz_ex.text
        assert response_ex["solution"] == quiz_ex.solution


async def test_read_quiz_not_found(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test accessing a non-existent quiz.

    Ensures that requesting a quiz with an invalid ID returns
    a 404 Not Found error with appropriate message.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=user.email,
        password="testpass",
    )
    fake_id = uuid7str()

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{fake_id}",
        headers=headers,
    )

    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Quiz not found"


async def test_read_quiz_not_enough_permission(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """
    Test unauthorized access to another user's quiz.

    Validates that a normal user cannot access a quiz owned by another user,
    resulting in a 403 Forbidden error.
    """
    quiz = await create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = (await db.exec(statement)).first()

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "You do not have permission to access this resource."


async def test_update_quiz(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test updating a quiz's properties by the owner.

    Verifies that the quiz's active status can be successfully modified
    and the changes are reflected in the response.
    """
    quiz = await create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = (await db.exec(statement)).first()
    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=user.email,
        password="testpass",
    )
    quiz.status = False
    update_data = {"status": "in_progress"}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}",
        headers=headers,
        json=update_data,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["status"] == update_data["status"]


async def test_update_quiz_not_found(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test updating a non-existent quiz.

    Ensures that attempting to modify a quiz with an invalid ID
    returns a 404 Not Found error with appropriate message.
    """
    quiz = await create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = (await db.exec(statement)).first()
    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=user.email,
        password="testpass",
    )
    quiz.status = False

    update_data = {"status": "in_progress"}
    fake_id = str(uuid7str())
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{fake_id}",
        headers=headers,
        json=update_data,
    )

    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Quiz not found"


async def test_update_quiz_not_enough_permission(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """
    Test unauthorized quiz update attempt.

    Confirms that a user without ownership cannot modify another user's quiz,
    resulting in a 403 Forbidden error with appropriate message.
    """
    quiz = await create_random_quiz(db)

    update_data = {"status": "in_progress"}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}",
        headers=normal_user_token_headers,
        json=update_data,
    )

    assert response.status_code == 403
    content = response.json()

    assert content["detail"] == "You cant save a quiz for someone else."


async def test_delete_quiz(client_with_test_db: AsyncClient, db: AsyncSession) -> None:
    """
    Test deleting a quiz by its owner.

    Validates that the quiz deletion is successful and the response
    contains the confirmation message.
    """
    quiz = await create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = (await db.exec(statement)).first()
    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=user.email,
        password="testpass",
    )

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Quiz deleted successfully"


async def test_delete_not_found(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test deleting a non-existent quiz.

    Ensures that attempting to delete a quiz with an invalid ID
    returns a 404 Not Found error with appropriate message.
    """
    quiz = await create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = (await db.exec(statement)).first()
    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=user.email,
        password="testpass",
    )

    fake_id = str(uuid7str())

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{fake_id}",
        headers=headers,
    )

    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Quiz not found"


async def test_delete_not_enough_permission(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """
    Test unauthorized quiz deletion attempt.

    Confirms that a user without ownership cannot delete another user's quiz,
    resulting in a 403 Forbidden error with appropriate message.
    """
    quiz = await create_random_quiz(db)

    response = await client_with_test_db.delete(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "You cant delete a quiz for someone else."


@patch("app.api.routes.quizzes.start_new_quiz", new_callable=AsyncMock)
async def test_start_quiz(
    mock_start_new_quiz: AsyncMock,
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test starting a new quiz with full mocking to avoid any DB access.
    """

    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    quiz_id = uuid7str()
    quiz_title = "My Quiz"
    quiz_length = 5
    quiz_tags = ["algebra"]

    quiz_data = StartQuizRequest(length=5, tags=["algebra"], title="My Quiz")

    exercise_public_1 = ExercisePublic(
        id=uuid7str(),
        text="What is 2+2?",
        solution="4",
        source_id="Texbook",
        source_name="Algebra 101",
        tags=["algebra"],
    )
    exercise_public_2 = ExercisePublic(
        id=uuid7str(),
        text="Solve x^2 = 4",
        solution="2 or -2",
        tags=["algebra"],
        source_id="Texbook",
        source_name="Algebra 101",
    )

    quiz_public = QuizPublic(
        id=quiz_id,
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
        title=quiz_title,
        exercises=[
            QuizExerciseDataPublic(exercise=exercise_public_1, position=0),
            QuizExerciseDataPublic(exercise=exercise_public_2, position=1),
        ],
    )
    mock_start_new_quiz.return_value = quiz_public

    # Act
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/start",
        headers=headers,
        json={
            "length": quiz_length,
            "tags": quiz_tags,
            "title": quiz_title,
        },
    )

    # Assert
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    content = response.json()
    assert content["id"] == quiz_id
    assert content["owner_id"] == str(user.id)
    assert content["status"] == "active"
    assert content["title"] == quiz_title
    assert isinstance(content["exercises"], list)

    # Verify mocks
    mock_start_new_quiz.assert_awaited_once_with(
        quiz_data=quiz_data,
        owner_id=user.id,
        session=ANY,
    )


async def test_start_quiz_wrong_user_id(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test that a user cannot start a quiz with a different user_id in URL.
    """
    user1 = await create_random_user(db)
    user2 = await create_random_user(db)  # different user

    headers = await user_authentication_headers(
        client=client_with_test_db, email=user1.email, password="testpass"
    )

    quiz_data = {"length": 5, "tags": ["algebra"], "title": "My Quiz"}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user2.id}/quizzes/start",
        headers=headers,
        json=quiz_data,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You can only start quizzes for yourself."


async def test_start_quiz_unauthorized(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test that an unauthenticated user cannot start a quiz.
    """
    quiz_data = {"length": 5, "tags": ["algebra"], "title": "My Quiz"}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{uuid7str()}/quizzes/start",
        json=quiz_data,
    )

    assert response.status_code == 401


async def test_start_quiz_invalid_data_sent(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test starting quiz with invalid data.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    invalid_data = {"tags": 1}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/start",
        headers=headers,
        json=invalid_data,
    )

    assert response.status_code == 422


async def test_start_quiz_invalid_length(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test for a quiz waaaaaay tooooooo looooooong.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/start",
        headers=headers,
        json={"length": 1000, "tags": ["algebra"]},
    )

    content = response.json()
    assert response.status_code == 422



async def test_save_quiz_route(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test saving a quiz.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    exercise = await create_random_exercise(db)

    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
        exercises=[exercise],
    )
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    answers = SubmitAnswer(
        response=[{"exercise_id": exercise.id, "answer": exercise.solution}]
    ).model_dump()

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/save",
        headers=headers,
        json=answers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Quiz progress saved successfully"


async def test_save_quiz_no_quiz(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    fake_id = uuid7str()
    answers = SubmitAnswer(
        response=[{"exercise_id": uuid7str(), "answer": "4"}]
    ).model_dump()
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{fake_id}/save",
        headers=headers,
        json=answers,
    )

    assert response.status_code == 404


async def test_save_quiz_submitted_quiz(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    exercise = await create_random_exercise(db)
    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.SUBMITTED.value,
        exercises=[exercise],
    )
    answers = SubmitAnswer(
        response=[{"exercise_id": exercise.id, "answer": exercise.solution}]
    ).model_dump()
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/save",
        headers=headers,
        json=answers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot save inactive quiz."


async def test_save_quiz_wrong_user(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    user = await create_random_user(db)
    answers = {"response": []}

    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
    )
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/save",
        headers=normal_user_token_headers,
        json=answers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to save this quiz."


async def test_save_quiz_empty_answers(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test saving a quiz with no answers (valid use case).
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    exercise = await create_random_exercise(db)
    quiz = Quiz(
        owner_id=user.id, status=QuizStatusChoices.ACTIVE.value, exercises=[exercise]
    )
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/save",
        headers=headers,
        json={"response": []},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Quiz progress saved successfully"


async def test_save_quiz_invalid_answer_format(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test sending malformed answers (e.g. wrong types).
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    quiz = Quiz(owner_id=user.id, status=QuizStatusChoices.ACTIVE.value)
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    # Invalid: exercise_id not a string, answer not a string
    invalid_payload = {"response": [{"exercise_id": 123, "answer": 456}]}

    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/save",
        headers=headers,
        json=invalid_payload,
    )

    assert response.status_code == 422


async def test_load_quiz_route(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test loading a quiz.
    """
    quiz = await create_random_quiz(db)
    await db.exec(
        update(Quiz)
        .where(Quiz.id == quiz.id)
        .values(status=QuizStatusChoices.ACTIVE.value)
    )
    await db.flush()
    await db.refresh(quiz)

    query = select(Quiz).where(Quiz.id == quiz.id).options(joinedload(Quiz.owner))
    result = await db.exec(query)
    quiz_with_owner = result.one()

    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=quiz_with_owner.owner.email,
        password="testpass",
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{quiz_with_owner.owner_id}/quizzes/load",
        headers=headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(quiz.id)
    assert content["status"] == QuizStatusChoices.ACTIVE.value


async def test_load_quiz_no_quiz(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/load",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Quiz not found."


async def test_load_quiz_wrong_user_id(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test that a user cannot load a quiz by forging user_id in URL.
    Should return 403 even if active quiz exists.
    """

    user = await create_random_user(db)
    # Auth as user
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    # Try to access /users/{fake_user}/quizzes/load
    fake_user_id = uuid7str()
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{fake_user_id}/quizzes/load",
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You can only load quizzes for yourself."


@pytest.mark.parametrize(
    "status",
    [
        QuizStatusChoices.NEW.value,
        QuizStatusChoices.IN_PROGRESS.value,
        QuizStatusChoices.SUBMITTED.value,
    ],
)
async def test_load_quiz_inactive_status(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    status: str,
) -> None:
    """
    Test that only 'active' quizzes are returned. Others are ignored.
    """

    quiz = await create_random_quiz(db)
    await db.exec(update(Quiz).where(Quiz.id == quiz.id).values(status=status))
    statement = select(Quiz).where(Quiz.id == quiz.id).options(joinedload(Quiz.owner))
    user = (await db.exec(statement)).one().owner
    await db.flush()

    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/load",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Quiz not found."


async def test_submit_quiz(client_with_test_db: AsyncClient, db: AsyncSession) -> None:
    """
    Test submitting a quiz.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    exercise1 = await create_random_exercise(db)
    exercise2 = await create_random_exercise(db)

    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
        exercises=[exercise1, exercise2],
    )

    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    answers = SubmitAnswer(
        response=[
            {"exercise_id": exercise1.id, "answer": exercise1.solution},
            {"exercise_id": exercise2.id, "answer": exercise2.solution},
        ]
    ).model_dump()

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/submit",
        headers=headers,
        json=answers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Quiz submitted successfully"


async def test_submit_quiz_no_quiz(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )
    fake_quiz_id = uuid7str()
    answers = {"response": [{"exercise_id": "1", "answer": "2"}]}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{fake_quiz_id}/submit",
        headers=headers,
        json=answers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Quiz not found"


async def test_submit_quiz_wrong_user_id(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """
    Test that a user cannot submit a quiz by forging user_id in URL.
    Should return 403 even if active quiz exists.
    """
    user = await create_random_user(db)

    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
    )
    db.add(quiz)
    await db.flush()
    answers = {"response": [{"exercise_id": "1", "answer": "2"}]}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}/submit",
        headers=normal_user_token_headers,
        json=answers,
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"] == "You do not have permission to submit this quiz."
    )


@pytest.mark.parametrize(
    "status",
    [
        QuizStatusChoices.NEW.value,
        QuizStatusChoices.IN_PROGRESS.value,
        QuizStatusChoices.SUBMITTED.value,
    ],
)
async def test_submit_quiz_non_active_status(
    client_with_test_db: AsyncClient,
    db: AsyncSession,
    status: str,
) -> None:
    quiz = await create_random_quiz(db)
    await db.exec(update(Quiz).where(Quiz.id == quiz.id).values(status=status))
    await db.flush()
    await db.refresh(quiz)

    user = (await db.exec(select(User).where(User.id == quiz.owner_id))).one()
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    answers = SubmitAnswer(response=[]).model_dump()

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/submit",
        headers=headers,
        json=answers,
    )

    assert response.status_code == 400
    assert "active" in response.json()["detail"].lower()


async def test_submit_quiz_invalid_answer_format(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test submitting answers with invalid types (e.g. exercise_id as int).
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    quiz = Quiz(owner_id=user.id, status=QuizStatusChoices.ACTIVE.value)
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    invalid_payload = {
        "response": [
            {"exercise_id": 123, "answer": 456}  # should be strings
        ]
    }

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/submit",
        headers=headers,
        json=invalid_payload,
    )

    assert response.status_code == 422


async def test_submit_quiz_missing_answers(
    client_with_test_db: AsyncClient, db: AsyncSession
) -> None:
    """
    Test submitting answers for only some of the quiz exercises.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db, email=user.email, password="testpass"
    )

    exercise1 = await create_random_exercise(db)
    exercise2 = await create_random_exercise(db)
    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
        exercises=[exercise1, exercise2],
    )
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)

    # Only answer one exercise
    answers = SubmitAnswer(
        response=[{"exercise_id": exercise1.id, "answer": exercise1.solution}]
    ).model_dump()

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/submit",
        headers=headers,
        json=answers,
    )

    assert response.status_code == 200


@patch("app.api.routes.quizzes.submit_quiz", new_callable=AsyncMock)
async def test_submit_quiz_internal_error(
    mock_submit_quiz: AsyncMock,
    client_with_test_db: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Test that internal errors during submission return 400.
    """
    user = await create_random_user(db)
    headers = await user_authentication_headers(
        client=client_with_test_db,
        email=user.email,
        password="testpass",
    )

    quiz = Quiz(owner_id=user.id, status=QuizStatusChoices.ACTIVE.value)
    db.add(quiz)
    await db.flush()

    mock_submit_quiz.side_effect = Exception("Database connection failed")

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}/submit",
        headers=headers,
        json={"response": []},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Database connection failed"

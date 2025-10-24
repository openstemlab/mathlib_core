import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from tests.utils.exercise import create_random_exercise
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.quiz import create_random_quiz
from app.models import QuizCreate, User


def test_create_quiz(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    headers = user_authentication_headers(
        client=client, email=user.email, password="testpass"
    )

    quiz_in = QuizCreate(is_active=False)

    response = client.post(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/",
        headers=headers,
        json=quiz_in.model_dump(),
    )
    assert response.status_code == 200
    content = response.json()
    assert content["owner_id"] == str(user.id)
    assert content["is_active"] == False
    assert "exercises" in content
    assert len(content["exercises"]) == 0


def test_create_quiz_for_other_user(
    client: TestClient,
    db: Session,
) -> None:
    user1 = create_random_user(db)
    headers = user_authentication_headers(
        client=client, email=user1.email, password="testpass"
    )
    user2 = create_random_user(db)
    quiz_in = QuizCreate(is_active=False)
    response = client.post(
        f"{settings.API_V1_STR}/users/{user2.id}/quizzes/",
        headers=headers,
        json=quiz_in.model_dump(),
    )
    assert response.status_code == 403


def test_read_quizzes(
    client: TestClient,
    db: Session,
):
    user = create_random_user(db)
    headers = user_authentication_headers(
        client=client, email=user.email, password="testpass"
    )

    response = client.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/",
        headers=headers,
    )

    assert response.status_code == 200
    assert "data" in response.json()
    assert "count" in response.json()


def test_read_quizzes_no_permission(
    client: TestClient,
    db: Session,
) -> None:
    user = create_random_user(db)
    headers = user_authentication_headers(
        client=client, email=user.email, password="testpass"
    )
    random_user_id = str(uuid.uuid4())

    response = client.get(
        f"{settings.API_V1_STR}/users/{random_user_id}/quizzes/",
        headers=headers,
    )

    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "You do not have permission to access this resource."


def test_read_quiz(
    client: TestClient,
    db: Session,
) -> None:
    quiz = create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = db.exec(statement).first()
    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password="testpass",
    )

    response = client.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/",
        headers=headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert all(key in content for key in ["id", "owner_id", "is_active", "exercises"])
    assert quiz.id == content["id"]
    assert quiz.owner_id == content["owner_id"]
    assert quiz.is_active == content["is_active"]

    assert len(content["exercises"]) == len(quiz.exercises)
    for response_ex, quiz_ex in zip(content["exercises"], quiz.exercises):
        assert response_ex["id"] == quiz_ex.id
        assert response_ex["text"] == quiz_ex.text
        assert response_ex["solution"] == quiz_ex.solution


def test_read_quiz_not_found(
    client: TestClient,
    db: Session,
) -> None:
    user = create_random_user(db)
    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password="testpass",
    )
    fake_id = str(uuid.uuid4)

    response = client.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{fake_id}/",
        headers=headers,
    )

    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Quiz not found"


def test_read_quiz_not_enough_permission(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    quiz = create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = db.exec(statement).first()

    response = client.get(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "You do not have permission to access this resource."


def test_update_quiz(
    client: TestClient,
    db: Session,
) -> None:
    quiz = create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = db.exec(statement).first()
    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password="testpass",
    )
    quiz.is_active = False
    update_data = {"is_active": True}

    response = client.put(
        f"{settings.API_V1_STR}/users/{user.id}/quizzes/{quiz.id}/",
        headers=headers,
        json=update_data,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["is_active"] == update_data["is_active"]


def test_update_quiz_not_found(client: TestClient, db: Session) -> None:
    quiz = create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = db.exec(statement).first()
    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password="testpass",
    )
    quiz.is_active = False

    update_data = {"is_active": True}
    fake_id = str(uuid.uuid4())
    response = client.put(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{fake_id}/",
        headers=headers,
        json=update_data,
    )

    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Quiz not found"


def test_update_quiz_not_enough_permission(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    quiz = create_random_quiz(db)

    update_data = {"is_active": True}

    response = client.put(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}/",
        headers=normal_user_token_headers,
        json=update_data,
    )

    assert response.status_code == 403
    content = response.json()

    assert content["detail"] == "You cant save a quiz for someone else."


def test_delete_quiz(client: TestClient, db: Session) -> None:
    quiz = create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = db.exec(statement).first()
    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password="testpass",
    )

    response = client.delete(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}/",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Quiz deleted successfully"


def test_delete_not_found(client: TestClient, db: Session) -> None:
    quiz = create_random_quiz(db)
    statement = select(User).where(User.id == quiz.owner_id)
    user = db.exec(statement).first()
    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password="testpass",
    )

    fake_id = str(uuid.uuid4())

    response = client.delete(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{fake_id}/",
        headers=headers,
    )

    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Quiz not found"


def test_delete_not_enough_permission(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    quiz = create_random_quiz(db)

    response = client.delete(
        f"{settings.API_V1_STR}/users/{quiz.owner_id}/quizzes/{quiz.id}/",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "You cant delete a quiz for someone else."

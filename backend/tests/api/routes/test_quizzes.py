import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from tests.utils.exercise import create_random_exercise
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.quiz import create_random_quiz
from app.models import QuizCreate, User

def test_create_quiz(
        client: TestClient,
        db: Session
    )-> None:
    user = create_random_user(db)
    headers = user_authentication_headers(
    client=client, 
    email=user.email, 
    password="testpass"
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


def test_create_quiz_not_authentificated(
        client: TestClient,
        db: Session,
)-> None:
    quiz_in = QuizCreate(is_active=False)
    response = client.post(
        f"{settings.API_V1_STR}/users/1/quizzes/",
        json=quiz_in.model_dump(),
    )
    assert response.status_code == 401


def test_create_quiz_for_other_user(
        client: TestClient,
        db: Session,
)-> None:

    user1 = create_random_user(db)
    headers = user_authentication_headers(
        client=client, 
        email=user1.email, 
        password="testpass"
    )
    user2 = create_random_user(db)
    quiz_in= QuizCreate(is_active=False)
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
    user= create_random_user(db)
    headers = user_authentication_headers(
        client=client, 
        email=user.email, 
        password="testpass"
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
)-> None:
    
    user = create_random_user(db)
    headers = user_authentication_headers(
        client=client, 
        email=user.email, 
        password="testpass"
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
        db:Session,
)-> None:
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
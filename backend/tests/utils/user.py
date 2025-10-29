"""
Utility functions for tests related to User models.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_email, random_lower_string


def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    """
    Generate authentication headers for API requests.
    Sends credentials to the login endpoint and returns headers
    containing the Bearer token for authorized requests.
    Args:
        client: TestClient instance for making HTTP requests
        email: User's email address
        password: User's password
    Returns:
        dict: Authorization headers with Bearer token
    """
    data = {"username": email, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_user(db: Session) -> User:
    """
    Create and return a test user with random email and fixed password.
    Generates a random email address, creates a UserCreate model with
    default password 'testpass', and persists the user to the database.
    Args:
        db: Database session for CRUD operations
    Returns:
        User: Created user object with database-generated fields
    """
    email = random_email()
    password = "testpass"
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    db.refresh(user)
    return user


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session
) -> dict[str, str]:
    """
    Retrieve or create a user and return valid authentication headers.
    If user with specified email exists, updates their password with
    a new random value. If not, creates a new user with the provided email
    and generated password. Returns authentication headers for the user.
    Args:
        client: TestClient instance for making HTTP requests
        email: Target user's email address
        db: Database session for CRUD operations
    Returns:
        dict: Authentication headers with Bearer token for the user
    """
    password = random_lower_string()
    user = crud.get_user_by_email(session=db, email=email)
    if not user:
        user_in_create = UserCreate(email=email, password=password)
        user = crud.create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        if not user.id:
            raise Exception("User id not set")
        user = crud.update_user(session=db, db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, email=email, password=password)

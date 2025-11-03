from uuid_extensions import uuid7str
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    ItemCreate,
    User,
    UserCreate,
    UserUpdate,
    Exercise,
    ExerciseCreate,
)


async def create_user(*, session: AsyncSession, user_create: UserCreate) -> User:
    """Function to create a user.
    
    :param session: The SQLAlchemy session object.
    :param user_create: The user data to create a User.
    :returns: User object.
    """

    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def update_user(*, session: AsyncSession, db_user: User, user_in: UserUpdate) -> Any:
    """Function to update a user.

    :param session: The SQLAlchemy session object.
    :param db_user: User object from database.
    :param user_in: UserUpdate object with data to change.
    :returns: updated User object.
    """

    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def get_user_by_email(*, session: AsyncSession, email: str) -> User | None:
    """Function to get a User object from database by email.
    
    :param session: The SQLAlchemy session object
    :param email: email string.
    :returns: User object
    """

    statement = select(User).where(User.email == email)
    session_user = await session.exec(statement)
    return session_user.first()


async def authenticate(*, session: AsyncSession, email: str, password: str) -> User | None:
    """Function to get a user authentificated.
    
    :param session: The SQLAlchemy session object.
    :param email: email string to find a user.
    :param password: password for a user.
    :returns: User object
    """

    db_user = await get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


async def create_item(*, session: AsyncSession, item_in: ItemCreate, owner_id: str) -> Item:
    """Function to create an item.
    
    :param session: The SQLAlchemy session object.
    :param item_in: Item data to create an item.
    :param owner_id: User id to assign item.
    :returns: Item object.
    """

    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    await session.commit()
    await session.refresh(db_item)
    return db_item


async def create_exercise(*, session: AsyncSession, exercise_in: ExerciseCreate) -> Exercise:
    """Function to create an exercise.

    :param session: The SQLAlchemy session object.
    :param exercise_in: exercise data to create an Exercise from.
    :returns: Exercise object.
    """
    
    db_exercise = Exercise.model_validate(exercise_in)
    session.add(db_exercise)
    await session.commit()
    await session.refresh(db_exercise)
    return db_exercise



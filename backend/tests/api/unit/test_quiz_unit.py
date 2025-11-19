from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from uuid_extensions import uuid7str
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError


from app.core.quiz import *
from app.models import Exercise, ExercisePublic
from tests.utils.exercise import create_random_exercise
from tests.utils.user import create_random_user

pytestmark = pytest.mark.asyncio(loop_scope="module")

async def test_form_quiz(db: AsyncSession,)-> None:
    """Tests the form_quiz function."""

    user = await create_random_user(db)
    tags = ["algebra", "geometry"]
    owner_id = user.id
    title = "Sample Quiz"

    # Create sample exercises
    for _ in range(10):
        exercise = await create_random_exercise(db, tags=tags)


    quiz = await form_quiz(length=5, tags=tags, owner_id=owner_id, title=title, session=db)

    assert quiz.title == title
    assert quiz.owner_id == owner_id
    assert len(quiz.exercises) == 5
    for exercise in quiz.exercises:
        assert "algebra" in exercise.tags


async def test_form_quiz_not_enough_exercises(db: AsyncSession):
    user = await create_random_user(db)
    tags = ["algebra"]
    
    # create only 2 exercises with the given tag
    for _ in range(2):
        await create_random_exercise(db, tags=tags)

    quiz = await form_quiz(length=5, tags=tags, owner_id=user.id, session=db)

    assert len(quiz.exercises) == 2  # Must be 2 since only 2 exercises are available
    assert quiz.title is None


async def test_form_quiz_no_tags_returns_random_exercises(db: AsyncSession):
    user = await create_random_user(db)

    for _ in range(5):
        await create_random_exercise(db, tags=["math"])

    quiz = await form_quiz(length=3, tags=None, owner_id=user.id, session=db)

    assert len(quiz.exercises) == 3
    assert quiz.owner_id == user.id
    assert quiz.title is None


async def test_form_quiz_empty_tags_returns_random_exercises(db: AsyncSession):
    user = await create_random_user(db)

    for _ in range(4):
        await create_random_exercise(db, tags=["physics"])

    quiz = await form_quiz(length=2, tags=[], owner_id=user.id, session=db)

    assert len(quiz.exercises) == 2

async def test_form_quiz_length_zero_returns_empty_quiz(db: AsyncSession):
    user = await create_random_user(db)
    quiz = await form_quiz(length=0, tags=["math"], owner_id=user.id, session=db)

    assert len(quiz.exercises) == 0
    assert quiz.owner_id == user.id


async def test_form_quiz_no_exercises_in_db(db: AsyncSession):
    user = await create_random_user(db)

    quiz = await form_quiz(length=3, tags=["math"], owner_id=user.id, session=db)

    assert len(quiz.exercises) == 0
    assert quiz.owner_id == user.id


@pytest.mark.xfail(raises=HTTPException, reason="HTTPException expected when owner does not exist.")
async def test_form_quiz_owner_not_exists_still_works(db: AsyncSession):
    fake_owner_id = uuid7str()
    tags = ["algebra"]

    for _ in range(3):
        await create_random_exercise(db, tags=tags)

    quiz = await form_quiz(length=2, tags=tags, owner_id=fake_owner_id, session=db)

    assert quiz.owner_id == fake_owner_id
    assert len(quiz.exercises) == 2
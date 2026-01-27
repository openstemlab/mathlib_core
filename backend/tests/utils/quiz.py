from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.quiz import form_quiz
from app.models import QuizPublic
from tests.utils.user import create_random_user

from tests.utils.exercise import create_random_exercise
from tests.utils.utils import random_lower_string


async def create_random_quiz(db: AsyncSession, owner_id: str = None) -> QuizPublic:
    """
    Utitility function that creates a random quiz.
    :param: db - the database session.
    :returns: QuizPublic - public representation of the quiz.
    """
    if owner_id is None:
        user = await create_random_user(db)
        owner_id = user.id
    tag = random_lower_string()
    title = random_lower_string()

    for _ in range(5):
        exercise = await create_random_exercise(db)
        exercise.tags.append(tag)
        db.add(exercise)

    await db.flush()

    quiz = await form_quiz(
        length=5, tags=[tag], owner_id=owner_id, title=title, session=db
    )

    await db.refresh(quiz)
    return quiz

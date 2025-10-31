
import random
from uuid_extensions import uuid7str
from sqlmodel import Session, select
from sqlalchemy import cast, String, or_
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.models import Exercise, ExercisePublic, Quiz, QuizPublic


def form_quiz(
    length: int,
    tags: list[str], 
    owner_id: str,
    title: str|None, 
    session: Session
) -> QuizPublic:
    """
    Form a quiz by selecting exercises based on the provided tags and populate a Quiz model.

    :param length: The number of exercises to include in the quiz.
    :param tags: A list of TagPublic objects to filter exercises.
    :param owner_id: The ID of the user owning the quiz.
    :param session: The database session.
    :return: A QuizPublic object representing the created quiz.
    """

    statement = select(Exercise).where(
    or_(*[Exercise.tags.op('?')(tag) for tag in tags])).limit(length)
    exercises = session.exec(statement).all()

    if len(exercises) < length:
        length = len(exercises)

    positions = list(range(length))
    random.shuffle(positions)

    quiz = Quiz(
        owner_id=owner_id,
        title=title,
        is_active=False
    )

    # adding exercises and positions to the quiz using link model
    for exercise, position in zip(exercises, positions):
        quiz.exercises.append(exercise)
        # refreshing position for each exercise
        quiz_exercise = quiz.exercises[-1].link
        quiz_exercise.position = position

    session.add(quiz)
    session.commit()
    session.refresh(quiz)

    quiz_public = QuizPublic(
        id=quiz.id,
        owner_id=quiz.owner_id,
        is_active=quiz.is_active,
        title=quiz.title,
        exercises=[(ExercisePublic.model_validate(ex), ex.link.position) for ex in quiz.exercises]
    )

    return quiz_public

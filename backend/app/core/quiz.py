from uuid import UUID
from sqlmodel import Session, select

from app.models import Exercise, ExerciseTag, TagPublic, Quiz, QuizPublic

def form_quiz(length: int, tags: list[TagPublic], owner_id: str, session: Session) -> QuizPublic:
    """
    Form a quiz by selecting exercises based on the provided tags and populate a Quiz model.

    :param length: The number of exercises to include in the quiz.
    :param tags: A list of TagPublic objects to filter exercises.
    :param owner_id: The ID of the user owning the quiz.
    :param session: The database session.
    :return: A QuizPublic object representing the created quiz.
    """
    tag_ids = [tag.id for tag in tags]
    subquery = (
        select(Exercise.id)
        .join(ExerciseTag)
        .where(ExerciseTag.tag_id.in_(tag_ids))
        .distinct()
        .limit(length)
        .subquery()
    )
    
    # Затем получаем полные объекты Exercise по этим ID
    statement = select(Exercise).where(Exercise.id.in_(select(subquery.c.id)))
    exercises = session.exec(statement).all()

    quiz = Quiz(owner_id=owner_id)
    quiz.exercises = exercises
    session.add(quiz)
    session.commit()
    session.refresh(quiz)

    return QuizPublic.model_validate(quiz)
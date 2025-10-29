from sqlmodel import Session
from app.core.quiz import form_quiz
from app.models import Exercise, Quiz, QuizPublic
from tests.utils.user import create_random_user
from tests.utils.tags import create_random_tag
from tests.utils.exercise import create_random_exercise


def create_random_quiz(db: Session) -> QuizPublic:
    """
    Utitility function that creates a random quiz.
    :param: db - the database session.
    :returns: QuizPublic - public representation of the quiz.
    """
    user = create_random_user(db)
    tag = create_random_tag(db)
    for _ in range(5):
        exercise = create_random_exercise(db)
        exercise.tags.append(tag)
        db.add(exercise)
    db.commit()
    quiz = form_quiz(length=5, tags=[tag], owner_id=user.id, session=db)
    return quiz

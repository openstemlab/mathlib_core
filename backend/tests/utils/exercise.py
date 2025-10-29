from sqlmodel import Session

from app import crud
from app.models import Exercise, ExerciseCreate, ExerciseTag, Tag
from tests.utils.utils import random_lower_string


def create_random_exercise(db: Session) -> Exercise:
    """Creates a randomised exercise."""
    
    source_name = random_lower_string()
    source_id = random_lower_string()
    text = random_lower_string()
    solution = random_lower_string()
    exercise_in = ExerciseCreate(
        source_name=source_name,
        source_id=source_id,
        text=text,
        solution=solution,
    )
    return crud.create_exercise(session=db, exercise_in=exercise_in)

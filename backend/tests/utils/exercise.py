from sqlmodel import Session

from app import crud
from app.models import Exercise, ExerciseCreate, ExerciseTag, Tag
from tests.utils.utils import random_lower_string

def create_random_exercise(db: Session) -> Exercise:
    source_name = random_lower_string()
    source_id = random_lower_string()
    text = random_lower_string()
    solution = random_lower_string()
    tag1 = crud.create_tag(
        session=db,
        tag_in=Tag(
            name=random_lower_string(),
            description=random_lower_string(),
            exercises=[],
        )
    )
    tag2 = crud.create_tag(
        session=db,
        tag_in=Tag(
            name=random_lower_string(),
            description=random_lower_string(),
            exercises=[],
        )
    )
    exercise_in = Exercise(source_name=source_name, source_id=source_id, text=text, solution=solution, tags=[tag1, tag2])
    return crud.create_exercise(session=db, exercise_in=exercise_in)
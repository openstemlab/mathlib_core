from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models import Exercise, ExerciseCreate
from tests.utils.utils import random_lower_string


async def create_random_exercise(db: AsyncSession) -> Exercise:
    """Creates a randomised exercise."""
    
    source_name = random_lower_string()
    source_id = random_lower_string()
    text = random_lower_string()
    solution = random_lower_string()
    tags=[random_lower_string()]
    exercise = Exercise(
        source_name=source_name,
        source_id=source_id,
        text=text,
        solution=solution,
        tags=tags,
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return exercise
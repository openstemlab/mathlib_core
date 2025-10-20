import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Exercise, ExerciseTag, ExercisePublic, ExercisesPublic, ExerciseCreate, ExerciseUpdate, Message

router = APIRouter(prefix="/exercises", tags=["exercises"])

@router.get("/", response_model=ExercisesPublic)
def read_exercises(
    session: SessionDep, skip: int = 0, limit: int = 100
)-> Any:
    """
    Retrieve exercises.
    """
    count_statement = select(func.count()).select_from(Exercise)
    count = session.exec(count_statement).one()
    statement = select(Exercise).offset(skip).limit(limit)
    exercises = session.exec(statement).all()
    return ExercisesPublic(data=exercises, count=count)

@router.get("/{id}", response_model=ExercisePublic)
def read_exercise(session: SessionDep, id: uuid.UUID)-> Any:
    """
    Get exercise by ID.
    """
    exercise = session.get(Exercise, id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise

@router.post("/", response_model=ExercisePublic)
def create_exercise(
    *, session: SessionDep, current_user: CurrentUser, exercise_in: ExerciseCreate
) -> Any:
    """
    Create a new exercise.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    exercise = Exercise.model_validate(exercise_in)
    session.add(exercise)
    session.commit()
    session.refresh(exercise)
    return exercise

@router.put("/{id}", response_model=ExercisePublic)
def update_exercise(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID, exercise_in: ExerciseUpdate
) -> Any:
    """
    Update an existing exercise.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    exercise = session.get(Exercise, id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    exercise_data = exercise_in.model_dump(exclude_unset=True)
    exercise.sqlmodel_update(exercise_data)
    session.add(exercise)
    session.commit()
    session.refresh(exercise)
    return exercise

@router.delete("/{id}")
def delete_exercise(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an exercise.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    exercise = session.get(Exercise, id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    session.delete(exercise)
    session.commit()
    return Message(message="Exercise deleted successfully")
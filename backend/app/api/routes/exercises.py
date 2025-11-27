from uuid_extensions import uuid7str
from typing import Any
from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Exercise,
    ExercisePublic,
    ExercisesPublic,
    ExerciseCreate,
    ExerciseUpdate,
    Message,
)

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("/", response_model=ExercisesPublic)
async def read_exercises(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve exercises.
    """

    count_statement = select(func.count()).select_from(Exercise)
    count = (await session.exec(count_statement)).one()
    statement = select(Exercise).offset(skip).limit(limit).order_by(Exercise.id)
    exercises = (await session.exec(statement)).all()
    public_list = []
    for exercise in exercises:
        exercise_data = ExercisePublic.model_validate(exercise)
        public_list.append(exercise_data)
    return ExercisesPublic(data=public_list, count=count)


@router.get("/{id}", response_model=ExercisePublic)
async def read_exercise(session: SessionDep, id: str) -> Any:
    """
    Get exercise by ID.
    """

    exercise = await session.get(Exercise, id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    response = ExercisePublic.model_validate(exercise)
    return response


@router.post("/", response_model=ExercisePublic)
async def create_exercise(
    *, session: SessionDep, current_user: CurrentUser, exercise_in: ExerciseCreate
) -> Any:
    """
    Create a new exercise.
    """

    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    exercise = Exercise.model_validate(exercise_in)
    session.add(exercise)
    await session.commit()
    await session.refresh(exercise)

    response = ExercisePublic.model_validate(exercise)
    return response


@router.put("/{id}", response_model=ExercisePublic)
async def update_exercise(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: str,
    exercise_in: ExerciseUpdate,
) -> Any:
    """
    Update an existing exercise.
    """

    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    exercise = await session.get(Exercise, id)

    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    exercise_data = exercise_in.model_dump(exclude_unset=True)

    exercise.sqlmodel_update(exercise_data)
    session.add(exercise)
    await session.commit()
    await session.refresh(exercise)

    response = ExercisePublic.model_validate(exercise)
    return response


@router.delete("/{id}")
async def delete_exercise(
    *, session: SessionDep, current_user: CurrentUser, id: str
) -> Message:
    """
    Delete an exercise.
    """

    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    exercise = await session.get(Exercise, id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    await session.delete(exercise)
    await session.commit()

    return Message(message="Exercise deleted successfully")

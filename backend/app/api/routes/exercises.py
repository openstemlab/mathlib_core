import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Exercise, ExerciseTag, Tag, ExercisesPublic

router = APIRouter(prefix="/exercises", tags=["exercises"])

@router.get("/", response_model=ExercisesPublic)
def read_exercises(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
)-> Any:
    """
    Retrieve exercises.
    """
    count_statement = select(func.count()).select_from(Exercise)
    count = session.exec(count_statement).one()
    statement = select(Exercise).offset(skip).limit(limit)
    exercises = session.exec(statement).all()
    return ExercisesPublic(data=exercises, count=count)
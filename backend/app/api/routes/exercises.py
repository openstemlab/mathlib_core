import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Exercise, ExerciseTag, ExercisePublic, ExercisesPublic, ExerciseCreate, ExerciseUpdate, Tag, TagPublic, Message

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
    exercises_with_tags = []
    for exercise in exercises:
        tags = []
        stmt = select(Tag).join(ExerciseTag).where(ExerciseTag.exercise_id == exercise.id)
        db_tags = session.exec(stmt).all()
        
        exercise_data = ExercisePublic(
            id=exercise.id,
            source_name=exercise.source_name,
            source_id=exercise.source_id,
            text=exercise.text,
            solution=exercise.solution,
            false_answers=exercise.false_answers,
            formula=exercise.formula,
            illustration=exercise.illustration,
            tags=[TagPublic.model_validate(tag) for tag in db_tags]
        )
        exercises_with_tags.append(exercise_data) 
    return ExercisesPublic(data=exercises_with_tags, count=count)


@router.get("/{id}", response_model=ExercisePublic)
def read_exercise(session: SessionDep, id: str)-> Any:
    """
    Get exercise by ID.
    """
    exercise = session.get(Exercise, id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    stmt = select(Tag).join(ExerciseTag).where(ExerciseTag.exercise_id == exercise.id)
    db_tags = session.exec(stmt).all()
    
    # creating response with tag info
    response = ExercisePublic(
        id=exercise.id,
        source_name=exercise.source_name,
        source_id=exercise.source_id,
        text=exercise.text,
        solution=exercise.solution,
        false_answers=exercise.false_answers,
        formula=exercise.formula,
        illustration=exercise.illustration,
        tags=[TagPublic.model_validate(tag) for tag in db_tags]
    )
    return response


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
    *, session: SessionDep, current_user: CurrentUser, id: str, exercise_in: ExerciseUpdate
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

    if "tags" in exercise_data:
        # removing current tags
        exercise.tags = []
        session.commit()
        
        # getting new tags from databse
        for tag_data in exercise_data["tags"]:
            tag = session.get(Tag, tag_data["id"])
            if tag:
                exercise.tags.append(tag)
        
        # clearing tags from data so there wont be conflict
        del exercise_data["tags"]

    # Обновляем остальные поля
    exercise.sqlmodel_update(exercise_data)
    session.add(exercise)
    session.commit()
    session.refresh(exercise)
    
    # Получаем обновленные теги для ответа
    stmt = select(Tag).join(ExerciseTag).where(ExerciseTag.exercise_id == exercise.id)
    db_tags = session.exec(stmt).all()
    
    # Создаем ответ с обновленными данными
    response = ExercisePublic(
        id=exercise.id,
        source_name=exercise.source_name,
        source_id=exercise.source_id,
        text=exercise.text,
        solution=exercise.solution,
        false_answers=exercise.false_answers,
        formula=exercise.formula,
        illustration=exercise.illustration,
        tags=[TagPublic.model_validate(tag) for tag in db_tags]
    )
    return response

@router.delete("/{id}")
def delete_exercise(
    *, session: SessionDep, current_user: CurrentUser, id: str
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
"""
Quizzes only accessable by the owner
"""

from uuid_extensions import uuid7str
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select, func


from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Quiz,
    QuizCreate,
    QuizUpdate,
    QuizPublic,
    QuizzesPublic,
    QuizExercise,
    Exercise,
    ExercisePublic,
    Message,
    User,
)

router = APIRouter(prefix="/users/{user_id}/quizzes", tags=["quizzes"])


@router.get("/", response_model=QuizzesPublic)
async def read_quizzes(
    session: SessionDep,
    current_user: CurrentUser,
    user_id: str,
    skip: int = 0,
    limit: int = 10,
) -> Any:
    """
    Retrieve all quizzes for a user.
    """
    user = await session.get(User, user_id)
    if user == current_user:
        count_statement = select(func.count()).select_from(Quiz)
        count = (await session.exec(count_statement)).one()
        statement = (
            select(Quiz).where(Quiz.owner_id == user_id).offset(skip).limit(limit)
        )
        if count == 0:
            return QuizzesPublic(data=[], count=0)
        else:
            quizzes = (await session.exec(statement)).all()
            return QuizzesPublic(data=quizzes, count=count)

    else:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this resource.",
        )


@router.get("/{id}", response_model=QuizPublic)
async def read_quiz(
    session: SessionDep, current_user: CurrentUser, id: str
) -> Any:
    """
    Access point for a specific quiz.
    """
    quiz = await session.get(Quiz, id)

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if current_user.id == quiz.owner_id:
        statement = (
            select(Exercise).join(QuizExercise).where(QuizExercise.quiz_id == id)
        )
        db_exercises = (await session.exec(statement)).all()
        response = QuizPublic(
            id=quiz.id,
            owner_id=quiz.owner_id,
            is_active=quiz.is_active,
            exercises=[
                ExercisePublic.model_validate(exercise) for exercise in db_exercises
            ],
        )
        return response
    else:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this resource.",
        )


@router.post("/", response_model=QuizPublic)
async def create_quiz(
    session: SessionDep, current_user: CurrentUser, user_id: str, quiz_in: QuizCreate
) -> Any:
    """
    Save a new quiz.
    """
    if current_user.id == user_id:
        data = quiz_in.model_dump()
        data["owner_id"] = current_user.id
        quiz = Quiz.model_validate(data)
        quiz.owner = current_user
        session.add(quiz)
        await session.commit()
        await session.refresh(quiz)
        return QuizPublic.model_validate(quiz)
    else:
        raise HTTPException(
            status_code=403, detail="You cant save a quiz for someone else."
        )


@router.put("/{id}", response_model=QuizPublic)
async def update_quiz(
    session: SessionDep,
    current_user: CurrentUser,
    user_id: str,
    id: str,
    quiz_in: QuizUpdate,
) -> Any:
    """
    Update quiz.
    """
    quiz = await session.get(Quiz, id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if current_user.id == user_id:
        quiz_data = quiz_in.model_dump(exclude_unset=True)
        for key, value in quiz_data.items():
            setattr(quiz, key, value)
        session.add(quiz)
        await session.commit()
        await session.refresh(quiz)
        return quiz
    else:
        raise HTTPException(
            status_code=403, detail="You cant save a quiz for someone else."
        )


@router.delete("/{id}", response_model=Message)
async def delete_quiz(
    session: SessionDep,
    current_user: CurrentUser,
    id: str,
) -> Message:
    """
    Delete quiz.
    """
    quiz = await session.get(Quiz, id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    if current_user.id == quiz.owner_id:
        await session.delete(quiz)
        await session.commit()
        return Message(message="Quiz deleted successfully")

    else:
        raise HTTPException(
            status_code=403, detail="You cant delete a quiz for someone else."
        )

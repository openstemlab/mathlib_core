"""
Quizzes only accessable by the owner
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select, func

from app.api.deps import CurrentUser, SessionDep
from app.models import Quiz, QuizCreate, QuizUpdate, QuizPublic, QuizzesPublic, Message, User

router = APIRouter(prefix="/users/{user_id}/quizzes", tags=["quizzes"])

@router.get("/", response_model=QuizzesPublic)
def read_quizzes(
    session: SessionDep, 
    current_user: CurrentUser, 
    user_id: uuid.UUID, 
    skip: int = 0, 
    limit: int = 10
    ) -> Any:
    """
    Retrieve all quizzes for a user.
    """
    user = session.get(User, user_id)
    if user == current_user:
        count_statement = select(func.count()).select_from(Quiz)
        count = session.exec(count_statement).one()
        statement = select(Quiz).where(Quiz.owner_id == user_id).offset(skip).limit(limit)
        if count == 0: 
            return QuizzesPublic(data=[], count=0)
        else:
            quizzes = session.exec(statement).all()
            return QuizzesPublic(data=quizzes, count=count)
        
    else:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    
@router.get("/{id}", response_model=QuizPublic)
def read_quiz(
    session: SessionDep, 
    current_user: CurrentUser, 
    user_id: uuid.UUID, 
    id: uuid.UUID) -> Any:
    """
    Access point for a specific quiz.
    """
    if current_user.id == user_id:
        quiz = session.get(Quiz, id)
        if quiz:
            return quiz
        else:
            raise HTTPException(status_code=404, detail="Quiz not found")
    else:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    
@router.post("/", response_model=QuizPublic)
def create_quiz(
    session: SessionDep, 
    current_user: CurrentUser, 
    user_id: uuid.UUID, 
    quiz_in: QuizCreate
    ) -> Any:
    """
    Save a new quiz.
    """
    if current_user.id == user_id:
        quiz = Quiz.model_validate(quiz_in)
        quiz.owner_id = current_user.id
        session.add(quiz)
        session.commit()
        session.refresh(quiz)
        return quiz
    else:
        raise HTTPException(status_code=403, detail="You cant save a quiz for someone else.")
    
@router.put("/{id}", response_model=QuizPublic)
def update_quiz(
    session: SessionDep, 
    current_user: CurrentUser, 
    user_id: uuid.UUID, 
    id: uuid.UUID, 
    quiz_in: QuizUpdate
    ) -> Any:
    """
    Update quiz.
    """
    if current_user.id == user_id:
        quiz = session.get(Quiz, id)
        if quiz:
            quiz = Quiz.model_validate(quiz_in)
            session.add(quiz)
            session.commit()
            session.refresh(quiz)
        else:
            raise HTTPException(status_code=404, detail="Quiz not found")
    else:
        raise HTTPException(status_code=403, detail="You cant save a quiz for someone else.")


@router.delete("/{id}", responce_model=Message)
def delete_quiz(
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    id: uuid.UUID,
    ) -> Message:
    """
    Delete quiz.
    """
    if current_user.id == user_id:
        quiz = session.get(Quiz, id)
        if quiz:
            session.delete(quiz)
            session.commit()
        else:
            raise HTTPException(status_code=404, detail="Quiz not found")
    else:
        raise HTTPException(status_code=403, detail="You cant delete a quiz for someone else.")
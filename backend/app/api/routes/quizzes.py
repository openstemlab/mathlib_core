"""
Quizzes only accessable by the owner
"""

from uuid_extensions import uuid7str
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select, func


from app.api.deps import CurrentUser, SessionDep
from app.core.quiz import (
    form_quiz, 
    deactivate_quizzes,
    get_quiz_by_id,
    get_all_quizzes_by_owner,
    create_quiz,
    update_quiz,
    delete_quiz,
    start_new_quiz,
    save_quiz_progress,
    load_active_quiz,
    submit_quiz,
)

from app.models import (
    Quiz,
    QuizCreate,
    QuizUpdate,
    QuizPublic,
    QuizzesPublic,
    QuizStatusChoices,
    QuizExercise,
    StartQuizRequest,
    Exercise,
    ExercisePublic,
    SubmitAnswer,
    Message,
    User,
)

router = APIRouter(prefix="/users/{user_id}/quizzes", tags=["quizzes"])


@router.get("/", response_model=QuizzesPublic)
async def read_quizzes_route(
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
        quiz_list = await get_all_quizzes_by_owner(owner_id=user_id, session=session)
        count = len(quiz_list)
        quizzes = quiz_list[skip : skip + limit]
        return QuizzesPublic(data=quizzes, count=count)

    else:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this resource.",
        )


@router.get("/{id}", response_model=QuizPublic)
async def read_quiz_route(
    session: SessionDep, current_user: CurrentUser, id: str
) -> Any:
    """
    Access point for a specific quiz.
    """
    quiz = await get_quiz_by_id(quiz_id=id, session=session)

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if current_user.id == quiz.owner_id:
        return quiz
    else:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this resource.",
        )


@router.post("/", response_model=Message)
async def create_quiz_route(
    session: SessionDep, current_user: CurrentUser, user_id: str, quiz_in: QuizCreate
) -> Any:
    """
    Save a new quiz.
    """
    if current_user.id == user_id:
        await create_quiz(
            quiz_in=quiz_in,
            session=session,
            owner_id=user_id,
        )        
        return Message(message="Quiz created successfully")
    else:
        raise HTTPException(
            status_code=403, detail="You cant save a quiz for someone else."
        )


@router.put("/{id}", response_model=QuizPublic)
async def update_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
    user_id: str,
    id: str,
    quiz_in: QuizUpdate,
) -> Any:
    """
    Update quiz.
    """
    quiz = await update_quiz(quiz_id=id, quiz_in=quiz_in, session=session)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if current_user.id == user_id:
        return quiz
    else:
        raise HTTPException(
            status_code=403, detail="You cant save a quiz for someone else."
        )


@router.delete("/{id}", response_model=Message)
async def delete_quiz_route(
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
    

@router.post("/start", response_model=QuizPublic)
async def start_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
    quiz_data: StartQuizRequest,
) -> Any:
    """
    Start a a new quiz.
    """
    quiz =  await start_new_quiz(quiz_data=quiz_data, session=session, owner_id=current_user.id)

    return quiz




@router.put("/save", response_model=Message)
async def save_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
    id: str,
    answers: SubmitAnswer,
) -> Any:
    """
    Save an active quiz.
    """
    #assuming that the quiz already created by /quizzes/start endpoint
    quiz = await session.get(Quiz, id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    if quiz.status == QuizStatusChoices.SUBMITTED.value:
        raise HTTPException(
            status_code=400,
            detail="Cannot save a submitted quiz.",
        )

    if current_user.id != quiz.owner_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to save this quiz.",
        )
    
    await save_quiz_progress(session=session, quiz=quiz, answers=answers)
    return Message(message="Quiz progress saved successfully")

    

@router.get("/load", response_model=QuizPublic)
async def load_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Load an active quiz.
    """
    quiz = await load_active_quiz(session=session, owner_id=current_user.id)

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    return quiz


@router.post("/submit", response_model=Message)
async def submit_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
    answers: SubmitAnswer,
    id: str,
) -> Any:
    """
    Submit a quiz by setting its status to submitted.
    """
    quiz = await session.get(Quiz, id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if current_user.id != quiz.owner_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to submit this quiz.",
        )
    try:
        await submit_quiz(session=session, quiz=quiz, answers=answers)
        return Message(message="Quiz submitted successfully")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


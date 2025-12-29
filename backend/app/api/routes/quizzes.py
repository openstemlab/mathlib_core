"""
Quizzes only accessable by the owner
"""

from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.core.quiz import (
    get_quiz_by_id,
    get_all_quizzes_by_owner,
    create_quiz,
    update_quiz,
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
    QuizExercise,
    QuizStatusChoices,
    StartQuizRequest,
    SubmitAnswer,
    QuizForGrading,
    QuizExerciseForGrading,
    ManualGradeRequest,
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


# reminder to myself - /load conflicts with /{id}, more specific endpoints should go first
@router.get("/load", response_model=QuizPublic)
async def load_quiz_route(
    user_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Load an active quiz.
    """

    if current_user.id != user_id:
        raise HTTPException(
            status_code=403, detail="You can only load quizzes for yourself."
        )
    quiz = await load_active_quiz(session=session, owner_id=user_id)

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    return quiz


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
    quiz = await session.get(Quiz, id)

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if current_user.id == user_id:
        updated_quiz = await update_quiz(quiz_id=id, quiz_in=quiz_in, session=session)
        return updated_quiz
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
        await session.flush()
        return Message(message="Quiz deleted successfully")

    else:
        raise HTTPException(
            status_code=403, detail="You cant delete a quiz for someone else."
        )


@router.post("/start", response_model=QuizPublic)
async def start_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
    user_id: str,
    quiz_data: StartQuizRequest,
) -> Any:
    """
    Start a a new quiz.
    """

    if current_user.id != user_id:
        raise HTTPException(
            status_code=403, detail="You can only start quizzes for yourself."
        )
    quiz = await start_new_quiz(
        quiz_data=quiz_data, session=session, owner_id=current_user.id
    )

    return quiz


@router.put("/{id}/save", response_model=Message)
async def save_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
    id: str,
    answers: SubmitAnswer,
) -> Any:
    """
    Save an active quiz. Only one active quiz can be saved at a time.
    """
    # assuming that the quiz already created by /quizzes/start endpoint
    quiz = await session.get(Quiz, id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if quiz.status != QuizStatusChoices.ACTIVE.value:
        raise HTTPException(
            status_code=400,
            detail="Cannot save inactive quiz.",
        )

    if current_user.id != quiz.owner_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to save this quiz.",
        )

    await save_quiz_progress(session=session, quiz=quiz, answers=answers)
    return Message(message="Quiz progress saved successfully")


@router.post("/{id}/submit", response_model=Message)
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
    if quiz.status != QuizStatusChoices.ACTIVE.value:
        raise HTTPException(
            status_code=400, detail="Only active quizzes can be submitted."
        )
    try:
        await submit_quiz(session=session, quiz=quiz, answers=answers)
        return Message(message="Quiz submitted successfully")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    


@router.get("/{id}/grade", response_model=QuizForGrading)
async def view_quiz_for_grading_route(
    session: SessionDep,
    current_user: CurrentUser,
    id: str,
):
    """
    Teacher-only endpoint to view a quiz for manual grading.
    Returns exercises with student answers and current correctness.
    """
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can grade quizzes.")

    quiz = await session.get(
        Quiz,
        id,
        options=[
            selectinload(Quiz.quiz_exercises).selectinload(QuizExercise.exercise),
            selectinload(Quiz.owner),
        ],
    )
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Fetch owner name
    owner_name = quiz.owner.full_name if quiz.owner else None

    # Fetch grader name if exists
    graded_by_name = None
    if quiz.graded_by_id and quiz.graded_by:
        graded_by_name = quiz.graded_by.full_name

    exercises_data = []
    for qe in quiz.quiz_exercises:
        exercises_data.append(
            QuizExerciseForGrading.from_db(qe)
            )

    return QuizForGrading(
        id=quiz.id,
        owner_id=quiz.owner_id,
        owner_name=owner_name,
        title=quiz.title,
        status=quiz.status,
        submitted_at=quiz.submitted_at,  
        exercises=exercises_data,
        final_score=quiz.final_score,
        feedback=quiz.feedback,
        graded_at=quiz.graded_at,
        graded_by_id=quiz.graded_by_id,
        graded_by_name=graded_by_name,
    )


@router.put("/{id}/grade", response_model=Message)
async def manual_grade_quiz_route(
    session: SessionDep,
    current_user: CurrentUser,
    id: str,
    request: ManualGradeRequest,
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can grade quizzes.")

    quiz = await session.get(
        Quiz,
        id,
        options=[selectinload(Quiz.quiz_exercises).selectinload(QuizExercise.exercise)],
    )
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Build map for fast lookup
    qe_map = {qe.exercise_id: qe for qe in quiz.quiz_exercises}
    submitted_exercise_ids = {corr.exercise_id for corr in request.corrections}

    # Validate: all quiz exercises must be corrected
    quiz_exercise_ids = set(qe_map.keys())
    if submitted_exercise_ids != quiz_exercise_ids:
        missing = quiz_exercise_ids - submitted_exercise_ids
        extra = submitted_exercise_ids - quiz_exercise_ids
        msg_parts = []
        if missing:
            msg_parts.append(f"missing corrections for exercise IDs: {list(missing)}")
        if extra:
            msg_parts.append(f"extra corrections for invalid exercise IDs: {list(extra)}")
        raise HTTPException(
            status_code=400,
            detail="; ".join(msg_parts)
        )

    correct = 0
    total = len(quiz.quiz_exercises)
    for correction in request.corrections:
        qe = qe_map[correction.exercise_id]
        qe.is_correct = correction.is_correct
        session.add(qe)
        if correction.is_correct:
            correct += 1
    quiz.final_score = (correct / total * 100) if total > 0 else 0.0

    # Update grading metadata
    quiz.graded_at = datetime.now(timezone.utc)
    quiz.graded_by_id = current_user.id
    quiz.feedback = request.feedback

    # Update status if provided
    if request.status is not None:
        quiz.status = request.status  

    session.add(quiz)
    await session.flush()

    return Message(message="Quiz manually graded successfully")

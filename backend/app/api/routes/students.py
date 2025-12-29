from fastapi import APIRouter, HTTPException

from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.models import Quiz, QuizGrade, StudentGrades
from app.api.deps import SessionDep, CurrentUser

router = APIRouter(prefix="/students", tags=["students"])

@router.get("/{student_id}/grades")
async def get_student_grades(
    student_id: str, 
    session: SessionDep, 
    current_user: CurrentUser
    )->StudentGrades:
    statement = select(Quiz).where(Quiz.owner_id == student_id, Quiz.submitted_at.is_not(None)).options(selectinload(Quiz.owner)).order_by(Quiz.submitted_at.desc())
    quizzes = (await session.exec(statement)).all()

    if not quizzes:
        raise HTTPException(status_code=404, detail="No quizzes found for this student.")

    grades = []
    for quiz in quizzes:
        grade = QuizGrade(
            quiz_id=quiz.id,
            title=quiz.title,
            submitted_at=quiz.submitted_at,
            score=quiz.final_score,
        )
        grades.append(grade)

    owner = quizzes[0].owner
    user_name = owner.full_name if owner and owner.full_name else "Unknown"
    return StudentGrades(
        user_id=student_id,
        user_name=user_name,
        grades=grades
    )
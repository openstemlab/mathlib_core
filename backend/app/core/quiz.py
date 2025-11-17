
import random
from uuid_extensions import uuid7str
from sqlmodel import  select
from sqlalchemy import cast, String, or_
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import (
    Exercise, 
    ExercisePublic, 
    Quiz, 
    QuizPublic, 
    QuizCreate, 
    QuizUpdate,
    QuizStatusChoices,
    QuizExercise, 
    User,
    StartQuizRequest,
    SubmitAnswer,
)


async def form_quiz(
    length: int,
    tags: list[str],
    owner_id: str,
    title: str | None,
    session: AsyncSession,
) -> QuizPublic:
    """
    Form a quiz by selecting exercises based on the provided tags and populate a Quiz model.

    :param length: The number of exercises to include in the quiz.
    :param tags: A list of TagPublic objects to filter exercises.
    :param owner_id: The ID of the user owning the quiz.
    :param session: The database session.
    :return: A QuizPublic object representing the created quiz.
    """

    statement = select(Exercise).where(
    or_(*[Exercise.tags.op('?')(tag) for tag in tags])).limit(length)
    exercises = (await session.exec(statement)).all()

    if len(exercises) < length:
        length = len(exercises)

    positions = list(range(length))
    random.shuffle(positions)

    quiz = Quiz(
        owner_id=owner_id,
        title=title,
        status="new",
    )

    # adding exercises and positions to the quiz using link model
    for exercise, position in zip(exercises, positions):
        quiz.exercises.append(exercise)
        # refreshing position for each exercise
        quiz_exercise = quiz.exercises[-1].link
        quiz_exercise.position = position

    session.add(quiz)
    await session.flush()
    await session.refresh(quiz, ["exercises"])

    quiz_public = QuizPublic(
        id=quiz.id,
        owner_id=quiz.owner_id,
        status=quiz.status,
        title=quiz.title,
        exercises=[(ExercisePublic.model_validate(ex), ex.link.position) for ex in quiz.exercises]
    )

    return quiz_public

async def deactivate_quizzes(owner_id: str, session: AsyncSession) -> None:
    """
    Deactivate all active quizzes for a given user by setting their status to 'in_progress'.

    :param owner_id: The ID of the user whose quizzes are to be deactivated.
    :param session: The database session.
    """
    statement = (
        select(Quiz)
        .where(Quiz.owner_id == owner_id, Quiz.status == "active")
        .with_for_update()  # Prevent concurrent modifications
    )
    active_quizzes = (await session.exec(statement)).all()

    for quiz in active_quizzes:
        quiz.status = "in_progress"
        session.add(quiz)

    await session.commit()


async def get_quiz_by_id(
    quiz_id: str,
    session: AsyncSession,
) -> QuizPublic | None:
    """
    Retrieve a Quiz by its ID.

    :param quiz_id: The ID of the quiz to retrieve.
    :param session: The database session.
    :return: The QuizPublic object if found, otherwise None.
    """
    statement = (
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.exercises))  # Eager load exercises
    )
    quiz = (await session.exec(statement)).first()
    if quiz:
        response = QuizPublic.model_validate(id=quiz.id,
                                        owner_id=quiz.owner_id,
                                        status=quiz.status,
                                        exercises=[(ExercisePublic.model_validate(ex), ex.link.position) for ex in quiz.exercises],
                                        title=quiz.title)
        return response
    return None


async def get_all_quizzes_by_owner(
    owner_id: str,
    session: AsyncSession,
) -> list[QuizPublic]:
    """
    Retrieve all quizzes for a given owner.

    :param owner_id: The ID of the user whose quizzes are to be retrieved.
    :param session: The database session.
    :return: A list of QuizPublic objects.
    """
    statement = (
        select(Quiz)
        .where(Quiz.owner_id == owner_id)
        .options(selectinload(Quiz.exercises))  # Eager load exercises
    )
    quizzes = (await session.exec(statement)).all()

    quiz_public_list = []
    for quiz in quizzes:
        quiz_public = QuizPublic.model_validate(
            id=quiz.id,
            owner_id=quiz.owner_id,
            status=quiz.status,
            exercises=[(ExercisePublic.model_validate(ex), ex.link.position) for ex in quiz.exercises],
            title=quiz.title
        )
        quiz_public_list.append(quiz_public)

    return quiz_public_list

async def create_quiz(
    quiz_in: QuizCreate,
    session: AsyncSession,
    owner_id: str,
) -> Quiz:
    """
    Create a new Quiz in the database.

    :param quiz_in: The Quiz data to create.
    :param session: The database session.
    :return: The created Quiz object.
    """
    data = Quiz.model_dump(quiz_in)
    statement = select(User).where(User.id == owner_id)
    owner = (await session.exec(statement)).first()

    exercise_ids = [ex for ex, _ in quiz_in.exercises]
    exercises = []
    if exercise_ids:
        exercise_statement = select(Exercise).where(Exercise.id.in_(exercise_ids))
        exercises = (await session.exec(exercise_statement)).all()

    db_quiz = Quiz(
        owner_id=owner_id,
        owner=owner,
        status=data.get("status", "new"),
        title=data.get("title"),
        exercises=exercises,
    )

    positions = [pos for _, pos in quiz_in.exercises]
    for exercise, position in zip(db_quiz.exercises, positions):
        exercise.link.position = position
        session.add(exercise)
    session.add(db_quiz)
    await session.flush()
    await session.refresh(db_quiz)


async def update_quiz(quiz_id: str, quiz_in: QuizUpdate, session: AsyncSession) -> QuizPublic | None:
    """
    Update an existing Quiz in the database.

    :param quiz_id: The ID of the Quiz to update.
    :param quiz_in: The Quiz data to update.
    :param session: The database session.
    :return: The updated QuizPublic object if found, otherwise None.
    """
    statement = select(Quiz).where(Quiz.id == quiz_id)
    db_quiz = (await session.exec(statement)).first()

    if not db_quiz:
        return None

    quiz_data = quiz_in.model_dump(exclude_unset=True)
    for field, value in quiz_data.items():
        setattr(db_quiz, field, value)

    session.add(db_quiz)
    await session.commit()
    await session.refresh(db_quiz)

    quiz_public = QuizPublic.model_validate(
        id=db_quiz.id,
        owner_id=db_quiz.owner_id,
        status=db_quiz.status,
        exercises=[(ExercisePublic.model_validate(ex), ex.link.position) for ex in db_quiz.exercises],
        title=db_quiz.title
    )

    return quiz_public

async def delete_quiz(quiz_id: str, session: AsyncSession) -> bool:
    """
    Delete a Quiz from the database.

    :param quiz_id: The ID of the Quiz to delete.
    :param session: The database session.
    :return: True if the Quiz was deleted, False if not found.
    """
    statement = select(Quiz).where(Quiz.id == quiz_id)
    db_quiz = (await session.exec(statement)).first()

    if not db_quiz:
        return False

    await session.delete(db_quiz)
    await session.commit()
    return True


async def start_new_quiz(quiz_data: StartQuizRequest, session: AsyncSession, owner_id: str) -> QuizPublic:
    quiz = await form_quiz(
        length=quiz_data.length,
        tags=quiz_data.tags,
        owner_id=owner_id,
        title=quiz_data.title,
        session=session,
        )

    await deactivate_quizzes(owner_id=owner_id, session=session)
    
    quiz.status = QuizStatusChoices.ACTIVE.value

    session.add(quiz)
    await session.commit()
    await session.refresh(quiz)

    statement = (
        select(Exercise, QuizExercise.position)
        .join(QuizExercise)
        .where(QuizExercise.quiz_id == quiz.id)
        .order_by(QuizExercise.position)
    )
    result = await session.exec(statement)
    exercise_data = result.all()
    exercises = [ExercisePublic.model_validate(ex) for ex, pos in exercise_data]
    
    return QuizPublic(
        id=quiz.id,
        owner_id=quiz.owner_id,
        status=quiz.status,
        title=quiz.title,
        exercises=exercises,
    )


async def save_quiz_progress(session: AsyncSession, quiz: Quiz, answers: SubmitAnswer) -> QuizPublic:
    # pulling exercises linked to the quiz
    statement = (
        select(Exercise, QuizExercise)
        .join(QuizExercise)
        .where(QuizExercise.quiz_id == quiz.id)
    )
    exercise_data = (await session.exec(statement)).all()

    # making maps for easy access
    solution_map ={ex.exercise_id: ex.solution for ex, quiz_ex in exercise_data}

    exercise_map ={ex.exercise_id: quiz_ex for ex, quiz_ex in exercise_data}

    #checking answers, marking correctness
    for answer in answers.response:
        exercise_id = answer["exercise_id"]
        if exercise_id in solution_map:
            quiz_exercise = exercise_map[exercise_id]
            correct = answer["answer"].strip() == solution_map[exercise_id].strip()

            # Update correctness
            quiz_exercise.is_correct = correct
            session.add(quiz_exercise)
    quiz.status = QuizStatusChoices.ACTIVE.value
    session.add(quiz)
    await session.flush()
    await session.refresh(quiz)


async def load_active_quiz(session: AsyncSession, owner_id: str) -> QuizPublic | None:
    statement = (
        select(Quiz)
        .where(Quiz.owner_id == owner_id, Quiz.status == QuizStatusChoices.ACTIVE.value)
        .options(selectinload(Quiz.exercises))  # Eager load exercises
    )
    quiz = (await session.exec(statement)).first()
    if quiz:
        response = QuizPublic.model_validate(id=quiz.id,
                                        owner_id=quiz.owner_id,
                                        status=quiz.status,
                                        exercises=[(ExercisePublic.model_validate(ex), ex.link.position) for ex in quiz.exercises],
                                        title=quiz.title)
        return response
    return None


async def submit_quiz(session: AsyncSession, quiz: Quiz, answers: SubmitAnswer):
    statement = (
        select(Exercise, QuizExercise)
        .join(QuizExercise)
        .where(QuizExercise.quiz_id == quiz.id)
    )
    exercise_data = (await session.exec(statement)).all()

    # making maps for easy access
    solution_map ={ex.exercise_id: ex.solution for ex, quiz_ex in exercise_data}

    exercise_map ={ex.exercise_id: quiz_ex for ex, quiz_ex in exercise_data}

    for answer in answers.response:
        exercise_id = answer["exercise_id"]
        if exercise_id in solution_map:
            quiz_exercise = exercise_map[exercise_id]
            correct = answer["answer"].strip() == solution_map[exercise_id].strip()

            # Update correctness
            quiz_exercise.is_correct = correct
            session.add(quiz_exercise)
    quiz.status = QuizStatusChoices.SUBMITTED.value
    session.add(quiz)
    await session.flush()
    await session.refresh(quiz)


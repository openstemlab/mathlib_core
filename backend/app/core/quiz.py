import random
import logging
from uuid_extensions import uuid7str
from sqlmodel import select, func
from sqlalchemy import cast, String, or_, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException

from app.models import (
    Exercise,
    ExercisePublic,
    Quiz,
    QuizPublic,
    QuizCreate,
    QuizUpdate,
    QuizStatusChoices,
    QuizExercise,
    QuizExerciseDataPublic,
    User,
    StartQuizRequest,
    SubmitAnswer,
)

logger = logging.getLogger(__name__)


async def form_quiz(
    length: int,
    tags: list[str] | None,
    owner_id: str,
    session: AsyncSession,
    title: str | None = None,
) -> Quiz:
    """
    Form a quiz by selecting exercises based on the provided tags and populate a Quiz model.
    If no tags provided, fills it with random exercises.

    :param length: The number of exercises to include in the quiz. If zero or negative, an empty quiz is created.
    :param tags: A list of tags to filter exercises.
    :param owner_id: The ID of the user owning the quiz.
    :param session: The database session.
    :param title: Optional title for the quiz.
    :return: A Quiz object representing the created quiz.
    """

    if length <= 0:
        return Quiz(owner_id=owner_id, title=title, status="new", exercises=[])

    if tags:
        statement = (
            select(Exercise)
            .where(or_(*[Exercise.tags.op("?")(tag) for tag in tags]))
            .limit(length)
        )
    else:
        statement = select(Exercise).order_by(func.random()).limit(length)

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

    session.add(quiz)
    await session.flush()

    # adding exercises and positions to the quiz using link model
    for exercise, position in zip(exercises, positions):
        quiz_exercise = QuizExercise(
            quiz_id=quiz.id,
            exercise_id=exercise.id,
            position=position,
        )

        session.add(quiz_exercise)

    await session.flush()
    await session.refresh(quiz, ["exercises"])

    return quiz


async def deactivate_quizzes(owner_id: str, session: AsyncSession) -> None:
    """Deactivate any currently active quizzes for the user.

    This is used to ensure only one active quiz exists, even though
    the DB enforces this via constraint. It prevents IntegrityError
    during new quiz creation and provides clean state transitions.

    Safe to call even if no active quizzes exist.

    :param owner_id: The ID of the user whose quizzes are to be deactivated.
    :param session: The database session.
    """

    statement = (
        update(Quiz)
        .where(Quiz.owner_id == owner_id, Quiz.status == QuizStatusChoices.ACTIVE.value)
        .values(status=QuizStatusChoices.IN_PROGRESS.value)
    )
    await session.exec(statement)
    await session.flush()


async def get_quiz_by_id(
    quiz_id: str,
    session: AsyncSession,
) -> QuizPublic | None:
    """Retrieve a Quiz by its ID.

    :param quiz_id: The ID of the quiz to retrieve.
    :param session: The database session.
    :return: The QuizPublic object if found, otherwise None.
    """
    statement = (
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.quiz_exercises).selectinload(QuizExercise.exercise))
    )
    quiz = (await session.exec(statement)).first()

    if not quiz:
        return None

    exercises_data = [
        QuizExerciseDataPublic(
            exercise=ExercisePublic.model_validate(qe.exercise),
            position=qe.position,
        )
        for qe in quiz.quiz_exercises
    ]

    response = QuizPublic(
        id=quiz.id,
        owner_id=quiz.owner_id,
        status=quiz.status,
        exercises=exercises_data,
        title=quiz.title,
    )
    return response


async def get_all_quizzes_by_owner(
    owner_id: str,
    session: AsyncSession,
) -> list[QuizPublic]:
    """Retrieve all quizzes for a given owner.

    :param owner_id: The ID of the user whose quizzes are to be retrieved.
    :param session: The database session.
    :return: A list of QuizPublic objects.
    """
    statement = (
        select(Quiz)
        .where(Quiz.owner_id == owner_id)
        .options(selectinload(Quiz.quiz_exercises).selectinload(QuizExercise.exercise))
        .order_by(Quiz.id)
    )
    request = await session.exec(statement)
    quizzes = request.all()

    quiz_public_list = []
    for quiz in quizzes:
        quiz_public = QuizPublic(
            id=quiz.id,
            owner_id=quiz.owner_id,
            status=quiz.status,
            exercises=[
                QuizExerciseDataPublic(
                    exercise=ExercisePublic.model_validate(qe.exercise),
                    position=qe.position,
                )
                for qe in quiz.quiz_exercises
            ],
            title=quiz.title,
        )
        quiz_public_list.append(quiz_public)

    return quiz_public_list


async def create_quiz(
    quiz_in: QuizCreate,
    session: AsyncSession,
    owner_id: str,
):
    """Create a new Quiz in the database. Empty quizzes are allowed.

    :param quiz_in: The Quiz data to create.
    :param session: The database session.
    :param owner_id: The ID of the user creating the quiz.
    :raises ValueError: If any exercise IDs are duplicated or not found.
    """

    if quiz_in.exercise_positions:
        # Detect duplicates
        seen_ids = set()
        for ex_pos in quiz_in.exercise_positions:
            ex_id = ex_pos.exercise.id
            if ex_id in seen_ids:
                raise ValueError(f"Duplicate exercise ID in quiz: {ex_id}")
            seen_ids.add(ex_id)

        # Fetch all exercises in one query
        exercise_ids = [ex.exercise.id for ex in quiz_in.exercise_positions]
        result = await session.exec(
            select(Exercise).where(Exercise.id.in_(exercise_ids))
        )
        exercises = list(result.all())

        # Fail fast: all exercises must exist
        found_ids = {ex.id for ex in exercises}
        missing = set(exercise_ids) - found_ids
        if missing:
            raise ValueError(f"Exercises not found in DB: {missing}")

        # Build position map before reordering
        position_map = {
            ex.exercise.id: ex.position for ex in quiz_in.exercise_positions
        }
    else:
        exercises = []
        position_map = {}

    db_quiz = Quiz(
        owner_id=owner_id,
        status=quiz_in.status or "new",
        title=quiz_in.title,
    )
    session.add(db_quiz)
    await session.flush()

    # Create links
    for exercise in exercises:
        quiz_exercise = QuizExercise(
            quiz_id=db_quiz.id,
            exercise_id=exercise.id,
            position=position_map[exercise.id],
        )
        session.add(quiz_exercise)

    await session.flush()


async def update_quiz(
    quiz_id: str, quiz_in: QuizUpdate, session: AsyncSession
) -> QuizPublic | None:
    """Update an existing Quiz in the database. Exercises are replaced if provided, so empty list leads to empty quiz, add existing exercises to keep them.

    :param quiz_id: The ID of the Quiz to update.
    :param quiz_in: The QuizUpdate object carrying update data.
    :param session: The database session.
    :return: The updated QuizPublic object if found, otherwise None.
    """
    statement = (
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.quiz_exercises).selectinload(QuizExercise.exercise))
    )
    db_quiz = (await session.exec(statement)).first()

    if not db_quiz:
        return None

    if quiz_in.status is not None:
        db_quiz.status = quiz_in.status
        session.add(db_quiz)
        await session.flush()
    if quiz_in.title is not None:
        db_quiz.title = quiz_in.title
        session.add(db_quiz)
        await session.flush()

    if "exercise_positions" in quiz_in.model_fields_set:
        # Clear existing links
        for link in db_quiz.quiz_exercises:
            await session.delete(link)
        await session.flush()

        # Add new links
        if quiz_in.exercise_positions is not None:
            for ex_pos in quiz_in.exercise_positions:
                quiz_exercise = QuizExercise(
                    quiz_id=db_quiz.id,
                    exercise_id=ex_pos.exercise.id,  # ex_pos is QuizExerciseData
                    position=ex_pos.position,
                )
                session.add(quiz_exercise)

            await session.flush()
        await session.refresh(db_quiz, attribute_names=["quiz_exercises"])

    await session.refresh(db_quiz)

    exercises_data = [
        QuizExerciseDataPublic(
            exercise=ExercisePublic.model_validate(qe.exercise),
            position=qe.position,
        )
        for qe in db_quiz.quiz_exercises
    ]

    quiz_public = QuizPublic(
        id=db_quiz.id,
        owner_id=db_quiz.owner_id,
        status=db_quiz.status,
        exercises=exercises_data,
        title=db_quiz.title,
    )

    return quiz_public


async def delete_quiz(quiz_id: str, session: AsyncSession) -> bool:
    """Delete a Quiz from the database.

    :param quiz_id: The ID of the Quiz to delete.
    :param session: The database session.
    :return: True if the Quiz was deleted, False if not found.
    """
    db_quiz = await session.get(Quiz, quiz_id)

    if not db_quiz:
        return False

    await session.delete(db_quiz)
    await session.flush()
    return True


async def start_new_quiz(
    quiz_data: StartQuizRequest, session: AsyncSession, owner_id: str
) -> QuizPublic:
    """Start a new quiz for a user, deactivating any existing active quizzes.

    :param quiz_data: StartQuizRequest object. Data required to start the quiz.
    :param session: The database session.
    :param owner_id: The ID of the user starting the quiz.
    :returns: QuizPublic - public representation of the started quiz.
    """

    await session.exec(select(User).where(User.id == owner_id).with_for_update())
    # Creating quiz in the database with given parameters
    quiz = await form_quiz(
        length=quiz_data.length,
        tags=quiz_data.tags,
        owner_id=owner_id,
        title=quiz_data.title,
        session=session,
    )

    # Deactivating any existing active quizzes for the user
    await deactivate_quizzes(owner_id=owner_id, session=session)
    # Setting the new quiz status to active
    quiz.status = QuizStatusChoices.ACTIVE.value

    session.add(quiz)
    await session.flush()

    await session.refresh(quiz)

    # Coverting to QuizPublic format
    statement = (
        select(Exercise, QuizExercise.position)
        .join(QuizExercise)
        .where(QuizExercise.quiz_id == quiz.id)
        .order_by(QuizExercise.position)
    )
    result = await session.exec(statement)
    exercise_data = result.all()

    exercises = [
        QuizExerciseDataPublic(exercise=ExercisePublic.model_validate(ex), position=pos)
        for ex, pos in exercise_data
    ]

    return QuizPublic(
        id=quiz.id,
        owner_id=quiz.owner_id,
        status=quiz.status,
        title=quiz.title,
        exercises=exercises,
    )


async def save_quiz_progress(
    session: AsyncSession, quiz: Quiz, answers: SubmitAnswer
) -> None:
    """Save the progress of an active quiz without submitting it.

    :param session: The database session.
    :param quiz: The Quiz object being progressed.
    :param answers: The answers provided so far.
    """
    # pulling exercises linked to the quiz
    statement = (
        select(Exercise, QuizExercise)
        .join(QuizExercise)
        .where(QuizExercise.quiz_id == quiz.id)
        .order_by(QuizExercise.position)
    )
    exercise_data = (await session.exec(statement)).all()

    # making maps for easy access
    solution_map = {ex.id: ex.solution for ex, quiz_ex in exercise_data}

    exercise_map = {ex.id: quiz_ex for ex, quiz_ex in exercise_data}

    # checking answers, marking correctness
    for answer in answers.response:
        exercise_id = answer.get("exercise_id")
        user_answer = answer.get("answer") or ""
        if not exercise_id:
            logger.warning("Missing exercise_id in answer: %s", answer)
        if exercise_id in solution_map:
            quiz_exercise = exercise_map[exercise_id]

            correct = user_answer.strip() == solution_map[exercise_id].strip()

            # Update correctness
            quiz_exercise.is_correct = correct
            session.add(quiz_exercise)
        else:
            logger.warning("Exercise ID %s not found in quiz %s", exercise_id, quiz.id)

    quiz.status = QuizStatusChoices.ACTIVE.value
    session.add(quiz)
    await session.flush()
    await session.refresh(quiz)


async def load_active_quiz(session: AsyncSession, owner_id: str) -> QuizPublic | None:
    """Load the active quiz for a user. If no active quiz exists, returns None. If by chance there is more than 1 active quiz(shouldnt be) returns oldest one.

    :param session: The database session.
    :param owner_id: The ID of the user whose active quiz is to be loaded.
    :returns: QuizPublic - public representation of the active quiz, or None if not found.
    """
    statement = (
        select(Quiz)
        .where(Quiz.owner_id == owner_id, Quiz.status == QuizStatusChoices.ACTIVE.value)
        .options(selectinload(Quiz.quiz_exercises).selectinload(QuizExercise.exercise))
        .order_by(Quiz.id)  # Eager load exercises
    )
    quiz = (await session.exec(statement)).first()

    if not quiz:
        return None

    exercises_data = [
        QuizExerciseDataPublic(
            exercise=ExercisePublic.model_validate(qe.exercise),
            position=qe.position,
        )
        for qe in quiz.quiz_exercises
    ]

    response = QuizPublic(
        id=quiz.id,
        owner_id=quiz.owner_id,
        status=quiz.status,
        exercises=exercises_data,
        title=quiz.title,
    )
    return response


async def submit_quiz(session: AsyncSession, quiz: Quiz, answers: SubmitAnswer):
    """Finalize and submit the quiz, marking it as submitted.

    :param session: The database session.
    :param quiz: The Quiz object being submitted.
    :param answers: The final answers provided.
    """
    statement = (
        select(Exercise, QuizExercise)
        .join(QuizExercise)
        .where(QuizExercise.quiz_id == quiz.id)
        .order_by(QuizExercise.position)
    )
    exercise_data = (await session.exec(statement)).all()

    # making maps for easy access
    solution_map = {ex.id: ex.solution for ex, quiz_ex in exercise_data}

    exercise_map = {ex.id: quiz_ex for ex, quiz_ex in exercise_data}

    for answer in answers.response:
        exercise_id = answer.get("exercise_id")
        user_answer = answer.get("answer") or ""
        if not exercise_id:
            logger.warning("Missing exercise_id in answer: %s", answer)
        if exercise_id in solution_map:
            quiz_exercise = exercise_map[exercise_id]

            correct = user_answer.strip() == solution_map[exercise_id].strip()

            quiz_exercise.is_correct = correct
            session.add(quiz_exercise)
        else:
            logger.warning("Exercise ID %s not found in quiz %s", exercise_id, quiz.id)
    quiz.status = QuizStatusChoices.SUBMITTED.value
    session.add(quiz)
    await session.flush()
    await session.refresh(quiz)

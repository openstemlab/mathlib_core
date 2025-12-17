from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from uuid_extensions import uuid7str
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError


from app.core.quiz import *
from app.models import QuizExerciseData
from tests.utils.exercise import create_random_exercise
from tests.utils.user import create_random_user

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_form_quiz(
    db: AsyncSession,
) -> None:
    """Tests the form_quiz function."""

    user = await create_random_user(db)
    tags = ["algebra", "geometry"]
    owner_id = user.id
    title = "Sample Quiz"

    # Create sample exercises
    for _ in range(10):
        exercise = await create_random_exercise(db, tags=tags)

    quiz = await form_quiz(
        length=5, tags=tags, owner_id=owner_id, title=title, session=db
    )

    assert quiz.title == title
    assert quiz.owner_id == owner_id
    assert len(quiz.exercises) == 5
    for exercise in quiz.exercises:
        assert "algebra" in exercise.tags


async def test_form_quiz_not_enough_exercises(db: AsyncSession):
    user = await create_random_user(db)
    tags = ["algebra"]

    # create only 2 exercises with the given tag
    for _ in range(2):
        await create_random_exercise(db, tags=tags)

    quiz = await form_quiz(length=5, tags=tags, owner_id=user.id, session=db)

    assert len(quiz.exercises) == 2  # Must be 2 since only 2 exercises are available
    assert quiz.title is None


async def test_form_quiz_no_tags_returns_random_exercises(db: AsyncSession):
    user = await create_random_user(db)

    for _ in range(5):
        await create_random_exercise(db, tags=["math"])

    quiz = await form_quiz(length=3, tags=None, owner_id=user.id, session=db)

    assert len(quiz.exercises) == 3
    assert quiz.owner_id == user.id
    assert quiz.title is None


async def test_form_quiz_empty_tags_returns_random_exercises(db: AsyncSession):
    user = await create_random_user(db)

    for _ in range(4):
        await create_random_exercise(db, tags=["physics"])

    quiz = await form_quiz(length=2, tags=[], owner_id=user.id, session=db)

    assert len(quiz.exercises) == 2


async def test_form_quiz_length_zero_returns_empty_quiz(db: AsyncSession):
    user = await create_random_user(db)
    quiz = await form_quiz(length=0, tags=["math"], owner_id=user.id, session=db)

    assert len(quiz.exercises) == 0
    assert quiz.owner_id == user.id


async def test_form_quiz_no_exercises_in_db(db: AsyncSession):
    user = await create_random_user(db)

    quiz = await form_quiz(length=3, tags=["math"], owner_id=user.id, session=db)

    assert len(quiz.exercises) == 0
    assert quiz.owner_id == user.id


@pytest.mark.xfail(raises=IntegrityError, reason="Owner expected to exist.")
async def test_form_quiz_owner_not_exists_still_works(db: AsyncSession):
    fake_owner_id = uuid7str()
    tags = ["algebra"]

    for _ in range(3):
        await create_random_exercise(db, tags=tags)

    quiz = await form_quiz(length=2, tags=tags, owner_id=fake_owner_id, session=db)

    assert quiz.owner_id == fake_owner_id
    assert len(quiz.exercises) == 2


async def test_deactivate_quizzes(db: AsyncSession):
    """Tests the deactivate_quizzes function. Only 1 active quiz can exist in db so testing with one."""

    user = await create_random_user(db)

    # Create active quizzes
    active_quiz1 = Quiz(owner_id=user.id, status=QuizStatusChoices.ACTIVE.value)
    db.add(active_quiz1)

    # Create inactive quiz
    inactive_quiz = Quiz(owner_id=user.id, status=QuizStatusChoices.IN_PROGRESS.value)
    db.add(inactive_quiz)

    await db.flush()

    # Deactivate quizzes
    await deactivate_quizzes(owner_id=user.id, session=db)

    # Refresh quizzes from the database
    await db.refresh(active_quiz1)
    await db.refresh(inactive_quiz)

    assert active_quiz1.status == QuizStatusChoices.IN_PROGRESS.value
    assert (
        inactive_quiz.status == QuizStatusChoices.IN_PROGRESS.value
    )  # Should remain unchanged


async def test_get_quiz_by_id(db: AsyncSession):
    """Tests the get_quiz_by_id function."""

    user = await create_random_user(db)

    exercise1 = await create_random_exercise(db)
    exercise2 = await create_random_exercise(db)

    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
        exercises=[exercise1, exercise2],
    )
    db.add(quiz)
    await db.flush()

    fetched_quiz = await get_quiz_by_id(quiz_id=quiz.id, session=db)

    assert fetched_quiz is not None
    assert fetched_quiz.id == quiz.id
    assert fetched_quiz.owner_id == user.id
    assert len(fetched_quiz.exercises) == 2
    fetched_exercise_ids = {ex.exercise.id for ex in fetched_quiz.exercises}
    assert exercise1.id in fetched_exercise_ids
    assert exercise2.id in fetched_exercise_ids


async def test_get_quiz_by_id_not_found(db: AsyncSession):
    """Tests the get_quiz_by_id function when quiz is not found."""

    non_existent_quiz_id = uuid7str()

    fetched_quiz = await get_quiz_by_id(quiz_id=non_existent_quiz_id, session=db)

    assert fetched_quiz is None


async def test_get_all_quizzes_by_owner(db: AsyncSession):
    """Tests the get_all_quizzes_by_owner function."""

    user = await create_random_user(db)

    # Create quizzes for the user
    for i in range(3):
        exercise = await create_random_exercise(db)
        quiz = Quiz(
            owner_id=user.id,
            status=QuizStatusChoices.NEW.value,
            exercises=[exercise],
            title=f"Quiz {i + 1}",
        )
        db.add(quiz)

    # Create a quiz for another user
    other_user = await create_random_user(db)
    other_quiz = Quiz(
        owner_id=other_user.id,
        status=QuizStatusChoices.NEW.value,
        title="Other User Quiz",
    )
    db.add(other_quiz)

    await db.flush()

    quizzes = await get_all_quizzes_by_owner(owner_id=user.id, session=db)

    assert len(quizzes) == 3
    for quiz in quizzes:
        assert quiz.owner_id == user.id
        assert other_quiz.id != quiz.id
        assert quiz.title in [f"Quiz {i + 1}" for i in range(3)]
        assert len(quiz.exercises) == 1
        exercise_ids = [ex.exercise.id for ex in quiz.exercises]
        assert exercise_ids[0] is not None
        assert quiz.exercises[0].position == 0


async def test_create_quiz(db: AsyncSession):
    """Tests the create_quiz function."""

    user = await create_random_user(db)

    exercise1 = await create_random_exercise(db)
    exercise2 = await create_random_exercise(db)

    quiz_in = QuizCreate(
        title="New Quiz",
        exercise_positions=[
            QuizExerciseData(exercise=exercise1, position=1),
            QuizExerciseData(exercise=exercise2, position=2),
        ],
    )

    await create_quiz(quiz_in, db, user.id)

    quiz_statement = (
        select(Quiz)
        .where(Quiz.owner_id == user.id, Quiz.title == "New Quiz")
        .options(selectinload(Quiz.quiz_exercises).selectinload(QuizExercise.exercise))
    )
    quiz = (await db.exec(quiz_statement)).first()

    assert quiz.id is not None
    assert quiz.owner_id == user.id
    assert quiz.title == "New Quiz"
    assert len(quiz.exercises) == 2
    positions = {qe.position for qe in quiz.quiz_exercises}
    assert positions == {1, 2}


async def test_create_quiz_raises_on_duplicate_exercise(db: AsyncSession):
    user = await create_random_user(db)
    exercise = await create_random_exercise(db)

    quiz_in = QuizCreate(
        exercise_positions=[
            QuizExerciseData(exercise=exercise, position=0),
            QuizExerciseData(exercise=exercise, position=1),
        ]
    )

    with pytest.raises(ValueError, match="Duplicate exercise ID in quiz"):
        await create_quiz(quiz_in, db, user.id)


async def test_create_quiz_raises_on_missing_exercise(db: AsyncSession):
    user = await create_random_user(db)
    real_ex = await create_random_exercise(db)

    fake_ex = Exercise(id="nonexistent", question="fake", solution="fake", tags=[])
    quiz_in = QuizCreate(
        exercise_positions=[
            QuizExerciseData(exercise=real_ex, position=0),
            QuizExerciseData(exercise=fake_ex, position=1),
        ]
    )

    with pytest.raises(ValueError, match="Exercises not found in DB"):
        await create_quiz(quiz_in, db, user.id)


async def test_update_quiz(db: AsyncSession):
    """Tests the update_quiz function."""

    user = await create_random_user(db)

    exercise1 = await create_random_exercise(db)
    exercise2 = await create_random_exercise(db)

    quiz = Quiz(
        owner_id=user.id,
        title="Original Quiz",
        exercises=[exercise1],
    )
    db.add(quiz)
    await db.flush()

    quiz_update = QuizUpdate(
        title="Updated Quiz",
        exercise_positions=[
            QuizExerciseData(exercise=exercise1, position=0),
            QuizExerciseData(exercise=exercise2, position=1),
        ],
    )

    updated_quiz = await update_quiz(quiz_id=quiz.id, quiz_in=quiz_update, session=db)

    assert updated_quiz.title == "Updated Quiz"
    assert len(updated_quiz.exercises) == 2
    assert updated_quiz.exercises[1].exercise.id == exercise2.id
    assert updated_quiz.exercises[1].position == 1


async def test_update_quiz_exercises_replaced(db: AsyncSession):
    """Tests that updating a quiz replaces its exercises correctly."""

    user = await create_random_user(db)

    exercise1 = await create_random_exercise(db)
    exercise2 = await create_random_exercise(db)
    exercise3 = await create_random_exercise(db)

    quiz = Quiz(
        owner_id=user.id,
        title="Quiz to Update",
        exercises=[exercise1, exercise2],
    )
    db.add(quiz)
    await db.flush()

    quiz_update = QuizUpdate(
        exercise_positions=[
            QuizExerciseData(exercise=exercise3, position=0),
        ],
    )

    updated_quiz = await update_quiz(quiz_id=quiz.id, quiz_in=quiz_update, session=db)

    assert len(updated_quiz.exercises) == 1
    assert updated_quiz.exercises[0].exercise.id == exercise3.id
    assert updated_quiz.exercises[0].position == 0


async def test_update_quiz_title_only_keeps_exercises(db: AsyncSession):
    user = await create_random_user(db)
    ex1 = await create_random_exercise(db)

    quiz = Quiz(owner_id=user.id, title="Old", exercises=[ex1])
    db.add(quiz)
    await db.flush()

    quiz_update = QuizUpdate(title="New Title")  # No exercise_positions
    updated = await update_quiz(quiz_id=quiz.id, quiz_in=quiz_update, session=db)

    assert updated.title == "New Title"
    assert len(updated.exercises) == 1
    assert updated.exercises[0].exercise.id == ex1.id


async def test_update_quiz_exercises_only_keeps_title(db: AsyncSession):
    user = await create_random_user(db)
    ex1 = await create_random_exercise(db)
    ex2 = await create_random_exercise(db)

    quiz = Quiz(owner_id=user.id, title="Keep Me", exercises=[ex1])
    db.add(quiz)
    await db.flush()

    quiz_update = QuizUpdate(
        exercise_positions=[QuizExerciseData(exercise=ex2, position=0)]
    )
    updated = await update_quiz(quiz_id=quiz.id, quiz_in=quiz_update, session=db)

    assert updated.title == "Keep Me"
    assert len(updated.exercises) == 1
    assert updated.exercises[0].exercise.id == ex2.id


async def test_update_quiz_with_exercise_positions_none_does_not_keep_exercises(
    db: AsyncSession,
):
    user = await create_random_user(db)
    ex = await create_random_exercise(db)

    quiz = Quiz(owner_id=user.id, exercises=[ex])
    db.add(quiz)
    await db.flush()

    quiz_update = QuizUpdate(title="New", exercise_positions=None)
    updated = await update_quiz(quiz_id=quiz.id, quiz_in=quiz_update, session=db)

    assert len(updated.exercises) == 0


async def test_start_new_quiz(db: AsyncSession):
    user = await create_random_user(db)
    exercise1 = await create_random_exercise(db)
    exercise2 = await create_random_exercise(db)
    exercise1.tags.append("tag1")
    exercise2.tags.append("tag1")

    quiz_data = StartQuizRequest(length=3, tags=["tag1"], title="Started Quiz")

    quiz = await start_new_quiz(quiz_data=quiz_data, owner_id=user.id, session=db)

    assert quiz.owner_id == user.id
    assert quiz.title == "Started Quiz"
    assert len(quiz.exercises) <= 2  # Only 2 exercises with tag1 exist
    for ex in quiz.exercises:
        assert "tag1" in ex.exercise.tags
        assert not hasattr(ex.exercise, "solution")
    assert quiz.status == QuizStatusChoices.ACTIVE.value


async def test_start_new_quiz_length_zero(db: AsyncSession):
    user = await create_random_user(db)
    quiz_data = StartQuizRequest(length=0, tags=["math"])

    quiz = await start_new_quiz(quiz_data=quiz_data, owner_id=user.id, session=db)

    assert quiz.owner_id == user.id
    assert len(quiz.exercises) == 0
    assert quiz.status == QuizStatusChoices.ACTIVE.value


async def test_start_new_quiz_no_matching_tags(db: AsyncSession):
    user = await create_random_user(db)
    await create_random_exercise(db, tags=["physics"])

    quiz_data = StartQuizRequest(length=5, tags=["chemistry"])

    quiz = await start_new_quiz(quiz_data=quiz_data, owner_id=user.id, session=db)

    assert len(quiz.exercises) == 0
    assert quiz.status == QuizStatusChoices.ACTIVE.value
    assert quiz.title is None


@patch("app.core.quiz.deactivate_quizzes", new_callable=AsyncMock)
async def test_start_new_quiz_calls_deactivate(mock_deactivate, db: AsyncSession):
    user = await create_random_user(db)
    ex = await create_random_exercise(db, tags=["math"])
    quiz_data = StartQuizRequest(length=1, tags=["math"])

    await start_new_quiz(quiz_data=quiz_data, owner_id=user.id, session=db)

    mock_deactivate.assert_called_once_with(owner_id=user.id, session=db)


async def test_save_quiz_progress(db: AsyncSession):
    user = await create_random_user(db)
    exercise = await create_random_exercise(db)

    quiz = Quiz(
        owner_id=user.id, status=QuizStatusChoices.ACTIVE.value, exercises=[exercise]
    )
    db.add(quiz)
    await db.flush()

    answer = SubmitAnswer(
        response=[
            {
                "exercise_id": exercise.id,
                "answer": exercise.solution,
            }
        ]
    )
    await save_quiz_progress(quiz=quiz, answers=answer, session=db)

    updated_quiz = (
        await db.exec(
            select(Quiz, QuizExercise).where(
                Quiz.id == quiz.id, QuizExercise.quiz_id == quiz.id
            )
        )
    ).first()
    assert updated_quiz[0].status == QuizStatusChoices.ACTIVE.value
    assert updated_quiz[1].is_correct == True


async def test_save_quiz_progress_handles_none_answer_gracefully(db: AsyncSession):
    user = await create_random_user(db)
    ex = await create_random_exercise(db)
    quiz = Quiz(owner_id=user.id, status="active", exercises=[ex])
    db.add(quiz)
    await db.flush()

    answer = SubmitAnswer(response=[{"exercise_id": ex.id, "answer": None}])

    await save_quiz_progress(session=db, quiz=quiz, answers=answer)

    link = (
        await db.exec(select(QuizExercise).where(QuizExercise.exercise_id == ex.id))
    ).one()
    # None → "" → not equal to "42"
    assert link.is_correct is False


async def test_save_quiz_progress_last_answer_wins(db: AsyncSession):
    user = await create_random_user(db)
    ex = await create_random_exercise(db)
    quiz = Quiz(owner_id=user.id, status="active", exercises=[ex])
    db.add(quiz)
    await db.flush()

    answer = SubmitAnswer(
        response=[
            {"exercise_id": ex.id, "answer": "0"},
            {"exercise_id": ex.id, "answer": ex.solution},
        ]
    )

    await save_quiz_progress(session=db, quiz=quiz, answers=answer)

    link = (
        await db.exec(select(QuizExercise).where(QuizExercise.exercise_id == ex.id))
    ).one()
    assert link.is_correct is True


async def test_load_active_quiz(db: AsyncSession):
    user = await create_random_user(db)

    ex_list = []
    for _ in range(5):
        ex = await create_random_exercise(db)
        ex_list.append(ex)

    quiz = Quiz(
        owner_id=user.id, status=QuizStatusChoices.ACTIVE.value, exercises=ex_list
    )
    db.add(quiz)
    await db.flush()

    active_quiz = await load_active_quiz(owner_id=user.id, session=db)

    assert active_quiz is not None
    assert active_quiz.status == QuizStatusChoices.ACTIVE.value
    if active_quiz:
        for ex in active_quiz.exercises:
            assert ex.exercise.id in [exercise.id for exercise in ex_list]


async def test_load_active_quiz_returns_none_for_in_progress_quiz(db: AsyncSession):
    user = await create_random_user(db)
    quiz = Quiz(owner_id=user.id, status=QuizStatusChoices.IN_PROGRESS.value)
    db.add(quiz)
    await db.flush()

    active = await load_active_quiz(session=db, owner_id=user.id)
    assert active is None


async def test_load_active_quiz_returns_empty_exercises_when_quiz_has_no_exercises(
    db: AsyncSession,
):
    user = await create_random_user(db)

    quiz = Quiz(owner_id=user.id, status=QuizStatusChoices.ACTIVE.value)
    db.add(quiz)
    await db.flush()

    result = await load_active_quiz(session=db, owner_id=user.id)

    assert result is not None
    assert result.id == quiz.id
    assert result.exercises == []


async def test_load_active_quiz_excludes_deleted_exercises_gracefully(db: AsyncSession):
    user = await create_random_user(db)
    ex = await create_random_exercise(db)

    # Create active quiz
    quiz = Quiz(
        owner_id=user.id,
        status=QuizStatusChoices.ACTIVE.value,
    )
    db.add(quiz)
    await db.flush()

    qe = QuizExercise(quiz_id=quiz.id, exercise_id=ex.id, position=0)
    db.add(qe)
    await db.flush()

    # Confirm quiz loads exercise
    result = await load_active_quiz(session=db, owner_id=user.id)
    assert len(result.exercises) == 1
    assert result.exercises[0].exercise.id == ex.id

    # Now delete the exercise
    await db.delete(ex)
    await db.flush()
    await db.refresh(quiz, attribute_names=["quiz_exercises"])

    # Reload quiz
    result = await load_active_quiz(session=db, owner_id=user.id)

    count = (
        await db.exec(select(func.count()).where(QuizExercise.exercise_id == ex.id))
    ).one()
    assert count == 0

    # The link should be gone due to CASCADE
    assert len(result.exercises) == 0


async def test_submit_quiz(db: AsyncSession):
    user = await create_random_user(db)
    ex = await create_random_exercise(db)
    quiz = Quiz(owner_id=user.id, status=QuizStatusChoices.ACTIVE.value, exercises=[ex])
    db.add(quiz)
    await db.flush()
    await db.refresh(quiz)
    answers = SubmitAnswer(response=[{"exercise_id": ex.id, "answer": ex.solution}])

    await submit_quiz(session=db, quiz=quiz, answers=answers)

    statement = select(Quiz).where(Quiz.id == quiz.id)
    submitted_quiz = (await db.exec(statement)).one()
    assert submitted_quiz is not None
    assert submitted_quiz.status == QuizStatusChoices.SUBMITTED.value
    assert submitted_quiz.quiz_exercises[0].is_correct is True


async def test_submit_quiz_empty_answers(db: AsyncSession):
    user = await create_random_user(db)
    ex = await create_random_exercise(db)

    quiz = Quiz(owner_id=user.id, exercises=[ex])
    db.add(quiz)
    await db.flush()

    answers = SubmitAnswer(response=[])

    await submit_quiz(session=db, quiz=quiz, answers=answers)

    await db.refresh(quiz)
    assert quiz.status == QuizStatusChoices.SUBMITTED.value

    link = (
        await db.exec(select(QuizExercise).where(QuizExercise.quiz_id == quiz.id))
    ).one()
    assert link.is_correct is None

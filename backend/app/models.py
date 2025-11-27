from uuid_extensions import uuid7str
from enum import Enum

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, String, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB


# Shared properties
class UserBase(SQLModel):
    """Base model for user entities containing common attributes.

    Attributes:
        email: Unique email address with maximum length 255 characters.
        is_active: Boolean indicating user account status.
        is_superuser: Boolean indicating administrative privileges.
        full_name: Optional full name of the user with maximum length 255.
    """

    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    """Model for user creation via API endpoints. Inherits from UserBase.

    Attributes:
        email: Unique email address with maximum length 255 characters.
        is_active: Boolean indicating user account status.
        is_superuser: Boolean indicating administrative privileges.
        full_name: Optional full name of the user with maximum length 255.
        password: Required password with validation constraints.
    """

    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    """Model for user registration requests.

    Attributes:
        email: Unique email address with maximum length 255 characters.
        password: Required password with validation constraints.
        full_name: Optional full name of the user with maximum length 255.
    """

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    """Model for user updates via API endpoints. Inherits from UserBase.

    Attributes:
        email: Optional, unique email address with maximum length 255 characters.
        password: Optional password with validation constraints.
    """

    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    """Model for self-updating user profile information.

    Attributes:
        full_name: Optional full name of the user with maximum length 255.
        email: Optional email address with maximum length 255.
    """

    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    """Model for password update requests.

    Attributes:
        current_password: Required current password.
        new_password: Required new password.
    """

    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    """Database representation of a user entity. Inherits from UserBase.

    Attributes:
        id: Unique identifier for the user.
        hashed_password: Hashed password for secure storage.
        items: List of items associated with the user.
        quizzes: List of quizzes associated with the user.
    """

    __tablename__ = "user"
    id: str = Field(default_factory=uuid7str, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(
        back_populates="owner",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    quizzes: list["Quiz"] = Relationship(
        back_populates="owner",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    """Public user data model for API responses. Inherits from UserBase.

    Attributes:
        id: Unique identifier for the user.
    """

    id: str


class UsersPublic(SQLModel):
    """Public model for user list responses.

    Attributes:
        data: List of UserPublic objects.
        count: Total number of users.
    """

    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    """Base model for items.

    Attributes:
        title: Required title with maximum length 255.
        description: Optional description with maximum length 255.
    """

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    """Model for item creation via API endpoints. Inherits from ItemBase."""

    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    """Model for item updates via API endpoints. Inherits from ItemBase.

    Attributes:
        title: Optional title with maximum length 255.
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    """Database representation of an item entity. Inherits from ItemBase.

    Attributes:
        id: Unique identifier for the item.
        owner_id: Foreign key to the owner's user ID.
        owner: Optional relationship to the owner's user.
    """

    __tablename__ = "item"
    id: str = Field(default_factory=uuid7str, primary_key=True)
    owner_id: str = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: User | None = Relationship(
        back_populates="items", sa_relationship_kwargs={"lazy": "selectin"}
    )


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    """Public representation of an item for API responses. Inherits from ItemBase.

    Attributes:
        id: Unique identifier for the item.
        owner_id: Foreign key to the owner's user ID.
    """

    id: str
    owner_id: str


class ItemsPublic(SQLModel):
    """Public representation of a list of items for API responses.

    Attributes:
        data: List of ItemPublic objects.
        count: Total number of items.
    """

    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    """Model for messages.

    Attributes:
        message: Required message string.
    """

    message: str


# JSON payload containing access token
class Token(SQLModel):
    """Access token model.

    Attributes:
        access_token: Required access token string.
        token_type: Optional token type string, defaults to 'bearer'.
    """

    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    """JWT token payload validation model.

    Attributes:
        sub: Optional User identifier.
    """

    sub: str | None = None


class NewPassword(SQLModel):
    """Validation model for a new password.

    Attributes:
        token: Authentication token.
        new_password: New password.
    """

    token: str
    new_password: str = Field(min_length=8, max_length=40)


class QuizExercise(SQLModel, table=True):
    """Model for M2M link between quizzes and exercises.

    Attributes:
        quiz_id: Foreign key to the quiz ID.
        quiz: Relationship to the quiz.
        exercise_id: Foreign key to the exercise ID.
        exercise: Relationship to the exercise.
        position: Position of the exercise in the quiz.
        is_correct: Optional boolean indicating if the exercise was answered correctly. None if not attempted.
    """

    __tablename__ = "quizexercise"
    quiz_id: str = Field(
        foreign_key="quiz.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    exercise_id: str = Field(
        foreign_key="exercise.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    quiz: "Quiz" = Relationship(back_populates="quiz_exercises")
    exercise: "Exercise" = Relationship(back_populates="quiz_exercises")
    position: int = 0
    is_correct: bool | None = None


class ExerciseBase(SQLModel):
    """Base model for an exercise.

    Attributes:
        source_name: Source of an excercise.
        source_id: id of an exercise in a given source.
        text: Text of an exercise.
        answers: list of all answers to the exercise to put in a quiz
        formula: formula for the exercise, if given
        illustration: illustration for the exercise, if given
    """

    source_name: str = Field(max_length=255)
    source_id: str = Field(max_length=255)
    text: str
    answers: list[str] = Field(default_factory=list)
    illustration: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ExerciseCreate(ExerciseBase):
    """Model for creating a new exercise.

    Attributes:
        solution: Required correct answer to the exercise
    """

    solution: str


class ExerciseUpdate(ExerciseBase):
    """Model for updating an existing exercise via API endpoint.

    Attributes:
        source_name: Optional. Source of an excercise.
        source_id: Optional. ID of an exercise in a given source.
        text: Optional. Text of an exercise.
        solution: Optional. Correct answer to the exercise
        formula: Optional. Formula for the exercise, if given
        illustration: Optional. Illustration for the exercise, if given
        tags: Optional. List of Tag objects, representing tags for the exercise
    """

    source_name: str | None = Field(default=None, max_length=255)
    source_id: str | None = Field(default=None, max_length=255)
    text: str | None = None
    solution: str | None = None
    illustration: list[str] | None = None
    tags: list[str] | None = None


class Exercise(ExerciseBase, table=True):
    """Database model for an exercise. Inherits from ExerciseBase.

    Attributes:
        id: Unique identifier for the exercise.
        answers: list of answers for the exercise
        illustration: list of illustrations for the exercise
        tags: list of tag strings representing tags for the exercise
        quizzes: list of Quiz objects representing quizzes that include the exercise
        quiz_exercises: list of QuizExercise objects representing exercises in quizzes for quick access to position and grading
        solution: correct answer to the exercise
        text: text of the exercise
    """

    __tablename__ = "exercise"
    id: str = Field(default_factory=uuid7str, primary_key=True)
    answers: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    illustration: list[str] | None = Field(
        default_factory=list, sa_column=Column(JSONB)
    )
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    quizzes: list["Quiz"] = Relationship(
        back_populates="exercises",
        link_model=QuizExercise,
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete",  # ORM cascade
            "passive_deletes": True,  # Trust DB to handle deletes
            "overlaps": "quiz",
        },
    )
    quiz_exercises: list["QuizExercise"] = Relationship(
        back_populates="exercise",
        sa_relationship_kwargs={
            "cascade": "all, delete",
            "passive_deletes": True,
            "overlaps": "quizzes",
        },
    )
    solution: str


class ExercisePublic(ExerciseBase):
    """Public representation of Exercise for API responses. Inherits from ExerciseBase.

    Attributes:
        id: Unique identifier for the exercise.
        illustration: list of illustrations for the exercise
        answers: list of answers for the exercise
        tags: list of strings representing tags for the exercise
        source_name: Source of an excercise.
        source_id: id of an exercise in a given source.
        text: Text of an exercise.
    """

    id: str
    illustration: list[str] = []
    answers: list[str] = []
    tags: list[str] = []


class ExercisesPublic(SQLModel):
    """Public representation for a list of Exercises.

    Attributes:
        data: list of ExercisePublic objects
        count: total number of exercises
    """

    data: list[ExercisePublic]
    count: int


class QuizStatusChoices(str, Enum):
    """Enum for quiz status choices. Only one active quiz per user can exist at a time, db enforced."""

    NEW: str = "new"  # freshly created, not started yet
    IN_PROGRESS: str = "in_progress"  # started but not completed
    ACTIVE: str = "active"  # last attempt is active
    SUBMITTED: str = "submitted"  # completed but not graded yet
    GRADED: str = "graded"  # graded and finished


class QuizBase(SQLModel):
    """Base model for a quiz.

    Attributes:
        status: new/in_progress/active/submitted/graded, new is default
        title: title of the quiz, optional.
    """

    status: QuizStatusChoices = QuizStatusChoices.NEW.value
    title: str | None = Field(default=None, max_length=255)


class QuizCreate(QuizBase):
    """Model for creating a new quiz via API endpoints.

    Attributes:
        exercise_positions: list of QuizExerciseData representing exercises and their positions.
    """

    exercise_positions: list[QuizExerciseData] = Field(default_factory=list)


class QuizUpdate(QuizBase):
    """Model for updating a quiz via API endpoints. Inherits from QuizBase.

    Atributes:
        status: Optional, status of the quiz.
        title: Optional, title of the quiz.
        exercise_positions: Optional list of QuizExerciseData representing exercises and their positions.
    """

    status: QuizStatusChoices | None = None
    title: str | None = Field(default=None, max_length=255)
    exercise_positions: list[QuizExerciseData] | None = None


class Quiz(QuizBase, table=True):
    """Database model for a Quiz. Inherits from QuizBase.

    Attributes:
        id: Unique identifier for the quiz.
        owner_id: Unique identifier for the user who created the quiz.
        owner: User object representing the owner of the quiz
        exercises: list of Exercise objects representing exercises included in the quiz
        status: status of the quiz - new/active/submitted/graded.
        quiz_exercises: list of QuizExercise objects for quick access to positions and scores.
    """

    __tablename__ = "quiz"
    id: str = Field(default_factory=uuid7str, primary_key=True)
    owner_id: str = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: User | None = Relationship(back_populates="quizzes")
    exercises: list["Exercise"] = Relationship(
        back_populates="quizzes",
        link_model=QuizExercise,
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete",
            "passive_deletes": True,
            "overlaps": "exercise,quiz_exercises",
        },
    )
    status: str = Field(
        default=QuizStatusChoices.NEW.value,
        sa_column=Column(
            "status",
            String,
            CheckConstraint(
                "status IN ('new', 'in_progress', 'active', 'submitted', 'graded')",
                name="valid_quiz_status",
            ),
            nullable=False,
        ),
    )
    quiz_exercises: list["QuizExercise"] = Relationship(
        back_populates="quiz",
        sa_relationship_kwargs={"lazy": "selectin", "overlaps": "exercises,quizzes"},
    )


class QuizExerciseData(SQLModel):
    """Model representing an exercise within a quiz along with its position.

    Attributes:
        exercise: Exercise object.
        position: Position of the exercise in the quiz.
    """

    exercise: Exercise
    position: int


class QuizExerciseDataPublic(SQLModel):
    """Model representing an exercise within a quiz along with its position.

    Attributes:
        exercise: ExercisePublic object representing the exercise.
        position: Position of the exercise in the quiz.
    """

    exercise: ExercisePublic
    position: int


class QuizPublic(QuizBase):
    """Public representation of a Quiz. Inherits for QuizBase.

    Attributes:
        id: Unique identifier for the quiz.
        owner_id: Unique identifier for the user who created the quiz.
        exercises: list of Exercise objects representing exercises included in the quiz
        status: status of the quiz - new/active/submitted/graded.
    """

    id: str
    owner_id: str
    exercises: list[
        QuizExerciseDataPublic
    ]  # list of {"exercise": ExercisePublic, "position": int}
    status: str


class QuizzesPublic(SQLModel):
    """Public representation for a list of Quizzes.

    Attributes:
        data: list of QuizPublic objects
        count: total number of quizzes
    """

    data: list[QuizPublic]
    count: int


class SubmitAnswer(SQLModel):
    """Model for submitting answers to the quiz.

    Attributes:
        response: list of dicts with exercise_id and answer.
    """

    response: list[dict[str, str | None]]  # [{"exercise_id": str, "answer": str}, ...]


class StartQuizRequest(SQLModel):
    """Model with data for starting a new quiz.

    Attributes:
        tags: List of tags to filter exercises.
        length: Number of exercises in the quiz.
        title: Optional title for the quiz.
    """

    tags: list[str] | None = Field(default_factory=list)
    length: int = Field(default=5, le=500)
    title: str | None = Field(default=None, max_length=255)

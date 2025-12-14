
from uuid_extensions import uuid7str
from enum import Enum
from datetime import datetime, timezone
from typing import Any


from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel, select
from sqlalchemy import Column, String, CheckConstraint
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
from sqlmodel.ext.asyncio.session import AsyncSession




# Join table: Course <-> User (enrollments)
class CourseEnrollment(SQLModel, table=True):
    __tablename__ = "courseenrollment"
    course_id: str = Field(foreign_key="course.id", primary_key=True)
    user_id: str = Field(foreign_key="user.id", primary_key=True)

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
    modules: list["UserModuleProgress"] = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    enrolled_courses:list["Course"]=Relationship(
        back_populates="attendants",
        link_model=CourseEnrollment,
        sa_relationship_kwargs={"lazy":"selectin"},
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
    module_id: str|None = Field(default=None, foreign_key="module.id")
    module: "Module" =Relationship(back_populates="quizzes")


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


class CourseBase(SQLModel):
    """Base model for courses.
    
    Attributes:
        title: Title of the course.
        description: Optional description of the course.
    """
    title: str
    description: str|None = None


class CourseCreate(CourseBase):
    """Model for creating a new course.
    
    Attributes:
        description: Optional description of the course.
        title: Title of the course.
    """
    modules:list["ModuleCreate"] = Field(default_factory=list)


class CourseUpdate(CourseBase):
    """Model for updating an existing course.
    
    Attributes:
        title: Title of the course, optional.
        description: Description of the course, optional.
        attendants: list of user ids enrolled in the course.
        modules: list of module ids in the course.
    """
    title: str | None = None
    description: str | None = None



class Course(CourseBase, table=True):
    """Database model for a Course. Inherits from CourseBase.
    
    Attributes:
        id: Unique identifier for the course.
        author_id: Unique identifier for the user who created the course.
        author: Relationship to the user who created the course.
        modules: Relationship to the modules in the course.
        title: Title of the course.
        description: Optional description of the course.
        attendants: list of users enrolled in the course.
    """
    __tablename__ = "course"
    id: str = Field(default_factory=uuid7str, primary_key=True)
    author_id: str = Field(foreign_key="user.id")
    author: User = Relationship(
        sa_relationship_kwargs=({
            "lazy": "selectin",
            "foreign_keys": "Course.author_id"
            }),
    )
    modules: list["Module"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "order_by": "Module.order",},
    )
    attendants:list["User"]=Relationship(
        back_populates="enrolled_courses",
        link_model=CourseEnrollment,
        sa_relationship_kwargs={"lazy":"selectin"},
    )



class CoursePublic(CourseBase):
    """Public representation of a Course. Inherits from CourseBase.

    Attributes:
        id: Unique identifier for the course.
        author_id: Unique identifier for the user who created the course.
        title: Title of the course.
        description: Optional description of the course.
        module_ids: list of Module ids representing modules in the course
        attendant_ids: list of User ids representing users enrolled in the course
    """
    id: str
    author_id: str
    module_ids:list[str]=Field(default_factory=list)
    attendant_ids:list[str]=Field(default_factory=list)

    @staticmethod
    def from_db(course:Course) -> "CoursePublic":
        """Create a CoursePublic instance from a Course database model.

        Args:
            course (Course): The Course database model instance.
        Returns:
            CoursePublic: The corresponding CoursePublic instance.
        """
        return CoursePublic(
            id=course.id,
            author_id=course.author_id,
            title=course.title,
            description=course.description,
            module_ids=[module.id for module in course.modules],
            attendant_ids=[user.id for user in course.attendants],
        )


class CoursesPublic(SQLModel):
    """Public representation for a list of Courses.

    Attributes:
        data: List of CoursePublic objects.
        count: Total number of courses.
    """
    data: list[CoursePublic]
    count: int




class ModuleBase(SQLModel):
    """Base model for modules.
    
    Attributes:
        title: Title of the module.
        content: Content of the module.
        order: Position of the module in the course.
        is_draft: Flag indicating if the module is a draft.
    """
    title: str
    content: str
    order: int
    is_draft: bool = True


class ModuleCreate(ModuleBase):
    """Model for creating a new module."""
    attachments:list[str]|None = None
    quizzes:list[str]|None = None
    course_id:str|None = None


class ModuleUpdate(ModuleBase):
    """Model for updating an existing module.
    
    Attributes:
        title: Optional, title of the module.
        content: Optional, content of the module.
        order: Optional, position of the module in the course.
        is_draft: Optional, flag indicating if the module is a draft.
    """
    title:str|None = None
    content:str|None = None
    order:int|None = None
    is_draft:bool|None = None
    attachments:list[str]|None = None
    quizzes:list[str]|None = None


class Module(ModuleBase, table=True):
    """Database model for a Module. Inherits from ModuleBase.
    
    Attributes:
        id: Unique identifier for the module.
        course_id: Unique identifier for the course.
        course: Relationship to the course.
        title: Title of the module.
        content: Content of the module.
        order: Position of the module in the course.
        released_at: Date and time when the module will be available.
        is_draft: Flag indicating if the module is a draft.
        attachments: Relationship to the attachments in the module.
        progress: Relationship to the progress of the module for users.
    """
    __table_args__ = (UniqueConstraint("course_id", "order",name="unique_module_order_per_course"),)
    __tablename__ = "module"
    id: str = Field(default_factory=uuid7str, primary_key=True)
    released_at: datetime|None = None
    author_id: str = Field(foreign_key="user.id", nullable=False)
    author: User = Relationship(sa_relationship_kwargs=({"lazy":"selectin","foreign_keys":"Module.author_id"}),)
    course_id: str = Field(foreign_key="course.id", nullable=False, ondelete="CASCADE")
    course: Course = Relationship(
        back_populates="modules", 
        sa_relationship_kwargs={"lazy":"selectin"},
        )
    attachments: list["Attachment"] = Relationship(back_populates="module")
    quizzes: list["Quiz"] = Relationship(
        back_populates="module",
        sa_relationship_kwargs={"lazy":"selectin"},
        )
    progress: list["UserModuleProgress"] = Relationship(back_populates="module")


class ModulePublic(ModuleBase):
    """Public representation of a Module. Inherits from ModuleBase.

    Attributes:
        id: Unique identifier for the module.
        course_id: Unique identifier for the course.
        attachments: List of Attachment ids representing attachments in the module.
        title: Title of the module.
        content: Content of the module.
        order: Position of the module in the course.
        is_draft: Flag indicating if the module is a draft.
        quizzes: List of Quiz ids representing quizzes in the module.
    """
    id: str
    course_id: str
    attachments: list[str] = Field(default_factory=list) #list of attachment ids
    quizzes:list[str]=Field(default_factory=list)

    @staticmethod
    async def from_db(db:AsyncSession, module:Module) -> "ModulePublic":
        """Create a ModulePublic instance from a Module database model.

        Args:
            module (Module): The Module database model instance.
        Returns:
            ModulePublic: The corresponding ModulePublic instance.
        """
        statement = (
        select(Module)
        .where(Module.id == module.id)
        .options(
            selectinload(Module.course),         # ← This loads course
            selectinload(Module.attachments),    # ← This loads attachments
            selectinload(Module.quizzes),        # ← This loads quizzes
        )
    )
        module = (await db.exec(statement)).first()
        return ModulePublic(
            id=module.id,
            course_id=module.course.id,
            title=module.title,
            content=module.content,
            order=module.order,
            is_draft=module.is_draft,
            attachments=[attachment.id for attachment in module.attachments],
            quizzes=[quiz.id for quiz in module.quizzes],
        )


class ModulesPublic(SQLModel):
    """Public representation for a list of Modules.

    Attributes:
        data: List of ModulePublic objects.
        count: Total number of modules.
    """
    data: list[ModulePublic]
    count: int


class ModuleOrderItem(SQLModel):
    module_id: str
    order: int

class ReorderModulesRequest(SQLModel):
    modules: list[ModuleOrderItem]


class AttachmentBase(SQLModel):
    """Base model for attachments.
    
    Attributes:
        title: Title of the attachment.
        file_url: URL to the attachment file.
        type: Type of the attachment (e.g., 'file', 'presentation', 'video', 'quiz').
        order: Position of the attachment in the module.
    """
    title: str
    file_url: str
    type: str
    order: int = 0


class AttachmentCreate(AttachmentBase):
    """Model for creating new Attachment.
    
    Attributes:
        file_url: URL to the attachment file.
        module_id: Unique identifier for the module.
        title: Title of the attachment.
        type: Type of the attachment (e.g., 'file', 'presentation', 'video', 'quiz').
        order: Position of the attachment in the module.
    """
    module_id: str

class AttachmentUpdate(AttachmentBase):
    """Model for updating an existing Attachment.
    
    Attributes:
        title: Optional, title of the attachment.
        file_url: Optional, URL to the attachment file.
        type: Optional, type of the attachment.
        order: Optional, position of the attachment in the module.
        module_id: Optional, unique identifier for the module.
    """
    title: str | None = None
    file_url: str | None = None
    type: str | None = None
    order: int | None = None
    module_id: str | None = None

class Attachment(AttachmentBase, table=True):
    """Database model for an Attachment. Inherits from AttachmentBase.
    
    Attributes:
        id: Unique identifier for the attachment.
        module_id: Unique identifier for the module.
        module: Relationship to the module.
        title: Title of the attachment.
        file_url: URL to the attachment file.
        type: Type of the attachment (e.g., 'file', 'presentation', 'video', 'quiz').
        order: Position of the attachment in the module.
    """
    __table_args__ = (UniqueConstraint("module_id", "order", name="unique_attachment_order_per_module"),)
    __tablename__ = "attachment"
    id: str = Field(default_factory=uuid7str, primary_key=True)
    module_id: str = Field(foreign_key="module.id", nullable=True, ondelete="CASCADE")
    module: Module|None = Relationship(back_populates="attachments")


class AttachmentPublic(AttachmentBase):
    """Public representation of an Attachment. Inherits from AttachmentBase.
    
    Attributes:
        id: Unique identifier for the attachment.
        module_id: Unique identifier for the module.
        title: Title of the attachment.
        file_url: URL to the attachment file.
        type: Type of the attachment (e.g., 'file', 'presentation', 'video', 'quiz').
        order: Position of the attachment in the module.
    """
    id: str
    module_id: str

    @staticmethod
    def from_db(attachment:Attachment) -> "AttachmentPublic":
        """Create an AttachmentPublic instance from an Attachment database model.

        Args:
            attachment (Attachment): The Attachment database model instance.
        Returns:
            AttachmentPublic: The corresponding AttachmentPublic instance.
        """
        return AttachmentPublic(
            id=attachment.id,
            module_id=attachment.module.id if attachment.module else "",
            title=attachment.title,
            file_url=attachment.file_url,
            type=attachment.type,
            order=attachment.order,
        )

class AttachmentsPublic(SQLModel):
    """List of AttachmentPublic objects.
    
    Attributes:
        data: List of AttachmentPublic objects.
        count: Total number of attachments.
    """
    data: list[AttachmentPublic]
    count: int

class UserModuleProgress(SQLModel, table=True):
    """Link model for keeping users progress of modules.
    
    Attributes:
        id: Unique identifier for the progress record.
        user_id: Unique identifier for the user.
        module_id: Unique identifier for the module.
        started_at: Timestamp when the user started the module.
        last_accessed: Timestamp of the last access to the module.
        completed_at: Timestamp when the module was completed.
        is_completed: Flag indicating if the module is completed.
        user: Relationship to the user.
        module: Relationship to the module.
    """
    id: str = Field(default_factory=uuid7str, primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    module_id: str = Field(foreign_key="module.id")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime|None = None
    is_completed: bool = False

    user: User = Relationship(back_populates="modules")
    module: Module = Relationship(back_populates="progress")


# class ValidationErrorItem(SQLModel):
#     index: int | None = None
#     module_data: dict[str, Any] | None = None
#     error: str


# class CourseCreationResponse(CoursePublic):
#     warning: str | None = None
#     failed_modules: list[ValidationErrorItem] = []

#     @staticmethod
#     def from_db(course: Course) -> "CourseCreationResponse":
#         course_public = CoursePublic.from_db(course)
#         return CourseCreationResponse(
#             **course_public.model_dump(),
#             warning=None,
#             failed_modules=[],
#         )


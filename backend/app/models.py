import uuid
import json
from typing import List, Self, Optional

from pydantic import EmailStr, field_validator
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import JSON



# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


class ExerciseTag(SQLModel, table=True):
    exercise_id: uuid.UUID = Field(
        foreign_key="exercise.id", primary_key=True
    )
    tag_id: uuid.UUID = Field(
        foreign_key="tag.id", primary_key=True
    )
    #relationships
    exercise: "Exercise" = Relationship(back_populates="tags")
    tag: "Tag" = Relationship(back_populates="exercises")


class ExerciseBase(SQLModel):
    """
    Base model for an exercise.
    """
    source_name: str = Field(max_length=255)
    source_id: str = Field(max_length=255)
    text: str
    solution: str
    formula: str|None = None
    illustration: str|None = None
  

class Exercise(ExerciseBase, table=True):
    """
    Database model for an exercise.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tags: list["Tag"] = Relationship(back_populates="exercises", link_model=ExerciseTag)

class ExercisesPublic(SQLModel):
    data: list[Exercise]
    count: int


class TagBase(SQLModel):
    name: str = Field(unique=True, index=True, max_length=255)
    description: Optional[str] = None


class Tag(TagBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    exercises: List["Exercise"] = Relationship(back_populates="tags", link_model=ExerciseTag)




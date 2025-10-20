import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import select, func

from app.api.deps import CurrentUser, SessionDep
from app.models import Tag, TagCreate, TagUpdate, TagPublic, TagsPublic, Message


router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("/", response_model=TagsPublic)
def read_tags(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> TagsPublic:
    """
    Retrieve tags.
    """
    count_statement = select(func.count()).select_from(Tag)
    count = session.exec(count_statement).one()
    statement = select(Tag).offset(skip).limit(limit)
    tags = session.exec(statement).all()
    return TagsPublic(data=tags, count=count)

@router.get("/{id}", response_model=TagPublic)
def read_tag(session: SessionDep, id: uuid.UUID) -> TagPublic:
    """
    Get tag by ID.
    """
    tag = session.get(Tag, id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag

@router.post("/", response_model=TagPublic)
def create_tag(
    *, session: SessionDep, current_user: CurrentUser, tag_in: TagCreate
) -> TagPublic:
    """
    Create a new tag.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    tag = TagPublic.model_validate(tag_in)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag

@router.put("/{id}", response_model=TagPublic)
def update_tag(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID, tag_in: TagUpdate
) -> TagPublic:
    """
    Update an existing tag.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    tag = session.get(TagPublic, id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag_data = tag_in.model_dump(exclude_unset=True)
    tag.sqlmodel_update(tag_data)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag

@router.delete("/{id}")
def delete_tag(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a tag.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    tag = session.get(Tag, id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    session.delete(tag)
    session.commit()
    return Message(message="Tag deleted successfully")
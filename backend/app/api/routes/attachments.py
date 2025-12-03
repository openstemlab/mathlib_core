from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Attachment,
    AttachmentCreate,
    AttachmentPublic,
    AttachmentUpdate,
    AttachmentsPublic,
    Message,
    Module,
)
from app.utils import _get_objects_by_id


router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/", response_model=AttachmentsPublic)
async def read_attachments_route(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 10,
):
    """
    Retrieve a list of attachments with pagination.
    Accessible to all authenticated users.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="No permission.")

    statement = select(Attachment).offset(skip).limit(limit)
    attachments = (await session.exec(statement)).all()

    if not attachments:
        return {"data": [], "count": 0}

    data = [
        AttachmentPublic.model_validate(att) for att in attachments
    ]

    return AttachmentsPublic(data=data[skip : skip + limit], count=len(attachments))


@router.get("/{attachment_id}", response_model=AttachmentPublic)
async def read_attachment_route(
    session: SessionDep,
    current_user: CurrentUser,
    attachment_id: str,
):
    """
    Retrieve a single attachment by ID.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="No permission.")

    attachment = await session.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    return AttachmentPublic.model_validate(attachment)


@router.post("/", response_model=AttachmentPublic)
async def create_attachment_route(
    session: SessionDep,
    current_user: CurrentUser,
    attachment_in: AttachmentCreate,
):
    """
    Create a new attachment. Requires module_id to exist.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="No permission.")

    # Verify that the module exists
    module = await session.get(Module, attachment_in.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")

    # Create the attachment
    attachment = Attachment(**attachment_in.model_dump())

    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)

    return AttachmentPublic.model_validate(attachment)


@router.put("/{attachment_id}", response_model=AttachmentPublic)
async def update_attachment_route(
    session: SessionDep,
    current_user: CurrentUser,
    attachment_id: str,
    attachment_in: AttachmentUpdate,
):
    """
    Update an existing attachment. Only superusers can update.
    Fields like `module_id` can be changed, but module must still exist.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="No permission.")

    attachment = await session.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    # Check if module_id is being updated and validate it
    if attachment_in.module_id is not None:
        module = await session.get(Module, attachment_in.module_id)
        if not module:
            raise HTTPException(status_code=404, detail="Module not found.")
        attachment.module_id = module.id
        attachment.module = module

    # Update other fields
    attachment_data = attachment_in.model_dump(exclude_unset=True, exclude={"module_id"})
    for key, value in attachment_data.items():
        setattr(attachment, key, value)

    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)

    return AttachmentPublic.model_validate(attachment)


@router.delete("/{attachment_id}", response_model=Message)
async def delete_attachment_route(
    session: SessionDep,
    current_user: CurrentUser,
    attachment_id: str,
):
    """
    Delete an attachment by ID. Only superusers allowed.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="No permission.")

    attachment = await session.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    await session.delete(attachment)
    await session.flush()

    return Message(message="Attachment deleted successfully.")
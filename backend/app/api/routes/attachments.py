from fastapi import APIRouter, HTTPException
from sqlmodel import select, func

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Attachment,
    AttachmentCreate,
    AttachmentPublic,
    AttachmentUpdate,
    AttachmentsPublic,
    Message,
    Module,
    ReorderAttachments
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
    count_statement = select(func.count()).select_from(Attachment)
    total_count = (await session.exec(count_statement)).one()

    statement = select(Attachment).offset(skip).limit(limit)
    attachments = (await session.exec(statement)).all()

    if not attachments:
        return {"data": [], "count": 0}

    data = [
        AttachmentPublic.from_db(att) for att in attachments
    ]

    return AttachmentsPublic(data=data, count=total_count)


@router.get("/{attachment_id}", response_model=AttachmentPublic)
async def read_attachment_route(
    session: SessionDep,
    current_user: CurrentUser,
    attachment_id: str,
):
    """
    Retrieve a single attachment by ID.
    """
    attachment = await session.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    return AttachmentPublic.from_db(attachment)


@router.post("/", response_model=AttachmentPublic)
async def create_attachment_route(
    session: SessionDep,
    current_user: CurrentUser,
    attachment_in: AttachmentCreate,
):
    """
    Create a new attachment. If module_id is provided, module must exist.
    Order will be auto-assigned as (max_order + 1) within the module.
    """
    # Validate module if provided
    if attachment_in.module_id:
        module = await session.get(Module, attachment_in.module_id)
        if not module:
            raise HTTPException(status_code=404, detail="Module not found.")
        
        # Auto-calculate order
        last_order_statement = (
            select(func.max(Attachment.order))
            .where(Attachment.module_id == attachment_in.module_id)
        )
        result = await session.exec(last_order_statement)
        next_order = (result.one() or 0) + 1
    else:
        module = None
        next_order = 0  # or leave as default

    # Create attachment
    attachment = Attachment(
        **attachment_in.model_dump(exclude={"order"}),
        order=next_order,
        module=module,
    )

    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)

    return AttachmentPublic.from_db(attachment)


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

    attachment = await session.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    # Check if module_id is being updated and validate it
    if attachment_in.module_id is not None:
        module = await session.get(Module, attachment_in.module_id)
        if not module:
            raise HTTPException(status_code=404, detail="Module not found.")
        result = await session.exec(
            select(func.max(Attachment.order)).where(Attachment.module_id == attachment_in.module_id)
        )
        new_order = (result.one() or 0) + 1

        attachment.module_id = module.id
        attachment.module = module
        attachment.order = new_order

    # Update other fields
    attachment_data = attachment_in.model_dump(exclude_unset=True, exclude={"module_id"})
    for key, value in attachment_data.items():
        setattr(attachment, key, value)

    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)

    return AttachmentPublic.from_db(attachment)


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


@router.post("/{module_id}/reorder", response_model=Message)
async def reorder_attachments_in_module(
    module_id: str,
    order_list: ReorderAttachments,  # list of attachment IDs in desired order
    session: SessionDep,
    current_user: CurrentUser,
):
    module = await session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")

    attachments = await session.exec(
        select(Attachment).where(Attachment.id.in_(order_list.order_list))
    )
    attachment_map = {a.id: a for a in attachments.all()}

    if len(attachment_map) != len(order_list.order_list):
        raise HTTPException(status_code=400, detail="Some attachments not found.")

    for idx, att_id in enumerate(order_list.order_list):
        attachment_map[att_id].order = idx
        session.add(attachment_map[att_id])

    await session.flush()
    return Message(message="Attachments reordered.")
from fastapi import APIRouter, HTTPException
from sqlmodel import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Attachment,
    Course,
    Module,
    ModuleCreate, 
    ModuleUpdate, 
    ModulePublic, 
    ModulesPublic,
    ModuleOrderItem, 
    Message,
    Quiz,
)
from app.utils import _get_objects_by_id


router = APIRouter(prefix="/modules", tags=["modules"])

@router.get("/", response_model=ModulesPublic)
async def read_modules_route(
    session: SessionDep, 
    current_user: CurrentUser, 
    skip:int = 0, 
    limit: int=10):

    statement = select(Module).order_by(Module.id).offset(skip).limit(limit)
    modules = (await session.exec(statement)).all()

    if not modules:
        return {"data":[], "count": 0}
    
    data = [await ModulePublic.from_db(db=session, module=module) for module in modules]
    
    count_statement = select(func.count()).select_from(Module)
    total_count = (await session.exec(count_statement)).one()
    return ModulesPublic(
        data=data[skip:skip+limit],
        count=total_count,
    )


@router.get("/{module_id}", response_model=ModulePublic)
async def read_module_route(session: SessionDep, current_user: CurrentUser, module_id: str):
   
    module = await session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")
    
    module_public = await ModulePublic.from_db(session, module)

    return module_public


@router.post("/", response_model=ModulePublic)
async def create_module_route(session:SessionDep, current_user: CurrentUser, module_in: ModuleCreate):

    course = await session.get(Course, module_in.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    attachments = await _get_objects_by_id(Attachment, module_in.attachments, session)
    for index, attachment in enumerate(attachments):
        attachment.order = index + 1

    quizzes = await _get_objects_by_id(Quiz, module_in.quizzes, session)

    module = Module(
        **module_in.model_dump(exclude={"attachments", "quizzes"}),
        author_id=current_user.id,
        course=course,
        attachments=attachments,
        quizzes=quizzes,
    )

    session.add(module)
    await session.flush()
    await session.refresh(module)

    # Return ModulePublic (convert relationships back to ID lists)
    module_public = await ModulePublic.from_db(session, module)

    return module_public


@router.put("/{module_id}", response_model=ModulePublic)
async def update_module_route(
    session: SessionDep,
    current_user: CurrentUser,
    module_id: str,
    module_in: ModuleUpdate,
):  
    statement = select(Module).where(Module.id == module_id).options(
        selectinload(Module.attachments),
        selectinload(Module.quizzes),
    )
    module = (await session.exec(statement)).one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")    
    if not any((current_user.is_superuser, current_user.id == module.author_id)):
        raise HTTPException(status_code=403, detail="No permission.")
    

    # Update scalar fields
    module_data = module_in.model_dump(exclude_unset=True, exclude={"attachments", "quizzes"})
    for key, value in module_data.items():
        setattr(module, key, value)

    # 2. Update attachments if provided
    if "attachments" in module_in.model_fields_set:  # explicitly passed in request
        attachments = await _get_objects_by_id(Attachment, module_in.attachments, session)
        for index, attachment in enumerate(attachments):
            attachment.order = index + 1
        module.attachments = attachments

    # 3. Update quizzes if provided
    if "quizzes" in module_in.model_fields_set:  # explicitly passed
        module.quizzes = await _get_objects_by_id(Quiz, module_in.quizzes, session)

    session.add(module)
    await session.flush()
    await session.refresh(module)

    module_public = await ModulePublic.from_db(session, module)

    return module_public


@router.delete("/{module_id}", response_model=Message)
async def delete_module_route(
    session: SessionDep,
    current_user: CurrentUser,
    module_id: str,
):
    module = await session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")
    if not any((current_user.is_superuser, current_user.id == module.author_id)):
        raise HTTPException(status_code=403, detail="No permission.")

    await session.delete(module)
    await session.flush()

    return Message(message="Module deleted successfully.")


@router.post("/reorder", response_model=dict)
async def reorder_modules(
    session: SessionDep,
    course_id: str,
    order_items: list[ModuleOrderItem]
):
    # 1. Fetch all modules in course
    result = await session.exec(
        select(Module).where(Module.course_id == course_id)
    )
    course_modules = {m.id: m for m in result.all()}

    if not course_modules:
        raise HTTPException(404, "No modules found in course")

    # 2. Validate all module_ids exist in course
    received_ids = [item.module_id for item in order_items]
    unknown_ids = set(received_ids) - set(course_modules.keys())
    if unknown_ids:
        raise HTTPException(400, f"Invalid module IDs: {unknown_ids}")

    # 3. Validate no duplicate orders
    orders = [item.order for item in order_items]
    if len(orders) != len(set(orders)):
        raise HTTPException(400, "Duplicate order values are not allowed")

    # 4. Optional: require all modules to be included
    if set(course_modules.keys()) != set(received_ids):
        raise HTTPException(400, "All modules in the course must be included in reorder request")

    # 5. Optional: validate order is positive
    if any(o < 1 for o in orders):
        raise HTTPException(400, "Position must be >= 1")

    # 6. Apply new order
    for item in order_items:
        module = course_modules[item.module_id]
        module.order = item.order

    await session.flush()
    return {"message": "Module order updated successfully"}
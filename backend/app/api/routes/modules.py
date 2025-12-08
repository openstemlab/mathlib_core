from fastapi import APIRouter, HTTPException
from sqlmodel import select
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

    statement = select(Module).offset(skip).limit(limit)
    modules = (await session.exec(statement)).all()

    if not modules:
        return {"data":[], "count": 0}
    
    data = []
    for module in modules:
        module_public = await ModulePublic.from_db(session, module)
        data.append(module_public)
    count = len(modules)
    return ModulesPublic(
        data=data[skip:skip+limit],
        count=count,
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

    quizzes = await _get_objects_by_id(Quiz, module_in.quizzes, session)

    module = Module(
        **module_in.model_dump(exclude={"attachments", "quizzes"}),
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
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="No permission.")

    statement = select(Module).where(Module.id == module_id).options(
        selectinload(Module.attachments),
        selectinload(Module.quizzes),
    )
    module = (await session.exec(statement)).one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")

    # Update scalar fields
    module_data = module_in.model_dump(exclude_unset=True, exclude={"attachments", "quizzes"})
    for key, value in module_data.items():
        setattr(module, key, value)

    # 2. Update attachments if provided
    if "attachments" in module_in.model_fields_set:  # explicitly passed in request
        module.attachments = await _get_objects_by_id(Attachment, module_in.attachments, session)

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
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="No permission.")

    module = await session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")

    await session.delete(module)
    await session.flush()

    return Message(message="Module deleted successfully.")
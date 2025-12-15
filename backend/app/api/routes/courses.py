from fastapi import APIRouter, HTTPException, status
from sqlmodel import select, func

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Course,
    CourseCreate,
    CoursePublic,
    CoursesPublic,
    CourseUpdate,
    Module,
    User,
)


router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("/", response_model=CoursePublic, status_code=status.HTTP_201_CREATED)
async def create_course_route(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    course_in: CourseCreate,
):
    """
    Create a course with modules.
    - Validates ALL modules first
    - Fails fast if any module is invalid
    - Returns detailed error list
    """
    errors = []

    # 1. Validate modules first — DO NOT CREATE ANYTHING YET

    used_orders = set()
    for idx, mod_data in enumerate(course_in.modules):

        if mod_data.order < 1:
            errors.append({
                "index": idx,
                "field": "order",
                "error": "Order must be >= 1"
            })


        if mod_data.order in used_orders:
            errors.append({
                "index": idx,
                "field": "order",
                "error": f"Duplicate order {mod_data.order}"
            })
        else:
            used_orders.add(mod_data.order)

    # If any errors → fail before touching DB
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Course creation failed due to invalid module data.",
                "errors": errors,
            },
        )

    # 2. Now we know all modules are valid — proceed
    course = Course(
        title=course_in.title,
        description=course_in.description,
        author_id=current_user.id,
    )
    session.add(course)
    await session.flush()  # Get course.id

    # 3. Create all modules (now safe)

    for mod_data in course_in.modules:
        module = Module(
            title=mod_data.title.strip(),
            content=mod_data.content.strip(),
            order=mod_data.order,
            is_draft=mod_data.is_draft or False,
            author_id=current_user.id,
            course_id=course.id,
        )
        session.add(module)

    await session.flush()

    await session.refresh(course)
    return CoursePublic.from_db(course)


@router.get("/", response_model=CoursesPublic)
async def read_courses_route(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 10,
):
    """
    Retrieve courses with pagination.
    """
    statement = select(Course).order_by(Course.id)
    courses = (await session.exec(statement.offset(skip).limit(limit))).all()
    count_statement = select(func.count()).select_from(Course)
    total_count = (await session.exec(count_statement)).one()
    courses_public = [CoursePublic.from_db(course) for course in courses]
    return CoursesPublic(data=courses_public, count=total_count)


@router.get("/{course_id}", response_model=CoursePublic)
async def read_course_route(
    course_id: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    """
    Get a specific course by ID.
    """
    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return CoursePublic.from_db(course)


@router.put("/{course_id}", response_model=CoursePublic)
async def update_course_route(
    *,
    session: SessionDep,
    current_user:CurrentUser,
    course_id: str,
    course_in: CourseUpdate,
):
    """
    Update a course.
    Only the author can update their course.
    """
    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    try:
        update_dict = course_in.model_dump(exclude_unset=True)
        course.sqlmodel_update(update_dict)
        session.add(course)
        await session.flush()
        await session.refresh(course)
        return CoursePublic.from_db(course)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{course_id}", response_model=dict)
async def delete_course_route(
    *,
    session: SessionDep,
    current_user:CurrentUser,
    course_id: str,
):
    """
    Delete a course by ID.
    Only the author can delete their course.
    """
    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    await session.delete(course)
    await session.flush()
    return {"message": "Course deleted successfully"}

@router.post("/{course_id}/enroll", response_model=dict)
async def enroll_in_course_route(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    course_id: str,
):
    """
    Enroll the current user in a course.
    """
    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    user = await session.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if course in user.enrolled_courses:
        raise HTTPException(status_code=400, detail="User already enrolled in this course")

    user.enrolled_courses.append(course)
    

    session.add(user)
    session.add(course)
    await session.flush()
    await session.refresh(user)
    await session.refresh(course)

    return {"message": "User enrolled in course successfully"}


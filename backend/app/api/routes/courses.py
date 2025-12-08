from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Course,
    CourseCreate,
    CoursePublic,
    CoursesPublic,
    CourseUpdate,
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
    Create a new course.
    Only authenticated users can create a course.
    The current user becomes the author.
    """
    try:
        
        course = Course(
            title=course_in.title,
            description=course_in.description,
            author_id=current_user.id,
        )
        session.add(course)
        await session.flush()
        await session.refresh(course)
        return CoursePublic.model_validate(course)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    statement = select(Course)
    courses = (await session.exec(statement.offset(skip).limit(limit))).all()
    count = len(courses)
    courses_public = [CoursePublic.model_validate(course) for course in courses]
    return CoursesPublic(data=courses_public, count=count)


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
    return CoursePublic.model_validate(course)


@router.put("/{course_id}", response_model=CoursePublic)
async def update_course(
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
        return CoursePublic.model_validate(course)
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


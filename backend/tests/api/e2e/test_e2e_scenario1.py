import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

pytestmark = pytest.mark.asyncio(loop_scope="module")

async def test_scenario_one(
        client_with_test_db: AsyncClient,
        db: AsyncSession
):
    user = {
        "email": "test@example.com",
        "password": "strongpassword",
        "full_name": "Test User"
    }

    # Register user
    response = await client_with_test_db.post(f"{settings.API_V1_STR}/users/signup", json=user)

    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == user["email"]
    assert user_data["full_name"] == user["full_name"]

    # Authenticate user

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/login/access-token",
        json={
            "username": user["email"],
            "password": user["password"]
        })
    assert response.status_code == 200
    teacher_auth_token = response.json()["access_token"]
    # Create course, module, quiz, exercises.

    #Creating course
    course = {"title": "Sample Course", "description": "A test course", "modules": []}

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses",
        headers={"Authorization": f"Bearer {teacher_auth_token}"},
        json=course)

    assert response.status_code == 200
    course_data = response.json()
    assert course_data["title"] == course["title"]
    assert course_data["author_id"] == user_data["id"]

    #Creating module
    module = {"title": "Sample Module", "content": "Module content", "order": 1, "is_draft": False, "course_id": course_data["id"], "attachments": [], "quizzes": []}

    response = await client_with_test_db.post(f"{settings.API_V1_STR}/modules/", json=module)

    assert response.status_code == 200
    module_data = response.json()
    assert module_data["title"] == module["title"]
    assert module_data["course_id"] == course_data["id"]

    #Creating exercises
    exercise1 = {"source_name":"Texbook", "source_id":"ex1", "text":"What is 2+2?", "answers":["1", "2", "3", "4"], "solution":"4", "tags":["math"]}
    exercise2 = {"source_name":"Texbook", "source_id":"ex2", "text":"What is 3*3?", "answers":["6", "7", "8", "9"], "solution":"9", "tags":["math"]}
    exercise3 = {"source_name":"Texbook", "source_id":"ex3", "text":"What is 5-2?", "answers":["2", "3", "4", "5"], "solution":"3", "tags":["math"]}

    response1 = await client_with_test_db.post(f"{settings.API_V1_STR}/exercises/", json=exercise1)
    response2 = await client_with_test_db.post(f"{settings.API_V1_STR}/exercises/", json=exercise2)
    response3 = await client_with_test_db.post(f"{settings.API_V1_STR}/exercises/", json=exercise3)
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response3.status_code == 200
    exercise1_data = response1.json()
    exercise2_data = response2.json()
    exercise3_data = response3.json()

    #Creating quiz - while we can create quiz directly, that requires putting in Exercise objects from DB. Here I am trying to put in ExercisePublic objects to see if it works.
    quiz = {
        "title": "Sample Quiz", 
        "exercise_positions": 
            [
            {"exercise":exercise1_data, "position":1}, 
            {"exercise":exercise2_data, "position":2}, 
            {"exercise":exercise3_data, "position":3},
            ],
        }

    response = await client_with_test_db.post(f"{settings.API_V1_STR}/quizzes/", json=quiz)
    assert response.status_code == 200
    quiz_data = response.json()
    assert quiz_data["title"] == quiz["title"]
    assert quiz_data["owner_id"] == user_data["id"]
    # It works like that, but we assumed different scenario, when quiz is created by students.

    #Creating link for a course invitation

    response = await client_with_test_db.post(f"{settings.API_V1_STR}/courses/{course_data['id']}/generate-invite",
        json={"course_id": course_data["id"]}
    )
    assert response.status_code == 200
    invite_data = response.json()
    assert "invite_token" in invite_data


    # Register student
    student = {
        "email": "student@example.com",
        "password": "studentpassword",
        "full_name": "Student User"
    }

    response = await client_with_test_db.post(f"{settings.API_V1_STR}/users/signup", json=student)

    assert response.status_code == 200

    # Authenticate student
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/login/access-token",
        json={
            "username": student["email"],
            "password": student["password"]
        })
    assert response.status_code == 200
    student_auth_token = response.json()["access_token"]
    # Use the invite link to join the course

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/courses/enroll/{invite_data['invite_token']}",
        headers={"Authorization": f"Bearer {student_auth_token}"}
    )
    assert response.status_code == 200


    # Start the quiz

    quiz_request = {"tags": ["math"], "length": 3}
    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/quizzes/start",
        headers={"Authorization": f"Bearer {student_auth_token}"},
        json=quiz_request
    )

    assert response.status_code == 200
    # Submit the quiz
    quiz_data = response.json()
    quiz_id = quiz_data["id"]
    exercise_ids = [ex["exercise"]["id"] for ex in quiz_data["exercises"]]

    submitted_answers = []
    for i, exercise_id in enumerate(exercise_ids):
        submitted_answers.append({
            "exercise_id": exercise_id,
            "answer": f"answer_{i+1}"
        })

    response = await client_with_test_db.post(
        f"{settings.API_V1_STR}/quizzes/{quiz_id}/submit",
        headers={"Authorization": f"Bearer {student_auth_token}"},
        json={"answers": submitted_answers}
    )

    assert response.status_code == 200

    # Check quiz submission for grading
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/quizzes/{quiz_id}/grade",
        headers={"Authorization": f"Bearer {teacher_auth_token}"}
    )
    assert response.status_code == 200

    grade_data = response.json()
    assert grade_data["id"] == quiz_id

    #Send back graded quiz

    manual_grade_request = {
        "corrections":[
            {"exercise_id": exercise_ids[0], "is_correct": False},
            {"exercise_id": exercise_ids[1], "is_correct": False},
            {"exercise_id": exercise_ids[2], "is_correct": False},
            ],
        "feedback":"Good effort, but please review the material and try again.",
        "status":"graded",
        "final_score":0,
        }
    
    response = await client_with_test_db.put(
        f"{settings.API_V1_STR}/quizzes/{quiz_id}/grade",
        headers={"Authorization": f"Bearer {teacher_auth_token}"},
        json=manual_grade_request
    )
    assert response.status_code == 200

    # Check student grades
    student_id = quiz_data["owner_id"]
    response = await client_with_test_db.get(
        f"{settings.API_V1_STR}/students/{student_id}/grades",
        headers={"Authorization": f"Bearer {teacher_auth_token}"},
    )
    assert response.status_code == 200
    grades_data = response.json()
    assert grades_data["user_id"] == student_id
    assert grade_data["user_name"] == "Student User"
    assert len(grades_data["grades"]) == 1
    assert grades_data["grades"][0]["quiz_id"] == quiz_id
    assert grades_data["grades"][0]["score"] == 0.0
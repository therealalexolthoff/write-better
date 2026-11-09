"""Which records a caller may reach (CLAUDE.md: teachers are kept separate).

Every record that belongs to a teacher carries their account uid as
"teacher_id": classes, assignments, students, exercises, submissions and AI
job records. A
teacher only ever reaches records with their own teacher_id; a student
only their own exercises; the admin no student records at all.

Each check below is a FastAPI dependency. Routes list them in
`dependencies=[...]` so they run before the request body is read: a
refused caller gets "not found" (or "forbidden" for the wrong role)
before anything else happens, and can't tell whether the record exists.
api/tests/test_teacher_isolation.py walks every route to prove it.
"""

from fastapi import Depends, HTTPException

from .auth import CurrentUser, get_current_user, require_student, require_teacher
from .firestore_client import get_db


def _student(student_id: str) -> dict | None:
    return get_db().collection("students").document(student_id).get().to_dict()


def _exercise(exercise_id: str) -> dict | None:
    return get_db().collection("exercises").document(exercise_id).get().to_dict()


def _class(class_id: str) -> dict | None:
    return get_db().collection("classes").document(class_id).get().to_dict()


def _assignment(assignment_id: str) -> dict | None:
    return get_db().collection("assignments").document(assignment_id).get().to_dict()


def teacher_owns(record: dict | None, user: CurrentUser) -> bool:
    """True only for a teacher, and only for a record with their teacher_id.
    A record without a teacher_id belongs to nobody."""
    return user.role == "teacher" and record is not None and record.get("teacher_id") == user.uid


def _student_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="student not found")


def _exercise_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="exercise not found")


def _students_own_exercise(exercise: dict | None, user: CurrentUser) -> bool:
    """A student reaches only their own exercises, once assigned."""
    return (
        exercise is not None
        and exercise.get("student_id") == user.student_id
        and exercise.get("status") == "assigned"
    )


# ---- teacher only ----


def owned_student(student_id: str, user: CurrentUser = Depends(require_teacher)) -> None:
    """The student (from the path, or the student_id query parameter)
    belongs to the calling teacher."""
    if not teacher_owns(_student(student_id), user):
        raise _student_not_found()


def owned_exercise(exercise_id: str, user: CurrentUser = Depends(require_teacher)) -> None:
    """The exercise belongs to the calling teacher."""
    if not teacher_owns(_exercise(exercise_id), user):
        raise _exercise_not_found()


def owned_assignment(assignment_id: str, user: CurrentUser = Depends(require_teacher)) -> None:
    """The assignment belongs to the calling teacher."""
    if not teacher_owns(_assignment(assignment_id), user):
        raise HTTPException(status_code=404, detail="assignment not found")


def owned_class(class_id: str, user: CurrentUser = Depends(require_teacher)) -> None:
    """The class (from the path, or the class_id query parameter) belongs
    to the calling teacher."""
    check_class(class_id, user)


def check_class(class_id: str, user: CurrentUser, *, open_only: bool = False) -> dict:
    """The teacher's own class, for routes that take a class id in the
    body or as an optional parameter. With open_only, archived classes
    are refused too (no new students go into one)."""
    record = _class(class_id)
    if not teacher_owns(record, user):
        raise HTTPException(status_code=404, detail="class not found")
    if open_only and record.get("archived"):
        raise HTTPException(status_code=409, detail="That class is archived.")
    return record


# ---- student only ----


def students_exercise(exercise_id: str, user: CurrentUser = Depends(require_student)) -> None:
    """The exercise is the calling student's own."""
    if not _students_own_exercise(_exercise(exercise_id), user):
        raise _exercise_not_found()


# ---- teacher or student ----


def exercise_for_caller(exercise_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    """The owning teacher, or the student it was assigned to."""
    if user.role == "teacher":
        if not teacher_owns(_exercise(exercise_id), user):
            raise _exercise_not_found()
    elif user.role == "student":
        if not _students_own_exercise(_exercise(exercise_id), user):
            raise _exercise_not_found()
    else:
        raise HTTPException(status_code=403, detail="teachers and students only")


def student_for_caller(student_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    """The owning teacher, or the student themselves."""
    if user.role == "teacher":
        if not teacher_owns(_student(student_id), user):
            raise _student_not_found()
    elif user.role == "student":
        if user.student_id != student_id:
            raise HTTPException(status_code=403, detail="not authorized for this student")
    else:
        raise HTTPException(status_code=403, detail="teachers and students only")

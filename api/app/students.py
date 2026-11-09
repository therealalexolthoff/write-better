"""Student account lifecycle: create, deactivate, reset password, delete.

Only a student's own teacher may call these (access.py) - see
docs/REQUIREMENTS.md FR-1/FR-3/FR-4. A student may read their own record.
Deletion requires the caller to pass the student's exact username as
confirmation (the UI-level "type the username to confirm" from FR-4,
enforced here too, not just in the React screen). Every lifecycle change
is audit-logged, per docs/REQUIREMENTS.md FR-5 as extended by the teacher:
account creation and deactivation are audited too, not just deletion and
password reset.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore_v1.base_query import FieldFilter

from . import identity, photos
from .audit import record as record_audit
from .access import check_class, owned_student, student_for_caller
from .auth import CurrentUser, require_teacher
from .firestore_client import get_db
from .profile import student_profile
from .models import (
    DeleteStudentRequest,
    MoveStudentRequest,
    NotesBody,
    ResetPasswordRequest,
    StudentCreateRequest,
    StudentPublic,
)

router = APIRouter(prefix="/students", tags=["students"])


def _student_doc(student_id: str):
    return get_db().collection("students").document(student_id)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="student not found")


@router.post("", response_model=StudentPublic)
def create_student(
    body: StudentCreateRequest, user: CurrentUser = Depends(require_teacher)
) -> StudentPublic:
    check_class(body.class_id, user, open_only=True)
    doc_ref = get_db().collection("students").document()
    try:
        uid = identity.create_student_user(body.username, body.password)
    except identity.EmailTaken as exc:
        raise HTTPException(
            status_code=409, detail="That username is already used at this school. Try adding a letter or a number."
        ) from exc
    identity.set_student_claims(uid, doc_ref.id)
    doc_ref.set(
        {
            "username": body.username,
            "auth_uid": uid,
            "teacher_id": user.uid,
            "class_id": body.class_id,
            "active": True,
            "teacher_notes": "",
            "created_at": datetime.now(timezone.utc),
        }
    )
    record_audit(user.uid, "create_student", target=doc_ref.id)
    return StudentPublic(student_id=doc_ref.id, username=body.username, active=True, class_id=body.class_id)


@router.get("", response_model=list[StudentPublic])
def list_students(class_id: str | None = None, user: CurrentUser = Depends(require_teacher)) -> list[StudentPublic]:
    """The teacher's students, or just one class's."""
    query = get_db().collection("students").where(filter=FieldFilter("teacher_id", "==", user.uid))
    if class_id is not None:
        check_class(class_id, user)
        query = query.where(filter=FieldFilter("class_id", "==", class_id))
    return [
        StudentPublic(student_id=doc.id, username=doc.get("username"), active=doc.get("active"), class_id=doc.get("class_id"))
        for doc in query.stream()
    ]


@router.get("/{student_id}", response_model=StudentPublic, dependencies=[Depends(student_for_caller)])
def get_student(student_id: str) -> StudentPublic:
    doc = _student_doc(student_id).get()
    if not doc.exists:
        raise _not_found()
    return StudentPublic(
        student_id=doc.id, username=doc.get("username"), active=doc.get("active"), class_id=doc.get("class_id")
    )


@router.put("/{student_id}/class", dependencies=[Depends(owned_student)])
def move_student(
    student_id: str, body: MoveStudentRequest, user: CurrentUser = Depends(require_teacher)
) -> StudentPublic:
    """Moves a student to another of the teacher's open classes. Their work,
    profile and notes go with them."""
    check_class(body.class_id, user, open_only=True)
    doc_ref = _student_doc(student_id)
    doc_ref.update({"class_id": body.class_id})
    record_audit(user.uid, "move_student", target=student_id)
    doc = doc_ref.get()
    return StudentPublic(student_id=doc.id, username=doc.get("username"), active=doc.get("active"), class_id=body.class_id)


@router.get("/{student_id}/profile", dependencies=[Depends(owned_student)])
def get_profile(student_id: str, user: CurrentUser = Depends(require_teacher)) -> dict:
    """The learner profile (FR-30) and the teacher's private notes (FR-31).
    Teacher only: students never see either."""
    doc = _student_doc(student_id).get()
    if not doc.exists:
        raise _not_found()
    return {"profile": student_profile(student_id), "teacher_notes": doc.get("teacher_notes") or ""}


@router.put("/{student_id}/notes", dependencies=[Depends(owned_student)])
def save_notes(student_id: str, body: NotesBody, user: CurrentUser = Depends(require_teacher)) -> dict:
    """The teacher's private notes. Never sent to the AI provider."""
    doc_ref = _student_doc(student_id)
    if not doc_ref.get().exists:
        raise _not_found()
    doc_ref.update({"teacher_notes": body.teacher_notes})
    return {"status": "ok"}


@router.post("/{student_id}/deactivate", response_model=StudentPublic, dependencies=[Depends(owned_student)])
def deactivate_student(
    student_id: str, user: CurrentUser = Depends(require_teacher)
) -> StudentPublic:
    doc_ref = _student_doc(student_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise _not_found()
    identity.disable_user(doc.get("auth_uid"))
    doc_ref.update({"active": False})
    record_audit(user.uid, "deactivate_student", target=student_id)
    return StudentPublic(student_id=student_id, username=doc.get("username"), active=False)


@router.post("/{student_id}/reset-password", dependencies=[Depends(owned_student)])
def reset_password(
    student_id: str, body: ResetPasswordRequest, user: CurrentUser = Depends(require_teacher)
) -> dict:
    doc = _student_doc(student_id).get()
    if not doc.exists:
        raise _not_found()
    identity.reset_password(doc.get("auth_uid"), body.password)
    record_audit(user.uid, "reset_password", target=student_id)
    return {"status": "ok"}


@router.delete("/{student_id}", dependencies=[Depends(owned_student)])
def delete_student(
    student_id: str, body: DeleteStudentRequest, user: CurrentUser = Depends(require_teacher)
) -> dict:
    doc_ref = _student_doc(student_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise _not_found()
    if body.confirm_username != doc.get("username"):
        raise HTTPException(status_code=400, detail="confirm_username does not match")

    # Everything the student owns (FR-4): photos, exercises, submissions,
    # and the job records of their AI calls (a failed job's error
    # can quote their text). The student record goes last, so if anything
    # fails partway, running the deletion again finds it and finishes.
    # The audit log keeps only ids, so its entries stay.
    photos.delete_folder(f"{student_id}/")
    db = get_db()
    for collection in ("exercises", "submissions", "jobs"):
        for owned in db.collection(collection).where(filter=FieldFilter("student_id", "==", student_id)).stream():
            db.collection(collection).document(owned.id).delete()
    identity.delete_user(doc.get("auth_uid"))
    doc_ref.delete()
    record_audit(user.uid, "delete_student", target=student_id)
    return {"status": "ok"}

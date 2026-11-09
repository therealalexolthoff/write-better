"""The admin: teacher sign-ups and teacher accounts.

Admin only (every route), and audit-logged. The admin manages accounts and
never reaches student work (CLAUDE.md): these routes return names, emails,
statuses and counts, never student records or their writing.

Sign-ups (signup.py creates them): approve gives the login the teacher
role; reject deletes the login and the request. Requests left pending
longer than SIGNUP_EXPIRY are deleted the next time the admin lists them.

Teachers: Firestore teachers/{auth uid}: name, email, active, source
("signup" or "admin"), created_at. The admin can also create a teacher
directly (with a one-time link to set their password), deactivate and
reactivate one, send a new password link, clear a lost authenticator app,
and transfer all of one teacher's students and their work to another.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, Field

from . import identity
from .audit import record as record_audit
from .auth import CurrentUser, require_admin
from .firestore_client import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

SIGNUP_EXPIRY = timedelta(days=30)
# Everything a teacher owns, by teacher_id (docs/ARCHITECTURE.md section 4).
# Classes go first, so moved students are never in a class their new
# teacher can't see; students last, so a transfer that stops partway still
# leaves each student with the teacher who can see the rest of their work.
# Run it again to finish.
OWNED_COLLECTIONS = ("classes", "assignments", "exercises", "submissions", "jobs", "students")


class NewTeacherBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # A basic shape check; Identity Platform validates the address itself.
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TransferBody(BaseModel):
    to_teacher_id: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _teacher_ref(uid: str):
    return get_db().collection("teachers").document(uid)


def _load_teacher(uid: str) -> dict:
    doc = _teacher_ref(uid).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="teacher not found")
    return doc.to_dict()


def _owned(collection: str, teacher_id: str):
    return get_db().collection(collection).where(filter=FieldFilter("teacher_id", "==", teacher_id)).stream()


# ---- sign-ups ----


@router.get("/signups")
def list_signups(user: CurrentUser = Depends(require_admin)) -> list[dict]:
    """Pending sign-ups, oldest first. Expired ones are deleted on the way."""
    pending = []
    for doc in get_db().collection("signup_requests").stream():
        request = doc.to_dict()
        if _now() - request["created_at"] > SIGNUP_EXPIRY:
            identity.delete_user(doc.id)
            get_db().collection("signup_requests").document(doc.id).delete()
            record_audit(user.uid, "expire_signup", target=doc.id)
            continue
        pending.append(
            {
                "uid": doc.id,
                "name": request["name"],
                "email": request["email"],
                "email_verified": identity.email_verified(doc.id),
                "created_at": request["created_at"],
            }
        )
    return sorted(pending, key=lambda r: r["created_at"])


def _load_signup(uid: str) -> dict:
    doc = get_db().collection("signup_requests").document(uid).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="sign-up request not found")
    return doc.to_dict()


@router.post("/signups/{uid}/approve")
def approve_signup(uid: str, user: CurrentUser = Depends(require_admin)) -> dict:
    request = _load_signup(uid)
    identity.set_role(uid, "teacher")
    _teacher_ref(uid).set(
        {"name": request["name"], "email": request["email"], "active": True, "source": "signup", "created_at": _now()}
    )
    get_db().collection("signup_requests").document(uid).delete()
    record_audit(user.uid, "approve_signup", target=uid)
    return {"status": "approved"}


@router.post("/signups/{uid}/reject")
def reject_signup(uid: str, user: CurrentUser = Depends(require_admin)) -> dict:
    _load_signup(uid)
    identity.delete_user(uid)
    get_db().collection("signup_requests").document(uid).delete()
    record_audit(user.uid, "reject_signup", target=uid)
    return {"status": "rejected"}


# ---- teachers ----


@router.get("/teachers")
def list_teachers(user: CurrentUser = Depends(require_admin)) -> list[dict]:
    teachers = [
        {
            "uid": doc.id,
            "name": doc.get("name"),
            "email": doc.get("email"),
            "active": doc.get("active"),
            "student_count": sum(1 for _ in _owned("students", doc.id)),
        }
        for doc in get_db().collection("teachers").stream()
    ]
    return sorted(teachers, key=lambda t: t["name"].lower())


@router.post("/teachers")
def create_teacher(body: NewTeacherBody, user: CurrentUser = Depends(require_admin)) -> dict:
    """A teacher account made by the admin, with a one-time link for the
    teacher to set their password. They verify their email and set up an
    authenticator app the first time they sign in, like any teacher."""
    try:
        uid = identity.create_teacher_user(body.email, body.name.strip())
    except identity.EmailTaken as exc:
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
    identity.set_role(uid, "teacher")
    _teacher_ref(uid).set(
        {"name": body.name.strip(), "email": body.email, "active": True, "source": "admin", "created_at": _now()}
    )
    record_audit(user.uid, "create_teacher", target=uid)
    return {"uid": uid, "setup_link": identity.password_setup_link(body.email)}


@router.post("/teachers/{uid}/deactivate")
def deactivate_teacher(uid: str, user: CurrentUser = Depends(require_admin)) -> dict:
    """The teacher can't sign in until reactivated. Their students and work
    are kept; transfer them to another teacher if they're leaving."""
    _load_teacher(uid)
    identity.disable_user(uid)
    _teacher_ref(uid).update({"active": False})
    record_audit(user.uid, "deactivate_teacher", target=uid)
    return {"status": "deactivated"}


@router.post("/teachers/{uid}/reactivate")
def reactivate_teacher(uid: str, user: CurrentUser = Depends(require_admin)) -> dict:
    _load_teacher(uid)
    identity.enable_user(uid)
    _teacher_ref(uid).update({"active": True})
    record_audit(user.uid, "reactivate_teacher", target=uid)
    return {"status": "active"}


@router.post("/teachers/{uid}/password-link")
def password_link(uid: str, user: CurrentUser = Depends(require_admin)) -> dict:
    """A one-time link to set a new password, for the admin to send."""
    teacher = _load_teacher(uid)
    record_audit(user.uid, "teacher_password_link", target=uid)
    return {"link": identity.password_setup_link(teacher["email"])}


@router.post("/teachers/{uid}/reset-authenticator")
def reset_authenticator(uid: str, user: CurrentUser = Depends(require_admin)) -> dict:
    """For a lost phone: the teacher signs in with their password next time
    and sets up a new authenticator app."""
    _load_teacher(uid)
    identity.clear_authenticator(uid)
    record_audit(user.uid, "reset_teacher_authenticator", target=uid)
    return {"status": "reset"}


@router.post("/teachers/{uid}/transfer")
def transfer_students(uid: str, body: TransferBody, user: CurrentUser = Depends(require_admin)) -> dict:
    """Moves every student of one teacher, with all their work, to another.
    Safe to run again if it stops partway. Returns how many records moved."""
    if body.to_teacher_id == uid:
        raise HTTPException(status_code=422, detail="Choose a different teacher.")
    _load_teacher(uid)
    target = _load_teacher(body.to_teacher_id)
    if not target["active"]:
        raise HTTPException(status_code=409, detail="That teacher is deactivated.")
    moved = {}
    for collection in OWNED_COLLECTIONS:
        docs = list(_owned(collection, uid))
        for doc in docs:
            get_db().collection(collection).document(doc.id).update({"teacher_id": body.to_teacher_id})
        moved[collection] = len(docs)
    record_audit(user.uid, "transfer_students", target=f"{uid}->{body.to_teacher_id}")
    return {"moved": moved}

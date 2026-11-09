"""A teacher's classes: create, rename, archive and reopen.

Firestore: classes/{id}: teacher_id, name, archived, created_at. Every
student belongs to one of their teacher's classes (students.class_id).
Archiving a class keeps its students and their work; it just can't take
new students, and the screens list it separately. Only a class's own
teacher reaches it (access.py).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, Field

from .access import owned_class
from .audit import record as record_audit
from .auth import CurrentUser, require_teacher
from .firestore_client import get_db

router = APIRouter(prefix="/classes", tags=["classes"])


class ClassBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)


def _ref(class_id: str):
    return get_db().collection("classes").document(class_id)


def _view(class_id: str, data: dict, student_count: int) -> dict:
    return {"class_id": class_id, "name": data["name"], "archived": data.get("archived", False), "student_count": student_count}


@router.get("")
def list_classes(user: CurrentUser = Depends(require_teacher)) -> list[dict]:
    """The teacher's classes: open ones first, then archived, each by name."""
    db = get_db()
    counts: dict[str, int] = {}
    for student in db.collection("students").where(filter=FieldFilter("teacher_id", "==", user.uid)).stream():
        counts[student.get("class_id")] = counts.get(student.get("class_id"), 0) + 1
    classes = [
        _view(doc.id, doc.to_dict(), counts.get(doc.id, 0))
        for doc in db.collection("classes").where(filter=FieldFilter("teacher_id", "==", user.uid)).stream()
    ]
    return sorted(classes, key=lambda c: (c["archived"], c["name"].lower()))


@router.post("")
def create_class(body: ClassBody, user: CurrentUser = Depends(require_teacher)) -> dict:
    ref = get_db().collection("classes").document()
    data = {"teacher_id": user.uid, "name": body.name.strip(), "archived": False, "created_at": datetime.now(timezone.utc)}
    ref.set(data)
    record_audit(user.uid, "create_class", target=ref.id)
    return _view(ref.id, data, 0)


@router.put("/{class_id}", dependencies=[Depends(owned_class)])
def rename_class(class_id: str, body: ClassBody, user: CurrentUser = Depends(require_teacher)) -> dict:
    _ref(class_id).update({"name": body.name.strip()})
    return {"status": "ok"}


@router.post("/{class_id}/archive", dependencies=[Depends(owned_class)])
def archive_class(class_id: str, user: CurrentUser = Depends(require_teacher)) -> dict:
    _ref(class_id).update({"archived": True})
    record_audit(user.uid, "archive_class", target=class_id)
    return {"status": "archived"}


@router.post("/{class_id}/reopen", dependencies=[Depends(owned_class)])
def reopen_class(class_id: str, user: CurrentUser = Depends(require_teacher)) -> dict:
    _ref(class_id).update({"archived": False})
    record_audit(user.uid, "reopen_class", target=class_id)
    return {"status": "open"}

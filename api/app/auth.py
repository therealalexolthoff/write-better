"""Authentication: who is calling, and which role they have.

Every endpoint except /health* and /config depends on one of these. Which
records a caller may touch (a teacher's own students and work, a
student's own exercises) is checked in access.py.

Roles (set as a custom claim on the Identity Platform account):
- "admin":   manages accounts and spending; never reaches student work.
- "teacher": their own classes, students and student work.
- "student": their own exercises.
An account with no role (for example a teacher sign-up the admin hasn't
approved yet) is refused everywhere.
"""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from . import identity

ROLES = ("admin", "teacher", "student")
# Roles that must sign in with an authenticator code as well as a password.
MFA_ROLES = ("admin", "teacher")


@dataclass
class CurrentUser:
    uid: str
    role: str  # one of ROLES
    student_id: str | None  # set only when role == "student"


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.removeprefix("Bearer ")
    try:
        claims = identity.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    role = claims.get("role")
    if role not in ROLES:
        raise HTTPException(status_code=401, detail="token missing a role claim")

    # MFA is enforced here, not just in the login screen (docs/REQUIREMENTS.md
    # FR-2). Identity Platform records the second factor used for this
    # sign-in in the token's "firebase" claim; a password-only admin or
    # teacher token is refused.
    if role in MFA_ROLES and claims.get("firebase", {}).get("sign_in_second_factor") != "totp":
        raise HTTPException(status_code=401, detail="this sign-in requires the authenticator code")

    return CurrentUser(uid=claims["uid"], role=role, student_id=claims.get("student_id"))


def require_teacher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="teacher only")
    return user


def require_student(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="students only")
    return user

"""Teacher sign-up requests.

The sign-up page creates the login in the browser with Identity Platform
(name, email, password) and Identity Platform sends a verification email.
Passwords go only to Identity Platform: this API never sees them. The new
login has no role, so it reaches nothing except these two routes. It then
asks to become a teacher here, and waits for the admin (admin.py) to
approve or reject the request.

Spam protection: a hidden form field ("website") that people never see but
bots fill in, a daily limit on new requests, and Identity Platform's own
limits on account creation. The email comes from the signed-in token, never
from the request body, so nobody can ask for an account in someone else's
name.

Firestore: signup_requests/{auth uid}: name, email, status ("pending"),
created_at, day (YYYY-MM-DD, for the daily limit). The admin approving or
rejecting a request deletes it.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, ConfigDict, Field

from shared.logs import log_event

from . import identity
from .auth import Account, get_account
from .firestore_client import get_db

router = APIRouter(prefix="/signup", tags=["signup"])

MAX_SIGNUPS_PER_DAY = 20


class SignupBody(BaseModel):
    # No other fields: in particular no email, which comes from the token.
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    # The hidden field. Anything in it means a bot filled in the form.
    website: str = Field(default="", max_length=200)


def _request_ref(uid: str):
    return get_db().collection("signup_requests").document(uid)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@router.post("")
def request_teacher_account(body: SignupBody, account: Account = Depends(get_account)) -> dict:
    """Asks for the signed-in, role-less login to become a teacher account.
    Asking again just reports the same pending request."""
    if account.role is not None:
        raise HTTPException(status_code=409, detail="This account is already set up.")
    if not account.email:
        raise HTTPException(status_code=422, detail="Sign up with an email address.")

    if body.website.strip():
        # Same reply as a real request, so the bot learns nothing; its login goes.
        log_event("signup_honeypot", "WARNING")
        identity.delete_user(account.uid)
        return {"status": "pending"}

    existing = _request_ref(account.uid).get()
    if existing.exists:
        return {"status": existing.get("status")}

    today = _today()
    requests_today = get_db().collection("signup_requests").where(filter=FieldFilter("day", "==", today)).stream()
    if sum(1 for _ in requests_today) >= MAX_SIGNUPS_PER_DAY:
        log_event("signup_daily_limit", "WARNING", limit=MAX_SIGNUPS_PER_DAY)
        raise HTTPException(status_code=429, detail="Sign-ups are full for today. Please try again tomorrow.")

    _request_ref(account.uid).set(
        {
            "name": body.name.strip(),
            "email": account.email,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "day": today,
        }
    )
    # Emails the admin (infra/monitoring.sh). Ids only, never the name or email.
    log_event("signup_requested", "NOTICE", uid=account.uid)
    return {"status": "pending"}


@router.get("/me")
def my_request(account: Account = Depends(get_account)) -> dict:
    """The caller's own sign-up status, for the "waiting for approval" page."""
    doc = _request_ref(account.uid).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="No sign-up request for this account.")
    return {"status": doc.get("status"), "email_verified": account.email_verified}

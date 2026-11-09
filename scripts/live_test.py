"""End-to-end test against the deployed app, with throwaway accounts.

    GOOGLE_CLOUD_PROJECT=write-better-app .venv/bin/python scripts/live_test.py <app URL> <a JPEG file>

Signs in exactly as people do - Identity Platform's REST API with the app's
public browser key, authenticator codes worked out from the enrolled secret
- and walks the whole path: a teacher signs up, the admin approves them,
they set up an authenticator, create a class and a student, and assign
writing; the student writes and adds a photo; the teacher scrubs, gets real
AI feedback, approves and releases; the student sees it. Then it checks
that a second teacher can't see any of it, that resetting an authenticator
works, and what sign-up says about a taken email. Everything it created is
deleted at the end (the student through the app's own delete route), even
if a step fails.

Makes two real AI calls (a few cents). Uses your gcloud sign-in for the few
setup steps a person would do by clicking a link (verifying an email).
Prints ids and statuses only.
"""

import base64
import hashlib
import hmac
import os
import secrets
import struct
import subprocess
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "infra"))
from create_admin import init  # noqa: E402 - your gcloud sign-in for firebase_admin
from firebase_admin import auth  # noqa: E402

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
APP = sys.argv[1].rstrip("/")
JPEG = open(sys.argv[2], "rb").read()
TAG = f"livetest{secrets.token_hex(3)}"
IDT = "https://identitytoolkit.googleapis.com"
results: list[tuple[str, bool, str]] = []
cleanup_uids: list[str] = []
cleanup_docs: list[tuple[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  - ' + detail) if detail else ''}", flush=True)


# ---- Identity Platform, as the browser does it ----

KEY = requests.get(f"{APP}/config", timeout=30).json()["firebase"]["apiKey"]
BROWSER = {"Referer": f"{APP}/", "Content-Type": "application/json"}


def idt(path: str, body: dict, version: str = "v1") -> dict:
    response = requests.post(f"{IDT}/{version}/{path}?key={KEY}", json=body, headers=BROWSER, timeout=30)
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"{path}: {data['error'].get('message')}")
    return data


def totp(secret: str, at: float | None = None) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = int((at or time.time()) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    return f"{(struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def fresh_code(secret: str) -> str:
    """A code from a 30-second window not used yet (codes can't be reused)."""
    time.sleep(31 - time.time() % 30)
    return totp(secret)


def enroll(id_token: str) -> str:
    """Adds an authenticator, as the setup screen does. Returns its secret."""
    started = idt("accounts/mfaEnrollment:start", {"idToken": id_token, "totpEnrollmentInfo": {}}, "v2")["totpSessionInfo"]
    idt(
        "accounts/mfaEnrollment:finalize",
        {"idToken": id_token, "displayName": "Authenticator app",
         "totpVerificationInfo": {"sessionInfo": started["sessionInfo"], "verificationCode": totp(started["sharedSecretKey"])}},
        "v2",
    )
    return started["sharedSecretKey"]


def sign_in(email: str, password: str, secret: str | None = None) -> str:
    data = idt("accounts:signInWithPassword", {"email": email, "password": password, "returnSecureToken": True})
    if "mfaPendingCredential" not in data:
        return data["idToken"]
    done = idt(
        "accounts/mfaSignIn:finalize",
        {"mfaPendingCredential": data["mfaPendingCredential"], "mfaEnrollmentId": data["mfaInfo"][0]["mfaEnrollmentId"],
         "totpVerificationInfo": {"verificationCode": fresh_code(secret)}},
        "v2",
    )
    return done["idToken"]


def api(method: str, path: str, token: str | None, **kwargs) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.request(method, f"{APP}{path}", headers={**headers, **kwargs.pop("headers", {})}, timeout=300, **kwargs)


def staff(email: str, role: str | None = None) -> tuple[str, str, str]:
    """A staff login with a verified email (as if they'd clicked the link),
    an authenticator, and the given role. Returns (uid, password, secret)."""
    password = secrets.token_urlsafe(18)
    uid = auth.create_user(email=email, password=password, email_verified=True).uid
    cleanup_uids.append(uid)
    if role:
        auth.set_custom_user_claims(uid, {"role": role})
    secret = enroll(sign_in(email, password))
    return uid, password, secret


def main() -> None:
    init(PROJECT)

    # ---- the admin ----
    admin_email = f"{TAG}.admin@example.com"
    admin_uid, admin_pw, admin_secret = staff(admin_email, "admin")
    admin = sign_in(admin_email, admin_pw, admin_secret)
    check("admin signs in with password + authenticator code", api("GET", "/admin/signups", admin).status_code == 200)

    # ---- a teacher signs up ----
    t_email, t_pw = f"{TAG}.teacher@example.com", secrets.token_urlsafe(18)
    signed_up = idt("accounts:signUp", {"email": t_email, "password": t_pw, "returnSecureToken": True})
    t_uid = signed_up["localId"]
    cleanup_uids.append(t_uid)
    cleanup_docs.append(("teachers", t_uid))
    pending = signed_up["idToken"]
    response = api("POST", "/signup", pending, json={"name": f"Live Test {TAG}"})
    check("sign-up request is accepted", response.json() == {"status": "pending"}, str(response.status_code))
    check("a pending sign-up reaches nothing else", api("GET", "/students", pending).status_code == 401)
    check("the admin sees the sign-up", t_uid in str(api("GET", "/admin/signups", admin).json()))
    check("the admin approves it", api("POST", f"/admin/signups/{t_uid}/approve", admin).status_code == 200)

    # [VERIFY] what sign-up says about a taken email, with enumeration protection on.
    try:
        idt("accounts:signUp", {"email": t_email, "password": secrets.token_urlsafe(18), "returnSecureToken": True})
        check("[VERIFY] sign-up with a taken email", False, "was accepted")
    except RuntimeError as exc:
        check("[VERIFY] sign-up with a taken email is refused", True, str(exc).split(": ", 1)[1])

    # The teacher verifies their email, then must still add an authenticator.
    auth.update_user(t_uid, email_verified=True)
    no_code = sign_in(t_email, t_pw)
    check("approved teacher without an authenticator is refused", api("GET", "/students", no_code).status_code == 401)
    t_secret = enroll(no_code)
    teacher = sign_in(t_email, t_pw, t_secret)
    check("teacher signs in with the authenticator code", api("GET", "/classes", teacher).json() == [])

    # ---- class, student, assignment ----
    class_id = api("POST", "/classes", teacher, json={"name": "Live test class"}).json()["class_id"]
    cleanup_docs.append(("classes", class_id))
    username, s_pw = f"{TAG}.s1", secrets.token_urlsafe(12)
    student_id = api("POST", "/students", teacher, json={"username": username, "password": s_pw, "class_id": class_id}).json()["student_id"]
    check("teacher creates a student", bool(student_id))
    created = api("POST", "/assignments", teacher, json={"class_id": class_id, "draft": {
        "kind": "writing", "title": "Live test", "prompt": "Describe your last weekend.", "min_words": None, "max_words": None}}).json()
    cleanup_docs.append(("assignments", created["assignment_id"]))
    exercise_id = created["exercise_ids"][0]
    check("teacher assigns writing to the class", len(created["exercise_ids"]) == 1)

    # ---- the student ----
    student = idt("accounts:signInWithPassword", {"email": f"{username}@students.internal", "password": s_pw, "returnSecureToken": True})["idToken"]
    check("student signs in", api("GET", "/me/exercises", student).json()[0]["exercise_id"] == exercise_id)
    text = "Last weekend I go to the beach with my sister. We swimmed in the sea and eat ice cream."
    api("PUT", f"/exercises/{exercise_id}/answers", student, json={"answers": {"text": text}})
    photo = api("POST", f"/exercises/{exercise_id}/photos", student, data=JPEG, headers={"Content-Type": "image/jpeg"})
    check("student uploads a photo", photo.status_code == 200 and len(photo.json()) == 1, str(photo.status_code))
    link = photo.json()[0]["url"] if photo.status_code == 200 else ""
    check("the photo's signed link works", link.startswith("https://storage.googleapis.com/") and requests.get(link, timeout=30).status_code == 200)
    check("student submits", api("POST", f"/exercises/{exercise_id}/submit", student, json={"answers": {"text": text}}).status_code == 200)

    # ---- the teacher reviews, with real AI ----
    transcribed = api("POST", f"/exercises/{exercise_id}/transcribe", teacher)
    check("real AI transcription of the photo", transcribed.status_code == 200, transcribed.json().get("state", transcribed.text[:120]))
    api("POST", f"/exercises/{exercise_id}/final-source", teacher, json={"source": "typed"})
    api("PUT", f"/exercises/{exercise_id}/scrubbed", teacher, json={"scrubbed_answers": {"text": text}})
    evaluated = api("POST", f"/exercises/{exercise_id}/evaluate", teacher, json={"note": ""})
    marks = len((evaluated.json().get("evaluation") or {}).get("annotations", [])) if evaluated.ok else 0
    check("real AI evaluation", evaluated.status_code == 200 and marks > 0, f"{marks} errors flagged" if evaluated.ok else evaluated.text[:160])
    check("approve and release", api("POST", f"/exercises/{exercise_id}/approve", teacher).ok and api("POST", f"/exercises/{exercise_id}/release", teacher).ok)
    view = api("GET", f"/exercises/{exercise_id}", student).json()
    check("student sees their marked writing", len(view.get("spans", [])) == marks and "correction" not in str(view))
    check("student's progress counts it", api("GET", "/me/errors", student).json()["pieces"] == 1)
    spending = api("GET", "/admin/spending", admin).json()
    check("admin's spending shows the AI calls", spending["calls"] >= 2, f"${spending['total_usd']:.4f} this month")

    # ---- a second teacher sees none of it ----
    other = api("POST", "/admin/teachers", admin, json={"name": f"Other {TAG}", "email": f"{TAG}.other@example.com"}).json()
    o_uid = other["uid"]
    cleanup_uids.append(o_uid)
    cleanup_docs.append(("teachers", o_uid))
    check("admin creates a teacher with a setup link", "oobCode=" in other["setup_link"] or "mode=resetPassword" in other["setup_link"])
    o_pw = secrets.token_urlsafe(18)
    auth.update_user(o_uid, password=o_pw, email_verified=True)  # as if they'd used the link and verified
    o_secret = enroll(sign_in(f"{TAG}.other@example.com", o_pw))
    second = sign_in(f"{TAG}.other@example.com", o_pw, o_secret)
    refused = [api(m, p, second).status_code for m, p in (
        ("GET", f"/students/{student_id}"), ("GET", f"/exercises/{exercise_id}"), ("GET", f"/assignments/{created['assignment_id']}"),
        ("GET", f"/overview?class_id={class_id}"), ("GET", f"/exercises/{exercise_id}/photos"))]
    check("a second teacher can't reach the first teacher's work", refused == [404] * 5, str(refused))
    check("a second teacher's lists are empty", api("GET", "/students", second).json() == [] and api("GET", "/assignments", second).json() == [])
    check("the admin can't reach student work", api("GET", f"/exercises/{exercise_id}", admin).status_code == 403)

    # ---- [VERIFY] resetting a lost authenticator ----
    reset = api("POST", f"/admin/teachers/{o_uid}/reset-authenticator", admin)
    after = requests.post(f"{IDT}/v1/projects/{PROJECT}/accounts:lookup", json={"localId": [o_uid]}, timeout=30, headers={
        "Authorization": f"Bearer {gcloud_token()}", "x-goog-user-project": PROJECT}).json()["users"][0]
    password_only = idt("accounts:signInWithPassword", {"email": f"{TAG}.other@example.com", "password": o_pw, "returnSecureToken": True})
    check("[VERIFY] resetting an authenticator clears it", reset.ok and not after.get("mfaInfo") and "idToken" in password_only,
          f"status {reset.status_code}, enrollments left: {len(after.get('mfaInfo', []))}")

    # ---- deleting the student through the app ----
    deleted = api("DELETE", f"/students/{student_id}", teacher, json={"confirm_username": username})
    check("teacher deletes the student, with their photos and work", deleted.ok and requests.get(link, timeout=30).status_code != 200)


def gcloud_token() -> str:
    return subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()


def cleanup() -> None:
    from google.cloud import firestore
    from google.oauth2.credentials import Credentials

    db = firestore.Client(project=PROJECT, credentials=Credentials(gcloud_token()))
    for collection, doc_id in cleanup_docs:
        db.collection(collection).document(doc_id).delete()
    for doc in db.collection("signup_requests").stream():
        if doc.get("email", "").startswith(TAG):
            doc.reference.delete()
    for uid in cleanup_uids:
        try:
            auth.delete_user(uid)
        except auth.UserNotFoundError:
            pass
    leftover = [u.email for u in auth.list_users().iterate_all() if (u.email or "").startswith(TAG)]
    print(f"cleanup: removed {len(cleanup_uids)} logins and {len(cleanup_docs)} records; test logins left: {len(leftover)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # report, then always clean up
        check("unexpected error", False, f"{type(exc).__name__}: {exc}")
    finally:
        cleanup()
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)

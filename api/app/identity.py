"""Identity Platform access: account lifecycle, roles and ID token verification.

Wraps firebase_admin so the rest of the API never imports it directly -
that makes it simple to monkeypatch in tests (see api/tests/conftest.py)
instead of needing live Identity Platform credentials to run the suite.

Accounts:
- Students are created by their teacher (students.py), with a synthetic
  email and a teacher-set password.
- Teachers sign up themselves in the browser (Identity Platform creates
  the login), or the admin creates them (admin.py). Either way they have
  no role until the admin approves them.
- The admin account is set up once with infra/create_admin.py.
The role is a custom claim: "admin", "teacher" or "student" (auth.py).
"""

from urllib.parse import parse_qs, urlencode, urlsplit

import firebase_admin
from firebase_admin import auth as fb_auth

STUDENT_EMAIL_DOMAIN = "students.internal"


class EmailTaken(Exception):
    """The email (or, for a student, the username) is already registered."""

_app: firebase_admin.App | None = None


def _get_app() -> firebase_admin.App:
    global _app
    if _app is None:
        _app = firebase_admin.initialize_app()
    return _app


def student_email(username: str) -> str:
    return f"{username}@{STUDENT_EMAIL_DOMAIN}"


def create_student_user(username: str, password: str) -> str:
    """Creates the Identity Platform user for a new student. Returns the auth
    uid. Raises EmailTaken if the username is already used: usernames are
    unique across the whole school, whichever teacher has the student."""
    _get_app()
    try:
        user = fb_auth.create_user(
            email=student_email(username),
            password=password,
            # True because this address is synthetic and unreachable, not because
            # anyone verified it - there's no inbox to check. Avoids the console
            # showing a permanently "unverified" account.
            email_verified=True,
        )
    except fb_auth.EmailAlreadyExistsError as exc:
        raise EmailTaken(username) from exc
    return user.uid


def set_student_claims(uid: str, student_id: str) -> None:
    _get_app()
    fb_auth.set_custom_user_claims(uid, {"role": "student", "student_id": student_id})


def set_role(uid: str, role: str) -> None:
    """Gives an admin or teacher account its role. The user's next token
    refresh (at most an hour, or at once when the app asks) carries it."""
    _get_app()
    fb_auth.set_custom_user_claims(uid, {"role": role})


def email_verified(uid: str) -> bool:
    _get_app()
    return fb_auth.get_user(uid).email_verified


def create_teacher_user(email: str, name: str) -> str:
    """Creates a teacher login with no password; they set one from the
    setup link (password_setup_link). Raises EmailTaken if the email is
    already registered. Returns the auth uid."""
    _get_app()
    try:
        return fb_auth.create_user(email=email, display_name=name, email_verified=False).uid
    except fb_auth.EmailAlreadyExistsError as exc:
        raise EmailTaken(email) from exc


def action_link_path(link: str) -> str:
    """The app's own page for an Identity Platform email link: the same
    one-time code, opened at /account-action (web/src/public/AccountAction.tsx)
    instead of Google's hosted page, which can't use the app's sign-in key.
    A path, so it works on whatever address the app is served from."""
    query = parse_qs(urlsplit(link).query)
    return "/account-action?" + urlencode({"mode": query["mode"][0], "oobCode": query["oobCode"][0]})


def password_setup_link(email: str) -> str:
    """A one-time link (a path on the app) to set or reset the account's
    password. The admin copies it to the teacher: there is no email service
    of our own."""
    _get_app()
    return action_link_path(fb_auth.generate_password_reset_link(email))


def clear_authenticator(uid: str) -> None:
    """Removes the account's authenticator app, for a teacher who lost their
    phone. Their next sign-in is password only, and the app then walks them
    through setting up a new authenticator.

    The Python Admin SDK has no call for this, so it goes to Identity
    Platform's accounts:update endpoint through the SDK's own authenticated
    client, replacing the MFA enrollments with none.
    [VERIFY] on the live project that this clears the enrollment."""
    from firebase_admin import _auth_client  # noqa: PLC0415 - only needed here

    client = _auth_client.Client(_get_app())
    client._user_manager._make_request("post", "/accounts:update", json={"localId": uid, "mfa": {"enrollments": []}})


def disable_user(uid: str) -> None:
    _get_app()
    fb_auth.update_user(uid, disabled=True)


def enable_user(uid: str) -> None:
    _get_app()
    fb_auth.update_user(uid, disabled=False)


def reset_password(uid: str, new_password: str) -> None:
    _get_app()
    fb_auth.update_user(uid, password=new_password)


def delete_user(uid: str) -> None:
    """Deletes the login. Already gone is fine, so a student deletion that
    stopped partway can simply be run again."""
    _get_app()
    try:
        fb_auth.delete_user(uid)
    except fb_auth.UserNotFoundError:
        pass


def verify_id_token(token: str) -> dict:
    """Returns the decoded token claims, including role/student_id custom
    claims. Raises firebase_admin.auth errors on an invalid/expired token.

    check_revoked=True also refuses tokens of disabled accounts and tokens
    issued before a password reset. Without it, a deactivated student's
    existing sign-in would keep working for up to an hour (the token
    lifetime). It costs one extra Identity Platform lookup per request."""
    _get_app()
    return fb_auth.verify_id_token(token, check_revoked=True)

"""Creates the Write Better admin account, or makes an existing account the admin.

Run once during setup, signed in to gcloud as a project owner:

    GOOGLE_CLOUD_PROJECT=write-better-app python infra/create_admin.py <admin email>

If no account has that email, it creates one with no password and prints a
one-time link to set it (nobody types a password into this script). Either
way it sets the "admin" role. Then sign in at /sign-in: the app asks you to
verify the email and set up an authenticator app.

Refuses to turn a student or teacher account into the admin: use a
separate email for the admin. Safe to run again: it prints the account's
state and only writes what's missing.
"""

import os
import subprocess
import sys

import firebase_admin
from firebase_admin import auth, credentials
from google.oauth2.credentials import Credentials


class GcloudCredential(credentials.Base):
    """Your own gcloud sign-in (a short-lived access token), so no
    service-account key or application-default login is needed."""

    def __init__(self, project: str):
        token = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
        self._credential = Credentials(token, quota_project_id=project)

    def get_credential(self):
        return self._credential


def init(project: str) -> None:
    firebase_admin.initialize_app(GcloudCredential(project), options={"projectId": project})


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    email = sys.argv[1].strip()
    init(os.environ["GOOGLE_CLOUD_PROJECT"])

    created = False
    try:
        user = auth.get_user_by_email(email)
        print(f"Found {email}: role {(user.custom_claims or {}).get('role')!r}, "
              f"email verified: {user.email_verified}, disabled: {user.disabled}")
    except auth.UserNotFoundError:
        user = auth.create_user(email=email)
        created = True
        print(f"Created {email} (no password yet).")

    role = (user.custom_claims or {}).get("role")
    if role is not None and role != "admin":
        sys.exit(f"This account is a {role}. Use a separate email for the admin.")
    if role != "admin":
        auth.set_custom_user_claims(user.uid, {"role": "admin"})
        print('Set role "admin".')
    else:
        print("Already the admin.")
    if created:
        print("\nOpen this one-time link to set your password, then sign in at /sign-in:")
        print(auth.generate_password_reset_link(email))


if __name__ == "__main__":
    main()

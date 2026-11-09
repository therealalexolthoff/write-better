"""Creates the Write Better admin account, or makes an existing account the admin.

Run once during setup (needs `gcloud auth application-default login` first):

    GOOGLE_CLOUD_PROJECT=write-better-app python infra/create_admin.py <admin email>

If no account has that email, it asks for a password (at least 12
characters, typed twice, never shown or stored here) and creates one.
Either way it sets the "admin" role. Then sign in at /sign-in: the app
asks you to verify the email and set up an authenticator app.

Refuses to turn a student or teacher account into the admin: use a
separate email for the admin. Safe to run again: it prints the account's
state and only writes what's missing.
"""

import getpass
import os
import sys

import firebase_admin
from firebase_admin import auth

MIN_PASSWORD = 12


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    email = sys.argv[1].strip()
    firebase_admin.initialize_app(options={"projectId": os.environ["GOOGLE_CLOUD_PROJECT"]})

    try:
        user = auth.get_user_by_email(email)
        print(f"Found {email}: role {(user.custom_claims or {}).get('role')!r}, "
              f"email verified: {user.email_verified}, disabled: {user.disabled}")
    except auth.UserNotFoundError:
        password = getpass.getpass(f"New password for {email} (at least {MIN_PASSWORD} characters): ")
        if len(password) < MIN_PASSWORD:
            sys.exit("Too short. Nothing was created.")
        if getpass.getpass("Type it again: ") != password:
            sys.exit("The passwords don't match. Nothing was created.")
        user = auth.create_user(email=email, password=password)
        print(f"Created {email}.")

    role = (user.custom_claims or {}).get("role")
    if role == "admin":
        print("Already the admin - nothing to do.")
        return
    if role is not None:
        sys.exit(f"This account is a {role}. Use a separate email for the admin.")
    auth.set_custom_user_claims(user.uid, {"role": "admin"})
    print('Set role "admin". Sign in at /sign-in to verify the email and set up an authenticator app.')


if __name__ == "__main__":
    main()

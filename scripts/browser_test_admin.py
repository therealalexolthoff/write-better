"""The admin-side steps of scripts/browser_test.mjs: approve <email> | cleanup <email>.
Uses your gcloud sign-in (infra/create_admin.py)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "infra"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from create_admin import init, GcloudCredential  # noqa: E402
from firebase_admin import auth  # noqa: E402
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "write-better-app")
init(PROJECT)
action, email = sys.argv[1:]
if action == "links":  # a teacher the admin created, and their one-time links
    user = auth.create_user(email=email, display_name="Link Test")
    auth.set_custom_user_claims(user.uid, {"role": "teacher"})
    from api.app.identity import action_link_path  # noqa: PLC0415
    print(os.environ["APP"] + action_link_path(auth.generate_password_reset_link(email)))
    # As the email sent from the browser carries it: Google's page, with the app's key.
    print(auth.generate_email_verification_link(email).replace("apiKey=&", f"apiKey={os.environ['KEY']}&"))
elif action == "verified":
    print("verified" if auth.get_user_by_email(email).email_verified else "not verified")
elif action == "approve":  # what the admin's Approve button and the email link do
    user = auth.get_user_by_email(email)
    auth.set_custom_user_claims(user.uid, {"role": "teacher"})
    auth.update_user(user.uid, email_verified=True)
    print("approved", user.uid)
else:
    from google.cloud import firestore
    db = firestore.Client(project=PROJECT, credentials=GcloudCredential(PROJECT).get_credential())
    try:
        user = auth.get_user_by_email(email)
        db.collection("signup_requests").document(user.uid).delete()
        db.collection("teachers").document(user.uid).delete()
        auth.delete_user(user.uid)
        print("deleted", user.uid)
    except auth.UserNotFoundError:
        print("nothing to delete")

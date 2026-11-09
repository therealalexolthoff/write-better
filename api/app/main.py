"""API service entry point.

Health checks, the public login config, the routers built phase by phase
(see docs/BUILD_PLAN.md), and the built React app from web/dist.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shared.logs import catch_unexpected_errors

from .security_headers import add_security_headers

from .admin import router as admin_router
from .assignments import router as assignments_router
from .classes import router as classes_router
from .config import settings
from .exercises import router as exercises_router
from .harness_client import call_harness_health
from .overview import router as overview_router
from .progress import router as progress_router
from .review import router as review_router
from .signup import router as signup_router
from .students import router as students_router
from .writing import router as writing_router

app = FastAPI(title="Write Better API")
catch_unexpected_errors(app)  # no tracebacks in the logs: they can quote student text
add_security_headers(app)
app.include_router(classes_router)
app.include_router(assignments_router)
app.include_router(students_router)
app.include_router(exercises_router)
app.include_router(review_router)
app.include_router(writing_router)
app.include_router(overview_router)
app.include_router(progress_router)
app.include_router(signup_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/harness")
def health_harness() -> dict:
    """Confirms the API can reach the private harness service."""
    try:
        return call_harness_health()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"harness unreachable: {exc}") from exc


@app.get("/config")
def public_config() -> dict:
    """What the login screen needs to talk to Identity Platform. No auth:
    the page needs this before anyone has signed in."""
    return {"firebase": {"apiKey": settings.firebase_api_key, "authDomain": settings.firebase_auth_domain}}


# The React app (docs/ARCHITECTURE.md section 2: served from this service).
# Each page path gets the app's index.html, so a reload or a shared link
# works; the app then picks the page (web/src/router.tsx - keep PAGES in
# step with PATHS there). Only these exact paths: an unknown API path still
# answers 404. Static files are mounted last so every API route above takes
# precedence. In local dev the folder doesn't exist and Vite's dev server
# is used instead.
PAGES = ("/privacy", "/sign-in", "/sign-up", "/app")  # "/" is served by the static mount
_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if _WEB_DIST.is_dir():

    def _index() -> FileResponse:
        return FileResponse(_WEB_DIST / "index.html")

    for _page in PAGES:
        app.add_api_route(_page, _index, methods=["GET"], include_in_schema=False)
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="web")

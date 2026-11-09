"""Security headers on every response (docs/SECURITY_REVIEW.md).

- Content-Security-Policy: scripts, styles and data only from this site and
  the Identity Platform endpoints the sign-in uses; photos from this site,
  Cloud Storage's signed links, and the browser's own previews (blob:,
  data:); no plugins; and no other site may show Write Better in a frame
  (clickjacking).
- HSTS: browsers only ever use HTTPS.
- nosniff, no referrer to other sites, and no camera, microphone or
  location access (photos come from a file picker, which needs none).
Styles allow 'unsafe-inline' only because React sets a few inline style
attributes (bar widths); scripts never allow inline code.
"""

from fastapi import FastAPI, Request

from .config import settings


def _policy() -> str:
    auth_domain = settings.firebase_auth_domain
    frames = f" https://{auth_domain}" if auth_domain else ""
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob: https://storage.googleapis.com",
            "connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com",
            f"frame-src 'self'{frames}",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


HEADERS = {
    "Content-Security-Policy": _policy(),
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def add_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        return response

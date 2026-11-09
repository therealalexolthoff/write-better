"""Monthly AI spend (Claude and Gemini): the hard cap and the admin's total.

docs/REQUIREMENTS.md FR-33: estimate before, enforce cap, record after.
Each call's cost is added with Firestore's atomic Increment, so calls for
different teachers at the same moment can't overwrite each other's totals.

Two small, accepted imprecisions with several teachers at once:
- the cap check (harness_ops.call_harness) reads the total before the call,
  so calls already running can take the month a few cents over the cap;
- the 75% alert is worked out from the total just after each write, so two
  calls crossing it together may send it twice (alerts are rate-limited to
  one an hour anyway, infra/monitoring.sh).
"""

from datetime import datetime, timezone

from google.cloud.firestore_v1.transforms import Increment

from shared.logs import log_event

from .firestore_client import get_db

# Spend past this share of the monthly cap is logged, which emails the
# admin (infra/monitoring.sh), well before AI feedback pauses.
WARN_AT = 0.75


def month_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def current_month_spend() -> float:
    doc = get_db().collection("spend").document(month_key()).get()
    if not doc.exists:
        return 0.0
    return doc.to_dict().get("total_usd", 0.0)


def record_spend(cost_usd: float, cap_usd: float) -> None:
    ref = get_db().collection("spend").document(month_key())
    ref.set({"total_usd": Increment(cost_usd), "calls": Increment(1)}, merge=True)
    after = ref.get().to_dict()["total_usd"]
    before = after - cost_usd
    if before < WARN_AT * cap_usd <= after:
        log_event("spend_threshold", "WARNING", month_spend_usd=round(after, 2), cap_usd=cap_usd)


def recent_months(count: int = 6) -> list[dict]:
    """Totals for the most recent months that had any AI use, newest first."""
    months = [{"month": doc.id, **doc.to_dict()} for doc in get_db().collection("spend").stream()]
    months.sort(key=lambda m: m["month"], reverse=True)
    return [{"month": m["month"], "total_usd": m.get("total_usd", 0.0), "calls": m.get("calls", 0)} for m in months[:count]]

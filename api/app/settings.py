"""The settings doc: a single Firestore document holding tunable config.

Minimal for now - just the spend cap and a conservative pre-call cost
estimate. Per-operation model names and real token budgets get added
when real Claude is wired in (docs/BUILD_PLAN.md Phase 3, second half);
adding them now would be config for a capability that doesn't exist yet.
See docs/ARCHITECTURE.md's settings schema for the eventual full shape.
"""

from pydantic import BaseModel

from .firestore_client import get_db


# The whole project must stay under $20 a month (CLAUDE.md), hosting
# included, so the AI cap can never be set above this.
MAX_CAP_USD = 20.0


class Settings(BaseModel):
    # Leaves room under $20 for everything else (docs/BUILD_PLAN.md).
    monthly_cap_usd: float = 15.0
    # A conservative fixed estimate used for the pre-call cap check, until
    # real per-operation token budgets exist (see module docstring).
    estimated_cost_per_call_usd: float = 0.05
    # How many recent approved submissions the learner profile counts
    # (docs/REQUIREMENTS.md FR-30).
    profile_window: int = 5


def get_settings() -> Settings:
    doc = get_db().collection("settings").document("global").get()
    if not doc.exists:
        return Settings()
    return Settings(**doc.to_dict())


def set_monthly_cap(cap_usd: float) -> None:
    get_db().collection("settings").document("global").set({"monthly_cap_usd": cap_usd}, merge=True)

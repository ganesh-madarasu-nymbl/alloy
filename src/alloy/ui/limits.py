"""Guards for a public deployment that shares one model key and one Bond login with every visitor."""

import hmac
import json
from datetime import date

from alloy.config import Settings


def live_unlocked(settings: Settings, entered: str) -> bool:
    if not settings.live_passcode:
        return True
    return hmac.compare_digest(entered.encode(), settings.live_passcode.encode())


def _usage(settings: Settings) -> dict:
    path = settings.cache_dir / "live_usage.json"
    return json.loads(path.read_text()) if path.exists() else {}


def live_runs_left(settings: Settings, today: date | None = None) -> int:
    day = (today or date.today()).isoformat()
    try:
        used = int(_usage(settings).get(day, 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0  # an unreadable counter must not hand out unlimited live runs
    return max(settings.live_runs_per_day - used, 0)


def record_live_run(settings: Settings, today: date | None = None) -> None:
    day = (today or date.today()).isoformat()
    try:
        used = int(_usage(settings).get(day, 0))
    except (OSError, ValueError, TypeError, AttributeError):
        used = settings.live_runs_per_day
    # Only today's count matters; older days are dropped.
    (settings.cache_dir / "live_usage.json").write_text(json.dumps({day: used + 1}))

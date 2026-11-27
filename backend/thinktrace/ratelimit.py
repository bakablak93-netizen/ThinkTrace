"""Request limits for the public demo.

Applied to the endpoints that will call the LLM in stage 2 (submit step: auto hint /
unknown-error analysis; hint; report text). Without an API key everything runs on
templates, the limits still protect the server from scripted abuse.

Two counters, both in memory of a single process:
  * per session   -- RATE_LIMIT_PER_SESSION requests per session id (lifetime);
  * per day       -- RATE_LIMIT_PER_DAY requests for the whole service per UTC day.
Over the limit the endpoint answers 429 {"error": "rate_limited"}.

Limitations (by design, documented in README): counters reset when the process restarts
(on free hosting that happens after idle spin-down), and they are not shared between
several instances. For a real LLM key also set a spending limit at the provider.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class RateLimiter:
    def __init__(self, per_session: int, per_day: int, today: Callable[[], str] = _utc_day):
        self.per_session = per_session
        self.per_day = per_day
        self._today = today
        self._lock = threading.Lock()
        self._sessions: dict[str, int] = defaultdict(int)
        self._day = ""
        self._day_count = 0

    def hit(self, session_id: str) -> bool:
        """Count one request. False (and nothing counted) if a limit is reached."""
        with self._lock:
            day = self._today()
            if day != self._day:
                self._day, self._day_count = day, 0
            if self._day_count >= self.per_day or self._sessions[session_id] >= self.per_session:
                return False
            self._day_count += 1
            self._sessions[session_id] += 1
            return True

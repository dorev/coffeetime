"""Limite anti-abus : N actions par personne sur une fenêtre glissante."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable


class RateLimiter:
    def __init__(
        self,
        max_actions: int,
        window_seconds: float = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_actions = max_actions
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Enregistre une action et retourne False si la limite est dépassée."""
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.max_actions:
            return False
        hits.append(now)
        return True

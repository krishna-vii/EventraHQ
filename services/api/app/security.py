"""Single-worker admission limits; hosted edge must also enforce per-client limits."""
from collections import deque
import time


class RateLimit:
    def __init__(self):
        self.windows = {}

    def allow(self, key: str, maximum: int, seconds: int = 60):
        now = time.monotonic()
        if len(self.windows) > 2048:
            self.windows = {k: v for k,v in self.windows.items() if v and v[-1] > now-seconds}
            if len(self.windows) > 2048:
                return False
        window = self.windows.setdefault(key, deque())
        while window and window[0] <= now-seconds:
            window.popleft()
        if len(window) >= maximum:
            return False
        window.append(now)
        return True

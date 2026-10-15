import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class AttemptState:
    failed_count: int = 0
    first_attempt_time: float = 0.0
    locked_until: float = 0.0


class LoginRateLimiter:
    """In-memory rate limiter and account lockout protection for login attempts.
    
    Protects against brute-force password guessing by enforcing consecutive
    failure thresholds and temporary lockout periods.
    """

    def __init__(
        self,
        max_failed_attempts: int = 5,
        lockout_duration_seconds: int = 900,  # 15 minutes
        window_seconds: int = 900,
    ):
        self.max_failed_attempts = max_failed_attempts
        self.lockout_duration_seconds = lockout_duration_seconds
        self.window_seconds = window_seconds
        self._states: dict[str, AttemptState] = {}
        self._lock = Lock()

    def _normalize_key(self, key: str) -> str:
        return key.strip().lower()

    def is_locked(self, key: str) -> tuple[bool, int]:
        """Check if a key is currently locked out.
        
        Returns:
            (is_locked, remaining_lockout_seconds)
        """
        norm_key = self._normalize_key(key)
        now = time.time()
        with self._lock:
            state = self._states.get(norm_key)
            if not state:
                return False, 0

            if state.locked_until > now:
                remaining = int(state.locked_until - now) + 1
                return True, remaining

            # Lockout expired, reset state
            if state.locked_until > 0:
                self._states.pop(norm_key, None)

            return False, 0

    def record_failure(
        self,
        key: str,
        max_attempts: int | None = None,
        lockout_seconds: int | None = None,
    ) -> tuple[bool, int]:
        """Record a failed login attempt.
        
        Returns:
            (is_now_locked, remaining_attempts_or_lockout_seconds)
        """
        norm_key = self._normalize_key(key)
        limit = max_attempts or self.max_failed_attempts
        lockout_dur = lockout_seconds or self.lockout_duration_seconds
        now = time.time()

        with self._lock:
            state = self._states.get(norm_key)
            if not state:
                state = AttemptState(failed_count=0, first_attempt_time=now)
                self._states[norm_key] = state

            # If the sliding window has expired since first attempt, reset counter
            if now - state.first_attempt_time > self.window_seconds:
                state.failed_count = 0
                state.first_attempt_time = now

            state.failed_count += 1

            if state.failed_count >= limit:
                state.locked_until = now + lockout_dur
                return True, lockout_dur

            remaining_attempts = limit - state.failed_count
            return False, remaining_attempts

    def record_success(self, key: str) -> None:
        """Reset failed attempt counters upon successful login."""
        norm_key = self._normalize_key(key)
        with self._lock:
            self._states.pop(norm_key, None)

    def reset(self) -> None:
        """Clear all rate limit states (useful for testing)."""
        with self._lock:
            self._states.clear()


# Global singleton instance for auth routes
login_limiter = LoginRateLimiter()

"""Shared multi-key rotation pool used by both llm/providers/groq.py and
llm/providers/gemini.py -- extracted so "rotate to the next configured key
on a rate limit, raise a terminal error once every key is exhausted" lives
in exactly one place instead of two independently maintained copies that
could drift apart. Provider-specific concerns (which SDK exception means
"rate limited", building the SDK client, the actual retry-with-backoff
loop for transient errors) stay in each provider's own module; this class
owns only the index/lock state and the rotate-or-exhaust decision, plus
its logging -- deliberately narrow, not a general provider abstraction.

Not thread-local -- shared across threads on purpose (matching both
providers' pre-refactor behavior): one thread's discovery that a key is
exhausted immediately benefits every other concurrently-running caller
instead of each independently re-discovering the same rate limit. Every
INCREMENT goes through rotate() under its own lock; a bare read of
current_index elsewhere (e.g. a provider's _client() cache lookup) is
safe enough under CPython's GIL for this purpose -- worst case under a
race is one thread briefly using a slightly stale index, which
self-corrects on its next call.
"""

from __future__ import annotations

import logging
import threading


class KeyRotationPool:
    """Tracks which configured API key (by 0-based position) is
    currently active for one provider. Rotation is a one-way,
    process-wide ratchet: it never un-rotates back to an earlier key
    within a process's lifetime. This class never sees the actual key
    values -- callers pass only `key_count`, so there is no way for it
    to log or otherwise leak a secret.
    """

    def __init__(self, *, provider_label: str, logger: logging.Logger) -> None:
        self._provider_label = provider_label
        self._logger = logger
        self._lock = threading.Lock()
        self._current_index = 0

    @property
    def current_index(self) -> int:
        return self._current_index

    def rotate(self, *, key_count: int) -> bool:
        """Advances the pointer to the next configured key. Returns True
        if it did (a next key existed), False if the current key was
        already the last one configured -- the caller's cue to give up
        on this provider entirely for the current request and raise a
        terminal, failover-eligible error.

        Logs which key INDEX was exhausted and which index it's rotating
        to (1-based, human-readable, e.g. "Groq API key #2") -- never a
        key value.
        """
        with self._lock:
            exhausted_position = self._current_index + 1
            if self._current_index + 1 < key_count:
                self._current_index += 1
                self._logger.warning(
                    "%s API key #%d rate-limited; rotating to key #%d of %d configured",
                    self._provider_label,
                    exhausted_position,
                    self._current_index + 1,
                    key_count,
                )
                return True
            self._logger.warning(
                "%s API key #%d rate-limited; all %d configured %s API key(s) exhausted, "
                "failing over to the next provider",
                self._provider_label,
                exhausted_position,
                key_count,
                self._provider_label,
            )
            return False

    def reset(self) -> None:
        """Test-only: resets the pointer back to the first configured key."""
        with self._lock:
            self._current_index = 0

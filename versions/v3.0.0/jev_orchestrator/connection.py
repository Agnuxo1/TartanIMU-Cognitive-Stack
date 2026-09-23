"""Shared, environment-configured TypeSafe/Jev connection for every agent."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from functools import lru_cache
import os
from typing import Any

from typesafe_sdk import TypeSafeClient

from .config import TYPESAFE_MODEL, TYPESAFE_TIMEOUT_SECONDS


class JevConnectionError(RuntimeError):
    """Raised when no usable TypeSafe credential is configured."""


def _candidate_keys() -> Iterator[str]:
    """Yield only credentials explicitly supplied by the calling process."""
    seen: set[str] = set()
    for env_name in ("TYPESAFE_API_KEY", "TYPESAFE_API_KEY_1", "TYPESAFE_API_KEY_2", "TYPESAFE_API_KEY_3"):
        value = os.environ.get(env_name, "").strip()
        if value and value not in seen:
            seen.add(value)
            yield value


def resolve_jev_keys() -> tuple[str, ...]:
    """Return configured keys or raise a non-secret diagnostic error."""
    keys = tuple(_candidate_keys())
    if not keys:
        raise JevConnectionError(
            "No TypeSafe credential is configured. Set TYPESAFE_API_KEY in "
            "the agent process before requesting a remote JEV decision."
        )
    return keys


def _retryable_auth_error(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    if status in {401, 403}:
        return True
    name = type(error).__name__.lower()
    return "auth" in name or "unauthor" in name or "forbidden" in name


class JevClient:
    """Failover facade with one System One entry point for every local agent."""

    def __init__(self, keys: tuple[str, ...] | None = None, *, timeout: float = TYPESAFE_TIMEOUT_SECONDS) -> None:
        self._keys = keys or resolve_jev_keys()
        self._timeout = timeout
        self._clients = [TypeSafeClient(api_key=key, model=TYPESAFE_MODEL, timeout=timeout) for key in self._keys]

    @property
    def credential_count(self) -> int:
        """Number of configured credentials, never the credentials themselves."""
        return len(self._clients)

    def system_one(
        self,
        *,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
        retry: Any | None = None,
        timeout: float | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any | None] | None = None,
        response_model: type[Any] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for index, client in enumerate(self._clients):
            try:
                return client.system_one(
                    state=state,
                    questions=questions,
                    model=model,
                    retry=retry,
                    timeout=timeout or self._timeout,
                    extra_headers=extra_headers,
                    extra_body=extra_body,
                    response_model=response_model,
                )
            except Exception as error:  # SDK error types vary between releases.
                last_error = error
                if index + 1 >= len(self._clients) or not _retryable_auth_error(error):
                    raise
        assert last_error is not None
        raise last_error

    def close(self) -> None:
        for client in self._clients:
            client.close()

    def __enter__(self) -> "JevClient":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: Any) -> None:
        self.close()


def create_jev_client(*, timeout: float = TYPESAFE_TIMEOUT_SECONDS) -> JevClient:
    """Create the shared connection facade for a new agent or process."""
    return JevClient(timeout=timeout)


@lru_cache(maxsize=1)
def get_jev_client() -> JevClient:
    """Return one process-local client for agents that share a process."""
    return create_jev_client()

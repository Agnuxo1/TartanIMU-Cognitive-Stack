"""Secure TypeSafe credential profiles for the local JEV connector.

Secrets are resolved from process memory or Windows Credential Manager.  The
legacy file fallback is retained only for recovery compatibility and is never
used when a vault credential is available.
"""
from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROFILE = "profile-a"
PROFILE_ACCOUNTS = {
    "profile-a": "Profile A",
    "profile-b": "Profile B",
    "profile-c": "Profile C",
}
CREDENTIAL_TARGET_PREFIX = "TypeSafe/JEV/"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


@dataclass(frozen=True)
class Credential:
    """A resolved credential; ``repr`` deliberately redacts the secret."""

    value: str
    source: str
    profile: str
    account: str | None = None

    def __repr__(self) -> str:  # pragma: no cover - defensive redaction
        return f"Credential(source={self.source!r}, profile={self.profile!r}, account={self.account!r})"


class CredentialStoreError(RuntimeError):
    """Raised when Windows Credential Manager cannot store a credential."""


class _FileTime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FileTime),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def normalize_profile(profile: str | None = None) -> str:
    """Return a safe profile slug, accepting a configured alias or label."""
    raw = (profile or os.environ.get("TYPESAFE_PROFILE") or os.environ.get("TYPESAFE_ACCOUNT") or DEFAULT_PROFILE).strip().lower()
    if raw in {"default", "current"}:
        return DEFAULT_PROFILE
    for alias, account in PROFILE_ACCOUNTS.items():
        if raw == alias or raw == account.casefold():
            return alias
    slug = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    if not slug:
        raise ValueError("TYPESAFE_PROFILE must contain a valid profile name")
    return slug[:80]


def profile_account(profile: str | None = None) -> str | None:
    """Return the non-secret account label associated with a profile."""
    return PROFILE_ACCOUNTS.get(normalize_profile(profile))


def credential_target(profile: str | None = None) -> str:
    return CREDENTIAL_TARGET_PREFIX + normalize_profile(profile)


def known_profiles() -> dict[str, str]:
    """Return profile labels only; no credential material is included."""
    return dict(PROFILE_ACCOUNTS)


def _advapi32() -> ctypes.WinDLL:
    if os.name != "nt":
        raise CredentialStoreError("Windows Credential Manager is unavailable on this platform")
    return ctypes.WinDLL("advapi32", use_last_error=True)


def read_windows_credential(profile: str | None = None) -> str | None:
    """Read one generic credential without exposing it in logs or exceptions."""
    if os.name != "nt":
        return None
    advapi = _advapi32()
    cred_read = advapi.CredReadW
    cred_read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(_CredentialW))]
    cred_read.restype = wintypes.BOOL
    cred_free = advapi.CredFree
    cred_free.argtypes = [ctypes.c_void_p]
    cred_free.restype = None
    result = ctypes.POINTER(_CredentialW)()
    if not cred_read(credential_target(profile), CRED_TYPE_GENERIC, 0, ctypes.byref(result)):
        return None
    try:
        record = result.contents
        if not record.CredentialBlob or not record.CredentialBlobSize:
            return None
        raw = ctypes.string_at(record.CredentialBlob, record.CredentialBlobSize)
        return raw.decode("utf-8").strip() or None
    except (UnicodeDecodeError, ValueError):
        return None
    finally:
        cred_free(result)


def write_windows_credential(profile: str, value: str, *, account: str | None = None) -> None:
    """Persist one credential in the current Windows user's credential vault."""
    if os.name != "nt":
        raise CredentialStoreError("Windows Credential Manager is unavailable on this platform")
    secret = value.strip()
    if not secret or len(secret.encode("utf-8")) > 512:
        raise CredentialStoreError("The TypeSafe credential is empty or exceeds the vault limit")
    canonical = normalize_profile(profile)
    blob = secret.encode("utf-8")
    blob_buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    target = credential_target(canonical)
    username = account or profile_account(canonical) or canonical
    record = _CredentialW(
        Flags=0,
        Type=CRED_TYPE_GENERIC,
        TargetName=target,
        Comment="TypeSafe JEV connector credential",
        LastWritten=_FileTime(),
        CredentialBlobSize=len(blob),
        CredentialBlob=ctypes.cast(blob_buffer, ctypes.POINTER(ctypes.c_ubyte)),
        Persist=CRED_PERSIST_LOCAL_MACHINE,
        AttributeCount=0,
        Attributes=None,
        TargetAlias=None,
        UserName=username,
    )
    advapi = _advapi32()
    cred_write = advapi.CredWriteW
    cred_write.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
    cred_write.restype = wintypes.BOOL
    if not cred_write(ctypes.byref(record), 0):
        # Do not include the target, blob, or OS error text: callers should be
        # able to surface this safely even when logs are shared.
        raise CredentialStoreError("Windows Credential Manager rejected the TypeSafe credential")


def _profile_env_name(profile: str) -> str:
    return "TYPESAFE_API_KEY_" + re.sub(r"[^A-Z0-9]", "_", profile.upper())


def _is_general_secret_dump(path: Path) -> bool:
    """Reject broad password/API inventories as legacy key sources."""
    name = path.name.casefold()
    return name.startswith("utilidades_") or name in {"credentials.txt", "passwords.txt", "secrets.txt"}


def resolve_credential(
    *,
    root: Path | None = None,
    profile: str | None = None,
    legacy_candidates: list[Path] | None = None,
) -> Credential | None:
    """Resolve a credential with safe precedence and bounded legacy fallback.

    Precedence is explicit process environment, profile-specific environment,
    Windows Credential Manager, then the old file path for compatibility.  The
    file fallback can be disabled with ``JEV_ALLOW_LEGACY_SECRET_FILE=0``.
    """
    canonical = normalize_profile(profile)
    account = profile_account(canonical)
    environment_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if environment_key:
        return Credential(environment_key, "environment:TYPESAFE_API_KEY", canonical, account)

    profile_key = os.environ.get(_profile_env_name(canonical), "").strip()
    if profile_key:
        return Credential(profile_key, f"environment:{_profile_env_name(canonical)}", canonical, account)

    vault_key = read_windows_credential(canonical)
    if vault_key:
        return Credential(vault_key, f"vault:{credential_target(canonical)}", canonical, account)

    if os.environ.get("JEV_ALLOW_LEGACY_SECRET_FILE", "0") == "1":
        candidates = legacy_candidates or []
        if root is not None:
            candidates.append(root / "secrets" / "typesafe_api_key.txt")
        explicit = os.environ.get("JEV_TYPESAFE_KEY_FILE", "").strip()
        if explicit:
            candidates.insert(0, Path(explicit))
        for path in candidates:
            if _is_general_secret_dump(path):
                continue
            try:
                value = path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if value:
                return Credential(value, f"legacy-file:{path}", canonical, account)
    return None

"""Encrypted per-source credentials for unified Edge sources."""

from __future__ import annotations

import json
from pathlib import Path

from agent.config import AGENT_DIR
from agent.security.vault import decrypt, encrypt


SOURCES_VAULT_PATH = AGENT_DIR / "source_credentials.vault"


class CredentialError(ValueError):
    """Raised when a credential reference cannot be resolved."""


def load_credential(credential_id: str, path: Path = SOURCES_VAULT_PATH) -> tuple[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entry = raw[credential_id]
        return decrypt(entry["username"]), decrypt(entry["password"])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise CredentialError(f"credential {credential_id!r} is unavailable") from exc


def save_credential(credential_id: str, username: str, password: str, path: Path = SOURCES_VAULT_PATH) -> None:
    """Store credentials encrypted; callers must never place them in sources.json."""
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    data[credential_id] = {"username": encrypt(username), "password": encrypt(password)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)
    path.chmod(0o600)

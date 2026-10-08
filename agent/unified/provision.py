"""Local, operator-driven provisioning for encrypted unified DVR credentials."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from agent.unified.config import SOURCES_CONFIG_PATH, SourceConfigError, validate_config
from agent.unified.credentials import save_credential


def _load_raw(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceConfigError(f"cannot read {path}: {exc}") from exc


def _dvr_credential_ids(config: dict) -> set[str]:
    return {
        source["dvr"]["credential_id"]
        for source in config["sources"]
        if source["type"] == "dvr"
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a unified Ively Edge source configuration")
    parser.add_argument("--config", type=Path, default=SOURCES_CONFIG_PATH)
    parser.add_argument("--credential-id", help="Store one encrypted DVR credential and exit")
    parser.add_argument("--username")
    args = parser.parse_args(argv)

    try:
        raw = _load_raw(args.config)
        config = validate_config(raw)
    except SourceConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    ids = _dvr_credential_ids(config)
    requested = {args.credential_id} if args.credential_id else ids
    unknown = requested - ids
    if unknown:
        print(f"Unknown DVR credential id(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    for credential_id in sorted(requested):
        username = args.username or input(f"DVR username for {credential_id}: ").strip()
        password = getpass.getpass(f"DVR password for {credential_id}: ")
        if not username or not password:
            print(f"Credential {credential_id} was not saved: username and password are required.", file=sys.stderr)
            return 2
        save_credential(credential_id, username, password)
        print(f"Saved encrypted credential: {credential_id}")

    print("Credentials are stored in source_credentials.vault; sources.json contains no passwords.")
    print("Run the unified validation command before the controlled first service start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

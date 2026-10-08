"""Validated configuration for the single Ively Edge streaming service."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from agent.config import AGENT_DIR, HLS_SEGMENT_DURATION, load_path_prefix


SOURCES_CONFIG_PATH = Path(os.environ.get("IVELY_SOURCES_CONFIG", AGENT_DIR / "sources.json"))
SUPPORTED_SOURCE_TYPES = {"nvr", "dvr", "rtsp"}
SUPPORTED_VIDEO_MODES = {"copy", "transcode"}


class SourceConfigError(ValueError):
    """Raised when a unified Edge source configuration is invalid."""


def _positive_int(value: Any, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise SourceConfigError(f"{name} must be an integer") from exc
    if result < 1:
        raise SourceConfigError(f"{name} must be greater than zero")
    return result


def _safe_path(value: Any, name: str) -> str:
    result = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", result):
        raise SourceConfigError(f"{name} must contain only letters, digits, underscore, dot, or dash")
    return result


def hls_segment_seconds() -> int:
    match = re.fullmatch(r"\s*(\d+)s\s*", str(HLS_SEGMENT_DURATION))
    return max(1, int(match.group(1))) if match else 2


def normalized_media(media: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return browser-safe H.264 defaults aligned with the HLS segment duration."""
    raw = dict(media or {})
    fps = _positive_int(raw.get("fps", 15), "media.fps")
    mode = str(raw.get("video_mode", "transcode")).strip().lower()
    if mode not in SUPPORTED_VIDEO_MODES:
        raise SourceConfigError("media.video_mode must be copy or transcode")
    return {
        "video_mode": mode,
        "width": _positive_int(raw.get("width", 640), "media.width"),
        "height": _positive_int(raw.get("height", 360), "media.height"),
        "fps": fps,
        "bitrate": str(raw.get("bitrate", "768k")),
        "maxrate": str(raw.get("maxrate", "900k")),
        "bufsize": str(raw.get("bufsize", "1536k")),
        "gop": _positive_int(raw.get("gop", fps * hls_segment_seconds()), "media.gop"),
    }


def _merge_media(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(base)
    merged.update(dict(override or {}))
    return normalized_media(merged)


def _validate_source(raw: dict[str, Any], defaults: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SourceConfigError(f"sources[{index}] must be an object")
    source_type = str(raw.get("type") or "").strip().lower()
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise SourceConfigError(f"sources[{index}].type must be one of: nvr, dvr, rtsp")
    source_id = _safe_path(raw.get("id") or f"{source_type}-{index + 1}", f"sources[{index}].id")
    path = _safe_path(raw.get("path") or source_id, f"sources[{index}].path")
    result = {"id": source_id, "type": source_type, "path": path, "media": _merge_media(defaults, raw.get("media"))}

    if source_type == "dvr":
        dvr = raw.get("dvr")
        if not isinstance(dvr, dict):
            raise SourceConfigError(f"sources[{index}].dvr must be an object")
        if "username" in dvr or "password" in dvr:
            raise SourceConfigError(
                f"sources[{index}].dvr must use credential_id; plaintext credentials are not allowed"
            )
        host = str(dvr.get("host") or "").strip()
        credential_id = _safe_path(dvr.get("credential_id"), f"sources[{index}].dvr.credential_id")
        if not host or not credential_id:
            raise SourceConfigError(f"sources[{index}].dvr requires host and credential_id")
        result["dvr"] = {
            "host": host,
            "port": _positive_int(dvr.get("port", 554), f"sources[{index}].dvr.port"),
            "credential_id": credential_id,
            "channel": _positive_int(raw.get("channel"), f"sources[{index}].channel"),
            "url_templates": list(dvr.get("url_templates") or []),
        }
    elif source_type == "rtsp":
        url = str(raw.get("url") or "").strip()
        if not url.startswith("rtsp://"):
            raise SourceConfigError(f"sources[{index}].url must be an rtsp:// URL")
        result["url"] = url
    else:
        # NVR sources reuse the camera selection already managed by the
        # provision UI. Individual NVR source definitions are deliberately
        # rejected until the setup UI can create them without a second writer.
        if not raw.get("legacy_cameras", True):
            raise SourceConfigError(f"sources[{index}].nvr currently requires legacy_cameras=true")
        result["legacy_cameras"] = True
    return result


def validate_config(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SourceConfigError("sources config must be an object")
    sources = raw.get("sources")
    if not isinstance(sources, list) or not sources:
        raise SourceConfigError("sources must be a non-empty list")
    defaults = normalized_media(raw.get("media"))
    validated = [_validate_source(source, defaults, index) for index, source in enumerate(sources)]
    ids = [source["id"] for source in validated]
    paths = [source["path"] for source in validated]
    if len(ids) != len(set(ids)):
        raise SourceConfigError("source ids must be unique")
    if len(paths) != len(set(paths)):
        raise SourceConfigError("published paths must be unique")
    return {"version": 1, "path_prefix": str(raw.get("path_prefix") or load_path_prefix()), "media": defaults, "sources": validated}


def load_config(path: Path = SOURCES_CONFIG_PATH) -> dict[str, Any] | None:
    """Load sources.json. A missing file preserves the legacy NVR-only startup."""
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceConfigError(f"cannot read {path}: {exc}") from exc
    return validate_config(raw)


def save_config(raw: dict[str, Any], path: Path = SOURCES_CONFIG_PATH) -> dict[str, Any]:
    """Validate then atomically persist source metadata without credentials."""
    config = validate_config(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    path.chmod(0o600)
    return config

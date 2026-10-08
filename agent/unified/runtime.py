"""Single-process source orchestration for NVR-only, DVR-only, and combined sites."""

from __future__ import annotations

from typing import Any

from agent.camera.mediamtx_writer import generate
from agent.camera.worker_reload import build_worker_configs, load_cams
from agent.config import MEDIAMTX_CONFIG, RTSP_PORT
from agent.unified.config import SourceConfigError, load_config
from agent.unified.dvr import build_dvr_urls, publisher_command, redacted_dvr_urls


class UnifiedRuntime:
    """Build all workers under one manager and prepare paths without restarting MediaMTX."""

    def __init__(self, manager) -> None:
        self.manager = manager
        self.config: dict[str, Any] | None = None

    def is_enabled(self) -> bool:
        return load_config() is not None

    def build_worker_configs(self) -> list[dict[str, Any]]:
        config = load_config()
        if config is None:
            raise SourceConfigError("sources.json is not configured")
        self.config = config
        workers: list[dict[str, Any]] = []
        use_legacy_nvr = any(source["type"] == "nvr" and source.get("legacy_cameras", True) for source in config["sources"])
        legacy_worker_names: set[str] = set()
        if use_legacy_nvr:
            legacy_workers = build_worker_configs(load_cams())
            workers.extend(legacy_workers)
            legacy_worker_names = {worker["stream_name"] for worker in legacy_workers}
        for source in config["sources"]:
            if source["type"] == "dvr":
                output_url = f"rtsp://127.0.0.1:{RTSP_PORT}/{source['path']}"
                urls = build_dvr_urls(source["dvr"])
                workers.append({
                    "stream_name": source["path"],
                    "ffmpeg_cmd": publisher_command(urls[0], output_url, source["media"]),
                    "ffmpeg_cmds": [publisher_command(url, output_url, source["media"]) for url in urls],
                    "rtsp_urls": redacted_dvr_urls(source["dvr"]),
                    "expected_fps": float(source["media"]["fps"]),
                })
            elif source["type"] == "rtsp":
                output_url = f"rtsp://127.0.0.1:{RTSP_PORT}/{source['path']}"
                workers.append({
                    "stream_name": source["path"],
                    "ffmpeg_cmd": publisher_command(source["url"], output_url, source["media"]),
                    "expected_fps": float(source["media"]["fps"]),
                })
        if not workers:
            raise SourceConfigError("unified configuration produced no workers")
        names = [worker["stream_name"] for worker in workers]
        if len(names) != len(set(names)):
            raise SourceConfigError("legacy NVR paths conflict with a unified source path")
        self._legacy_worker_names = legacy_worker_names
        return workers

    def prepare_paths(self, workers: list[dict[str, Any]]) -> bool:
        """Write the complete publisher path set. It intentionally does not restart MediaMTX."""
        nvr_cams = load_cams() if any(source["type"] == "nvr" for source in self.config["sources"]) else []
        extra_paths = [
            worker["stream_name"]
            for worker in workers
            if worker["stream_name"] not in getattr(self, "_legacy_worker_names", set())
        ]
        return generate(nvr_cams, config_path=str(MEDIAMTX_CONFIG), extra_publisher_paths=extra_paths)

    def start(self) -> dict[str, Any]:
        workers = self.build_worker_configs()
        changed = self.prepare_paths(workers)
        started = self.manager.reload(workers)
        return {
            "ok": started == len(workers),
            "mode": "unified",
            "started": started,
            "total": len(workers),
            "stream_names": [worker["stream_name"] for worker in workers],
            "mediamtx_config_changed": changed,
            "mediamtx_restarted": False,
            "maintenance_restart_required": changed,
        }

    def status(self) -> dict[str, Any]:
        """Expose source metadata without returning RTSP credentials."""
        config = load_config()
        if config is None:
            return {"configured": False, "sources": []}
        return {
            "configured": True,
            "sources": [
                {
                    "id": source["id"],
                    "type": source["type"],
                    "path": source["path"],
                    "channel": source.get("channel"),
                    "dvr": {
                        key: value
                        for key, value in source.get("dvr", {}).items()
                        if key != "credential_id"
                    },
                    "media": source["media"],
                }
                for source in config["sources"]
            ],
        }

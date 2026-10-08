"""DVR RTSP source resolution and normalized FFmpeg publishing."""

from __future__ import annotations

import shlex
from urllib.parse import quote

from agent.unified.credentials import load_credential


DEFAULT_DVR_URL_TEMPLATES = (
    "rtsp://{username}:{password}@{host}:{port}/Streaming/Channels/{channel}01",
    "rtsp://{username}:{password}@{host}:{port}/Streaming/Channels/{channel}02",
    "rtsp://{username}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=0",
    "rtsp://{username}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=1",
)


def build_dvr_urls(dvr: dict) -> list[str]:
    username, password = load_credential(dvr["credential_id"])
    values = {
        "host": dvr["host"],
        "port": dvr["port"],
        "channel": dvr["channel"],
        "username": quote(username, safe=""),
        "password": quote(password, safe=""),
    }
    templates = dvr.get("url_templates") or DEFAULT_DVR_URL_TEMPLATES
    return [str(template).format(**values) for template in templates]


def redacted_dvr_urls(dvr: dict) -> list[str]:
    templates = dvr.get("url_templates") or DEFAULT_DVR_URL_TEMPLATES
    values = {
        "host": dvr["host"], "port": dvr["port"], "channel": dvr["channel"],
        "username": "<credential>", "password": "<credential>",
    }
    return [str(template).format(**values) for template in templates]


def publisher_command(input_url: str, output_url: str, media: dict) -> str:
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "repeat+warning",
        "-rtsp_transport", "tcp", "-rtsp_flags", "prefer_tcp",
        "-timeout", "10000000", "-fflags", "+genpts+discardcorrupt",
        "-err_detect", "ignore_err", "-ec", "guess_mvs+deblock",
        "-use_wallclock_as_timestamps", "1", "-analyzeduration", "5000000",
        "-probesize", "5000000", "-reorder_queue_size", "64", "-max_delay", "500000",
        "-i", input_url, "-map", "0:v:0", "-an",
    ]
    if media["video_mode"] == "copy":
        command.extend(["-c:v", "copy"])
    else:
        width, height, fps, gop = media["width"], media["height"], media["fps"], media["gop"]
        command.extend([
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            "-pix_fmt", "yuv420p", "-profile:v", "main", "-level:v", "3.1",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(fps), "-fps_mode", "cfr", "-g", str(gop), "-keyint_min", str(gop),
            "-sc_threshold", "0", "-x264-params", "scenecut=0:bframes=0:repeat-headers=1",
            "-b:v", media["bitrate"], "-maxrate", media["maxrate"], "-bufsize", media["bufsize"],
        ])
    command.extend(["-f", "rtsp", "-rtsp_transport", "tcp", "-pkt_size", "1200", output_url])
    return " ".join(shlex.quote(item) for item in command)

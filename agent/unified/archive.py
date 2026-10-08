"""Hikvision DVR archive search without copying recordings onto the Edge device."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

import requests
from requests.auth import HTTPDigestAuth

from agent.unified.credentials import load_credential


class ArchiveSearchError(RuntimeError):
    """Raised when an upstream DVR archive search cannot be completed."""


def _iso_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ArchiveSearchError("archive timestamps must include a timezone, for example Z")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _xml_text(node: ElementTree.Element, name: str) -> str:
    value = node.findtext(f"{{*}}{name}") or ""
    return value.strip()


def _request_xml(channel: int, start_time: str, end_time: str, max_results: int) -> bytes:
    root = ElementTree.Element("CMSearchDescription")
    ElementTree.SubElement(root, "searchID").text = "ively-unified-archive"
    tracks = ElementTree.SubElement(root, "trackList")
    ElementTree.SubElement(tracks, "trackID").text = str(100 + int(channel))
    spans = ElementTree.SubElement(root, "timeSpanList")
    span = ElementTree.SubElement(spans, "timeSpan")
    ElementTree.SubElement(span, "startTime").text = _iso_utc(start_time)
    ElementTree.SubElement(span, "endTime").text = _iso_utc(end_time)
    ElementTree.SubElement(root, "maxResults").text = str(max(1, min(int(max_results), 64)))
    ElementTree.SubElement(root, "searchResultPostion").text = "0"
    metadata = ElementTree.SubElement(root, "metadataList")
    ElementTree.SubElement(metadata, "metadataDescriptor").text = "//recordType.meta.std-cgi.com"
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def search_recordings(source: dict[str, Any], start_time: str, end_time: str, max_results: int = 32) -> list[dict[str, str]]:
    if source.get("type") != "dvr":
        raise ArchiveSearchError("archive search is available only for DVR sources")
    dvr = source["dvr"]
    username, password = load_credential(dvr["credential_id"])
    url = f"http://{dvr['host']}/ISAPI/ContentMgmt/search"
    try:
        response = requests.post(
            url,
            data=_request_xml(dvr["channel"], start_time, end_time, max_results),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            auth=HTTPDigestAuth(username, password),
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ArchiveSearchError(f"DVR archive request failed: {exc}") from exc
    if response.status_code != 200:
        raise ArchiveSearchError(f"DVR archive search returned HTTP {response.status_code}")
    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise ArchiveSearchError("DVR archive response was not valid XML") from exc
    if root.tag.rsplit("}", 1)[-1] != "CMSearchResult":
        raise ArchiveSearchError(_xml_text(root, "statusString") or "DVR archive search failed")

    results: list[dict[str, str]] = []
    for item in root.findall(".//{*}searchMatchItem"):
        descriptor = item.find("{*}mediaSegmentDescriptor")
        span = item.find("{*}timeSpan")
        if descriptor is None or span is None:
            continue
        results.append({
            "track_id": _xml_text(item, "trackID"),
            "start_time": _xml_text(span, "startTime"),
            "end_time": _xml_text(span, "endTime"),
            "codec": _xml_text(descriptor, "codecType"),
            "playback_uri": _xml_text(descriptor, "playbackURI"),
        })
    return results

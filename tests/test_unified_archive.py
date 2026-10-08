from xml.etree import ElementTree

from agent.unified.archive import _request_xml


def test_archive_search_request_uses_dvr_track_id_and_utc_times():
    payload = _request_xml(1, "2026-09-28T18:30:00Z", "2026-09-28T19:30:00Z", 99)
    root = ElementTree.fromstring(payload)

    assert root.findtext("trackList/trackID") == "101"
    assert root.findtext("timeSpanList/timeSpan/startTime") == "2026-09-28T18:30:00Z"
    assert root.findtext("maxResults") == "64"

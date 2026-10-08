import pytest

from agent.unified.config import SourceConfigError, hls_segment_seconds, validate_config


def dvr_source(path="customer_site_analog_dvr_ch1_low"):
    return {
        "id": "dvr-ch1",
        "type": "dvr",
        "path": path,
        "channel": 1,
        "dvr": {"host": "192.168.1.6", "credential_id": "site-dvr"},
    }


def test_dvr_defaults_to_normalized_h264_profile():
    config = validate_config({"sources": [dvr_source()]})
    media = config["sources"][0]["media"]

    assert media["video_mode"] == "transcode"
    assert media["gop"] == media["fps"] * hls_segment_seconds()


def test_dvr_config_rejects_plaintext_credentials():
    source = dvr_source()
    source["dvr"]["username"] = "admin"
    source["dvr"]["password"] = "secret"
    with pytest.raises(SourceConfigError, match="plaintext credentials"):
        validate_config({"sources": [source]})


def test_duplicate_published_paths_are_rejected():
    duplicate = dvr_source()
    duplicate["id"] = "dvr-ch2"
    with pytest.raises(SourceConfigError, match="published paths must be unique"):
        validate_config({"sources": [dvr_source(), duplicate]})


def test_legacy_nvr_source_needs_no_camera_object():
    config = validate_config({"sources": [{"id": "nvr", "type": "nvr", "legacy_cameras": True}]})

    assert config["sources"][0]["legacy_cameras"] is True

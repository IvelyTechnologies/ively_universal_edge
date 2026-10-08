from agent.unified import dvr


def test_dvr_publisher_uses_hls_aligned_normalized_h264():
    command = dvr.publisher_command(
        "rtsp://input/stream",
        "rtsp://127.0.0.1:8554/customer_site_analog_dvr_ch1_low",
        {
            "video_mode": "transcode",
            "width": 640,
            "height": 360,
            "fps": 15,
            "gop": 30,
            "bitrate": "768k",
            "maxrate": "900k",
            "bufsize": "1536k",
        },
    )

    assert "-c:v libx264" in command
    assert "-g 30" in command
    assert "bframes=0" in command
    assert "repeat-headers=1" in command


def test_dvr_urls_are_credential_safe_in_status_output(monkeypatch):
    monkeypatch.setattr(dvr, "load_credential", lambda _credential_id: ("admin", "pass#word"))
    source = {
        "host": "192.168.1.6",
        "port": 554,
        "channel": 1,
        "credential_id": "site-dvr",
    }

    urls = dvr.build_dvr_urls(source)
    redacted = dvr.redacted_dvr_urls(source)

    assert "pass%23word" in urls[0]
    assert "pass" not in redacted[0]
    assert "<credential>" in redacted[0]

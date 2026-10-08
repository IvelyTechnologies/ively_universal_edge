# Unified Edge Installation

Unified Edge runs NVR, analog DVR, and direct RTSP publishers under one
`ively-agent` service and one MediaMTX configuration owner.

## Fresh install

1. Install the normal Edge package with `installer/install-with-venv.sh`.
2. Copy `configs/unified_sources.sample.json` to `/opt/ively/agent/sources.json`.
3. Set each source `path`, DVR `host`, and `channel`. Do not add a password to this file.
4. Run `sudo bash installer/enable-unified-edge.sh` on the Mini PC.
5. Enter each DVR credential when prompted. It is encrypted in
   `/opt/ively/agent/source_credentials.vault`.
6. Verify `curl -s http://127.0.0.1:8080/health` and
   `curl -s http://127.0.0.1:9997/v3/paths/list`.

## Operating rules

- Only `ively-agent` owns source publishers and `mediamtx.yml`.
- Do not run `analog-dvr-edge.service` with Unified Edge.
- Network loss or a failed camera restarts that source worker only.
- MediaMTX starts automatically after boot through systemd. It is restarted
  during first setup or a deliberate maintenance change, not by normal recovery.
- Existing NVR-only devices without `sources.json` continue using legacy startup.

## Combined site example

Keep the `legacy-nvr` source in `sources.json` to use cameras selected through
the existing provisioning UI. Add one DVR source for each desired DVR channel.
All output paths must be unique.

## DVR archive bridge

Unified Edge can search recordings stored on the DVR hard disk without copying
them to the Mini PC. The local API is `POST /archive/search` on port `8080` with
`source_id`, `start_time`, `end_time`, and optional `max_results`. Dashboard and
backend playback integration can call this bridge in the next phase.

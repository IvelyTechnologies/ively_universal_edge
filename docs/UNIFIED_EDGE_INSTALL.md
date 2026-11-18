# Unified Edge Installation

Unified Edge runs NVR, analog DVR, and direct RTSP publishers under one
`ively-agent` service and one MediaMTX configuration owner. The service manager
starts one independent FFmpeg publisher for every selected NVR camera or DVR
channel. A failed channel therefore restarts by itself without stopping the
other camera streams.

## Before Starting

1. Connect the Mini PC and DVR/NVR to the same local LAN.
2. Confirm the Mini PC can reach every DVR/NVR IP address.
3. Decide the published path for every camera. Paths must be unique and may
   use only letters, digits, `_`, `-`, and `.`.
4. For an existing site, retain the current NVR `cams.json` and make a backup
   before migration. Do not run Unified Edge and `analog-dvr-edge.service`
   together.

## 1. Install Unified Edge

On a fresh Mini PC, clone the Unified repository and run the venv installer:

```bash
git clone https://github.com/IvelyTechnologies/ively_universal_edge.git
cd ively_universal_edge
sudo bash installer/install-with-venv.sh
```

The installer intentionally refuses to overwrite an existing normal Edge
checkout. That is expected on a live NVR device; perform migration during a
maintenance window instead of replacing a working system unexpectedly.

## 2. Create `sources.json`

Create the protected configuration file from the supplied example:

```bash
sudo mkdir -p /opt/ively/agent
sudo cp /opt/ively/edge/configs/unified_sources.sample.json /opt/ively/agent/sources.json
sudo chmod 600 /opt/ively/agent/sources.json
sudo nano /opt/ively/agent/sources.json
```

Choose **one** example below. Replace only example IPs, paths, and channel
numbers. Never put DVR username or password in this file.

### NVR-only Site

Use this when existing NVR/IP cameras are already selected through the regular
Edge provisioning page. Their existing camera paths remain unchanged.

```json
{
  "version": 1,
  "sources": [
    {
      "id": "legacy-nvr",
      "type": "nvr",
      "legacy_cameras": true
    }
  ]
}
```

### DVR-only Site

Use one `dvr` item per required analog DVR channel. This example publishes
DVR channel 1 as `customer_dvr_ch1_low`.

```json
{
  "version": 1,
  "media": {
    "video_mode": "transcode",
    "width": 640,
    "height": 360,
    "fps": 15,
    "bitrate": "768k",
    "maxrate": "900k",
    "bufsize": "1536k"
  },
  "sources": [
    {
      "id": "customer-dvr-ch1",
      "type": "dvr",
      "path": "customer_dvr_ch1_low",
      "channel": 1,
      "dvr": {
        "host": "192.168.1.108",
        "port": 554,
        "credential_id": "customer-dvr"
      }
    }
  ]
}
```

### Combined NVR and DVR Site

Use this when the same Mini PC must publish existing NVR cameras plus analog
DVR channels. The NVR source reuses the existing camera selection; add one
DVR object for every analog channel.

```json
{
  "version": 1,
  "media": {
    "video_mode": "transcode",
    "width": 640,
    "height": 360,
    "fps": 15,
    "bitrate": "768k",
    "maxrate": "900k",
    "bufsize": "1536k"
  },
  "sources": [
    {
      "id": "legacy-nvr",
      "type": "nvr",
      "legacy_cameras": true
    },
    {
      "id": "customer-dvr-ch1",
      "type": "dvr",
      "path": "customer_dvr_ch1_low",
      "channel": 1,
      "dvr": {
        "host": "192.168.1.108",
        "port": 554,
        "credential_id": "customer-dvr"
      }
    },
    {
      "id": "customer-dvr-ch2",
      "type": "dvr",
      "path": "customer_dvr_ch2_low",
      "channel": 2,
      "dvr": {
        "host": "192.168.1.108",
        "port": 554,
        "credential_id": "customer-dvr"
      }
    }
  ]
}
```

`transcode` is the recommended DVR default: it normalizes damaged timestamps
and produces browser-compatible H.264 output. Use `copy` only after a DVR
source has been verified stable.

## 3. Validate Before Changing Services

This command checks JSON structure, source types, unique IDs, and unique
published paths. It does not stop or restart a service.

```bash
sudo PYTHONPATH=/opt/ively/edge /opt/ively/venv/bin/python3 -c "from agent.unified.config import load_config; c = load_config(); print('VALID', [(s['type'], s['path']) for s in c['sources']])"
```

Expected output for the combined example:

```text
VALID [('nvr', 'legacy-nvr'), ('dvr', 'customer_dvr_ch1_low'), ('dvr', 'customer_dvr_ch2_low')]
```

If this reports an error, correct `sources.json` before continuing.

## 4. Enable Unified Edge

### Fresh Device or DVR-only Device

Run the setup command. It prompts once for each distinct `credential_id` and
saves credentials encrypted in `/opt/ively/agent/source_credentials.vault`.

```bash
sudo bash /opt/ively/edge/installer/enable-unified-edge.sh
```

### Existing NVR Plus Analog DVR Migration

After configuration validation succeeds, choose a short maintenance window.
This stops the old analog publisher, prepares the complete MediaMTX path list,
and starts one Unified agent service.

```bash
sudo systemctl disable --now analog-dvr-edge.service
sudo bash /opt/ively/edge/installer/enable-unified-edge.sh
```

The command performs the one controlled MediaMTX restart required to add new
publisher paths. Normal camera recovery does not restart MediaMTX.

## 5. Verify Every Published Stream

```bash
sudo systemctl status ively-agent mediamtx --no-pager
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:9997/v3/paths/list
```

For a combined site, confirm the MediaMTX path list contains existing NVR paths
and every configured DVR path. Verify a DVR output from the Mini PC:

```bash
timeout 65 ffmpeg -v error -rtsp_transport tcp -timeout 10000000 \
  -i "rtsp://127.0.0.1:8554/customer_dvr_ch1_low" \
  -t 55 -an -f null -
echo "DVR_CH1_EXIT=$?"
```

`DVR_CH1_EXIT=0` means the local published RTSP stream stayed readable for the
full test. Run the same command for each configured path.

## Operating Rules

- Only `ively-agent` owns source publishers and `mediamtx.yml`.
- Do not run `analog-dvr-edge.service` with Unified Edge.
- Network loss or a failed camera restarts that source worker only.
- MediaMTX starts automatically after boot through systemd. It is restarted
  during first setup or a deliberate maintenance change, not by normal recovery.
- Existing NVR-only devices without `sources.json` continue using legacy startup.
- A DVR source supports common Hikvision and Dahua RTSP URL forms automatically.

## DVR archive bridge

Unified Edge can search recordings stored on the DVR hard disk without copying
them to the Mini PC. The local API is `POST /archive/search` on port `8080` with
`source_id`, `start_time`, `end_time`, and optional `max_results`. Dashboard and
backend playback integration can call this bridge in the next phase.

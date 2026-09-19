# cubesatsim-aprs-parser

Ground station for a [CubeSatSim](https://github.com/tomwardill/CubeSatSim):
decodes its APRS telemetry, drives gauges and a web visualisation, and has
buttons that command the CubeSatSim between APRS and SSTV modes over RF.

## Services

All run from `docker-compose.yml`; the three Python services share one image
(`Dockerfile`) with different entrypoints.

| Service | Entrypoint | Does |
|---|---|---|
| parser | `run-parser.sh` | `rtl_fm` on 434.9 MHz → `multimon-ng` → `main.py` → MQTT `cubesatsim/data` |
| gauges | `run-gauges.sh` | `gauges.py`, MQTT → I2C gauges |
| buttons | `run-buttons.sh` | `buttons.py`, GPIO buttons/LEDs, transmits mode commands |
| visualisation | nginx | `frontend/` |
| mosquitto | | MQTT broker |

`update.sh` pulls the images named by `REGISTRY` in `.env` and restarts.

## Mode commands (buttons service)

Pressing the APRS or SSTV button sets a pending request. On the next
`cubesatsim/data` message (i.e. just after the CubeSatSim finishes a packet and
starts listening) `buttons.py`:

1. keys PTT: `rigctl -r host.docker.internal -m 2 T 1`
2. waits 1 s, plays `sstv_mode.wav` / `aprs_mode.wav` with
   `aplay -D plughw:CARD=Device,DEV=0`
3. unkeys PTT

On the CubeSatSim, direwolf decodes the packet and `dtmf_aprs_cc.py` matches
`MODE=s` / `MODE=a`.

### Host setup

PTT is the CM108 GPIO on the radio's USB sound card, driven by `rigctld` on the
host (hamlib built from source into `/usr/local`):

    sudo cp systemd/cm108-init.service /lib/systemd/system/
    sudo systemctl enable --now cm108-init

The SA818 transmits on the CubeSatSim's receive frequency, narrow:

    sa818 radio --frequency 435.000 --bw 0

### Command wav files

Made with direwolf's `gen_packets` (bash `echo`, so the `\` stays literal):

    echo -n "2E0JJI-10>AMSAT-11:=5324.21N\00132.14WSMODE=s" | gen_packets -a 75 -o sstv_mode.wav -
    echo -n "2E0JJI-10>AMSAT-11:=5324.21N\00132.14WSMODE=a" | gen_packets -a 75 -o aprs_mode.wav -

Check one with `atest sstv_mode.wav`.

### Transmit audio level

Set with the sound card's `Speaker` control, then persist it:

    amixer -c Device sset Speaker 4
    sudo alsactl store

Measured 2026-09-19, as the audio level direwolf reports on the CubeSatSim
(`journalctl -u command -f`; direwolf suggests about 50):

| Speaker (0-37) | Received level | |
|---|---|---|
| 0 | - | effectively muted, never decodes |
| 1 | 33 | decodes |
| 4 | 46 | in use |
| 6 | 57 | |
| 12 | 108 | |
| 20+ | ~200 | saturated / over-deviated |

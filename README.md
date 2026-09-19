# cubesatsim-aprs-parser

Ground station for a [CubeSatSim](https://github.com/tomwardill/CubeSatSim):
decodes its APRS telemetry, drives gauges and a web visualisation, and has
buttons that command the CubeSatSim between APRS and SSTV modes over RF.

## Services

All run from `docker-compose.yml`; the three Python services share one image
(`Dockerfile`) with different entrypoints.

| Service | Entrypoint | Does |
|---|---|---|
| parser | `run-parser.sh` | `rtl_fm` on 434.9 MHz → `multimon-ng` → `main.py` → MQTT `cubesatsim/data`; the same audio → `sstv_detect.py` → MQTT `cubesatsim/photos` when an SSTV image ends |
| gauges | `run-gauges.sh` | `gauges.py`, MQTT → I2C gauges |
| buttons | `run-buttons.sh` | `buttons.py`, GPIO buttons/LEDs, transmits mode commands |
| visualisation | nginx | `frontend/` |
| mosquitto | | MQTT broker |

`update.sh` pulls the images named by `REGISTRY` in `.env` and restarts.

## Visualisation

`frontend/` shows a wireframe CubeSat driven by the MQTT feed: attitude from the
gyro, a solar panel on each face shaded by that panel's voltage, and the SSTV
image painted line by line when one is coming in.

Panel shading is a sequential ramp, a single hue from dark (no light) to bright
(full sun), fixed to 0 V - 2.50 V so a colour always means the same voltage.
`?vmax=` changes the top of the scale if the venue needs it, e.g.
`http://zero2/?vmax=1.2` for a dim room. There is no scale on screen: the
physical gauges carry the levels. The panel in the most light gets a brighter
frame when one of them clearly leads.

## Mode commands (buttons service)

The CubeSatSim shares one radio for transmit and receive, so it only hears
commands between its own transmissions: for about 10 s after each telemetry
packet in APRS mode, and for about 17 s after each 74 s image in SSTV mode.

Pressing the APRS or SSTV button sets a pending request. On the next
`cubesatsim/data` message (SSTV requested) or `cubesatsim/photos` message (APRS
requested), i.e. just as the CubeSatSim starts listening, `buttons.py`:

1. sets the transmit level: `amixer -c Device sset Speaker 4` (`--tx_volume`)
2. keys PTT: `rigctl -r host.docker.internal -m 2 T 1`
3. waits 1 s, plays `sstv_mode.wav` / `aprs_mode.wav` with
   `aplay -D plughw:CARD=Device,DEV=0`
4. unkeys PTT

The request stays pending, and is sent again in the next listening window, until
a message from the new mode arrives or it has been sent 3 times. Reset cancels it.

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

`buttons.py` sets the sound card's `Speaker` control before each transmission
(`--tx_volume`, default 4), because a desktop sound server on the host has been
seen to put it back to 0, which silently mutes the command. To try a level by
hand, and keep it across reboots:

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

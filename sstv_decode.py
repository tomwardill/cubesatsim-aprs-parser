"""Decode the CubeSatSim's SSTV images (Scottie 2) line by line.

Reads the raw rtl_fm audio (16 bit little endian mono) on stdin and publishes
each image line to MQTT as soon as it has been received, so the visualisation
can draw the picture as it arrives:

    cubesatsim/sstv/start  {"image": 3, "mode": "Scottie 2", "width": 320, "height": 256}
    cubesatsim/sstv/line   {"image": 3, "line": 17, "rgb": "<base64, 3 bytes per pixel>"}
    cubesatsim/sstv/end    {"image": 3, "lines": 256}

An image starts with a VIS header: a 1900 Hz leader, then 300 ms of bits at
1100-1300 Hz that run straight into the first 1200 Hz sync pulse. Nothing else
the CubeSatSim sends stays below 1400 Hz for that long. Each Scottie line is
then: 1.5 ms gap, green, 1.5 ms gap, blue, 9 ms sync, 1.5 ms gap, red. Pixel
brightness is the tone frequency, 1500 Hz (black) to 2300 Hz (white).
"""

import base64
import json
import sys

import click
import numpy as np
import paho.mqtt.client as mqtt

SAMPLE_RATE = 22050

WIDTH = 320
HEIGHT = 256
SCAN = 0.088064  # seconds for one colour of one line
GAP = 0.0015
SYNC = 0.009
LINE = 3 * SCAN + 3 * GAP + SYNC
SYNC_OFFSET = 2 * GAP + 2 * SCAN  # from the start of a line to its sync pulse

BLACK = 1500
WHITE = 2300
CENTRE = 1750  # middle of everything we care about, 1100 to 2300 Hz
VIS_CODES = {56: "Scottie 2"}


class ScottieDecoder:
    def __init__(self, sample_rate=SAMPLE_RATE):
        self.fs = sample_rate
        # audio -> instantaneous frequency
        taps = np.hamming(61) * np.sinc(2 * 1000 / sample_rate * (np.arange(61) - 30))
        self.taps = taps / taps.sum()
        self.pending = b""
        self.mixed_tail = np.zeros(len(self.taps) - 1, dtype=np.complex128)
        self.last_z = 0j
        self.samples_in = 0

        self.freq = np.zeros(0)  # instantaneous frequency, Hz
        self.base = 0  # sample number of freq[0]
        self.searched = 0  # no need to look for a header before this sample

        self.image = 0
        self.line = None  # None while waiting for a header
        self.sync = 0.0  # where the current line's sync pulse should start
        self.missed_syncs = 0

    def feed(self, data: bytes) -> list[tuple]:
        """Add audio, return ("start", info) / ("line", n, rgb) / ("end", lines) events."""
        self._demodulate(data)
        events = []
        while True:
            if self.line is None:
                if not self._find_header(events):
                    break
            elif not self._decode_line(events):
                break
        self._trim()
        return events

    def _demodulate(self, data):
        data = self.pending + data
        usable = len(data) // 2 * 2
        self.pending = data[usable:]
        samples = np.frombuffer(data[:usable], dtype="<i2").astype(np.float64)
        if not len(samples):
            return
        n = np.arange(self.samples_in, self.samples_in + len(samples))
        self.samples_in += len(samples)
        mixed = np.concatenate(
            [self.mixed_tail, samples * np.exp(-2j * np.pi * CENTRE * n / self.fs)]
        )
        self.mixed_tail = mixed[-(len(self.taps) - 1) :]
        z = np.convolve(mixed, self.taps, mode="valid")
        steps = z * np.conj(np.concatenate([[self.last_z], z[:-1]]))
        self.last_z = z[-1]
        freq = np.angle(steps) * self.fs / (2 * np.pi) + CENTRE
        self.freq = np.concatenate([self.freq, freq])

    def _trim(self):
        # a header search looks back 0.7 s, a line needs its green and blue
        keep_from = self.searched - int(0.7 * self.fs)
        if self.line is not None:
            keep_from = int(self.sync - (SYNC_OFFSET + 0.05) * self.fs)
        drop = keep_from - self.base
        if drop > 0:
            self.freq = self.freq[drop:]
            self.base += drop

    def _mean(self, start, stop):
        """Mean frequency between two (fractional, absolute) sample positions."""
        a = max(int(round(start)) - self.base, 0)
        b = max(int(round(stop)) - self.base, a + 1)
        return float(self.freq[a:b].mean())

    def _find_header(self, events):
        window = int(0.005 * self.fs)
        # look far enough back to see a whole header and the leader before it
        first = max(self.searched - int(0.7 * self.fs), self.base)
        freq = self.freq[first - self.base :]
        # leave the last 10 ms: a run ending there may not really have ended
        usable = first + len(freq) - int(0.01 * self.fs)
        if usable <= self.searched:
            return False
        smooth = np.convolve(freq, np.ones(window) / window, mode="same")
        edges = np.diff((smooth < 1400).astype(np.int8))
        starts = np.flatnonzero(edges == 1)
        already, self.searched = self.searched, usable
        for end in np.flatnonzero(edges == -1):
            before = starts[starts < end]
            if not len(before) or not already <= first + end < usable:
                continue
            start = before[-1]
            if not 0.27 <= (end - start) / self.fs <= 0.35:
                continue
            leader = freq[max(start - int(0.3 * self.fs), 0) : max(start - int(0.02 * self.fs), 1)]
            if len(leader) < 0.1 * self.fs or abs(np.median(leader) - 1900) > 100:
                continue
            self.image += 1
            self.line = 0
            self.missed_syncs = 0
            self.sync = first + end + SYNC_OFFSET * self.fs
            self.searched = first + end
            code = self._vis_code(first + start)
            events.append(
                (
                    "start",
                    {
                        "image": self.image,
                        "mode": VIS_CODES.get(code, f"VIS {code}, assuming Scottie 2"),
                        "width": WIDTH,
                        "height": HEIGHT,
                    },
                )
            )
            return True
        return False

    def _vis_code(self, header):
        bit = 0.030 * self.fs
        bits = [
            self._mean(header + (i + 0.2) * bit, header + (i + 0.8) * bit) < 1200
            for i in range(1, 8)
        ]
        return sum(1 << i for i, one in enumerate(bits) if one)

    def _decode_line(self, events):
        fs = self.fs
        slack = 0.003 if self.line == 0 else 0.0015
        line_end = self.sync + (SYNC + GAP + SCAN + slack) * fs
        if line_end + 0.01 * fs > self.base + len(self.freq):
            return False  # not all here yet

        # find the sync pulse: the 9 ms stretch with the lowest mean frequency
        width = int(round(SYNC * fs))
        first = int(self.sync - slack * fs) - self.base
        last = int(self.sync + slack * fs) - self.base
        sums = np.cumsum(np.concatenate([[0.0], self.freq[first : last + width]]))
        means = (sums[width:] - sums[:-width]) / width
        best = int(np.argmin(means))
        if means[best] < 1350:
            found = self.base + first + best
            # trust the first pulse completely, then follow drift gently
            self.sync += (found - self.sync) * (1.0 if self.line == 0 else 0.5)
            self.missed_syncs = 0
        else:
            # noise never stays this low for 9 ms, so the picture has stopped
            self.missed_syncs += 1

        starts = (
            self.sync + (SYNC + GAP) * fs,  # red
            self.sync - (2 * SCAN + GAP) * fs,  # green
            self.sync - SCAN * fs,  # blue
        )
        pixel = SCAN * fs / WIDTH
        smooth = np.convolve(self.freq, np.ones(int(pixel)) / int(pixel), mode="same")
        centres = (np.arange(WIDTH) + 0.5) * pixel
        rgb = np.empty((WIDTH, 3), dtype=np.uint8)
        for channel, start in enumerate(starts):
            tones = np.interp(start + centres - self.base, np.arange(len(smooth)), smooth)
            rgb[:, channel] = np.clip((tones - BLACK) / (WHITE - BLACK) * 255, 0, 255)

        if self.missed_syncs >= 3:
            events.append(("end", self.line - 2))
        else:
            events.append(("line", self.line, rgb.tobytes()))
            self.line += 1
            self.sync += LINE * fs
            if self.line < HEIGHT:
                return True
            events.append(("end", HEIGHT))
        self.searched = int(line_end)
        self.line = None
        return True


@click.command()
@click.option("--mqtt_host", default="localhost", help="MQTT broker host")
@click.option("--mqtt_port", default=1883, help="MQTT broker port")
@click.option(
    "--mqtt_topic", default="cubesatsim/sstv", help="MQTT topic prefix to publish to"
)
@click.option("--mqtt_username", default=None, help="MQTT username (if required)")
@click.option("--mqtt_password", default=None, help="MQTT password (if required)")
def main(mqtt_host, mqtt_port, mqtt_topic, mqtt_username, mqtt_password):
    """Publish SSTV image lines as they are received."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)
    client.connect_async(mqtt_host, mqtt_port, 60)
    client.loop_start()

    decoder = ScottieDecoder()
    while True:
        data = sys.stdin.buffer.read1(65536)
        if not data:
            break
        for event in decoder.feed(data):
            if event[0] == "start":
                client.publish(f"{mqtt_topic}/start", json.dumps(event[1]))
                print(f"SSTV image {decoder.image} started: {event[1]['mode']}", flush=True)
            elif event[0] == "line":
                message = {
                    "image": decoder.image,
                    "line": event[1],
                    "rgb": base64.b64encode(event[2]).decode(),
                }
                client.publish(f"{mqtt_topic}/line", json.dumps(message))
            else:
                message = {"image": decoder.image, "lines": event[1]}
                client.publish(f"{mqtt_topic}/end", json.dumps(message))
                print(f"SSTV image {decoder.image} ended after {event[1]} lines", flush=True)


if __name__ == "__main__":
    main(auto_envvar_prefix="CUBESATSIM")
    sys.exit(0)

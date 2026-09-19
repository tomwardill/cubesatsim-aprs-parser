"""Spot the end of each CubeSatSim SSTV image in the receiver audio.

In SSTV mode the CubeSatSim only listens for commands in the gap between
images, so the buttons service needs to know when an image has just finished.
Reads the raw rtl_fm audio (16 bit little endian mono) on stdin and publishes
to cubesatsim/photos every time a long run of SSTV tones stops.

SSTV audio is a single tone between 1200 and 2300 Hz, around 3400 zero
crossings a second; FM noise with no carrier is around 11000. An APRS packet
looks like SSTV but only lasts a second or two.
"""

import json
import sys
from datetime import datetime, timezone

import click
import paho.mqtt.client as mqtt

SAMPLE_RATE = 22050

# one output byte per sample: is the sample negative? (from its high byte)
_SIGN = bytes(1 if b & 0x80 else 0 for b in range(256))


def zero_crossings(samples: bytes) -> int:
    signs = samples[1::2].translate(_SIGN)
    return signs.count(b"\x00\x01") + signs.count(b"\x01\x00")


class SstvEndDetector:
    def __init__(
        self,
        sample_rate=SAMPLE_RATE,
        block_seconds=0.5,
        tone_band=(2000, 5500),  # zero crossings per second
        min_image_seconds=30,
        end_blocks=2,
    ):
        self.block_seconds = block_seconds
        self.block_bytes = int(sample_rate * block_seconds) * 2
        self.tone_band = tone_band
        self.min_image_seconds = min_image_seconds
        self.end_blocks = end_blocks
        self.buffer = b""
        self.tone_seconds = 0.0
        self.quiet_blocks = 0

    def feed(self, data: bytes) -> list[float]:
        """Add audio, return the duration of each image that just ended."""
        self.buffer += data
        ended = []
        while len(self.buffer) >= self.block_bytes:
            block = self.buffer[: self.block_bytes]
            self.buffer = self.buffer[self.block_bytes :]
            duration = self._block(block)
            if duration:
                ended.append(duration)
        return ended

    def _block(self, block: bytes):
        rate = zero_crossings(block) / self.block_seconds
        if self.tone_band[0] <= rate < self.tone_band[1]:
            self.tone_seconds += self.block_seconds
            self.quiet_blocks = 0
            return None
        # a single odd block doesn't end an image
        self.quiet_blocks += 1
        if self.quiet_blocks < self.end_blocks:
            return None
        duration, self.tone_seconds = self.tone_seconds, 0.0
        if duration >= self.min_image_seconds:
            return duration
        return None


@click.command()
@click.option("--mqtt_host", default="localhost", help="MQTT broker host")
@click.option("--mqtt_port", default=1883, help="MQTT broker port")
@click.option(
    "--mqtt_topic", default="cubesatsim/photos", help="MQTT topic to publish to"
)
@click.option("--mqtt_username", default=None, help="MQTT username (if required)")
@click.option("--mqtt_password", default=None, help="MQTT password (if required)")
def main(mqtt_host, mqtt_port, mqtt_topic, mqtt_username, mqtt_password):
    """Publish a message each time an SSTV image finishes."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)
    client.connect_async(mqtt_host, mqtt_port, 60)
    client.loop_start()

    detector = SstvEndDetector()
    while True:
        data = sys.stdin.buffer.read1(65536)
        if not data:
            break
        for duration in detector.feed(data):
            message = {
                "event": "sstv_image_end",
                "duration": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            client.publish(mqtt_topic, json.dumps(message))
            print(f"Published to {mqtt_topic}: {message}", flush=True)


if __name__ == "__main__":
    main(auto_envvar_prefix="CUBESATSIM")
    sys.exit(0)

import array
import math
import random

from sstv_detect import SAMPLE_RATE, SstvEndDetector, zero_crossings


def tone(seconds, hz=1900, amplitude=3000):
    n = int(SAMPLE_RATE * seconds)
    return array.array(
        "h", (int(amplitude * math.sin(2 * math.pi * hz * i / SAMPLE_RATE)) for i in range(n))
    ).tobytes()


def noise(seconds, amplitude=9000):
    rng = random.Random(1)
    n = int(SAMPLE_RATE * seconds)
    return array.array("h", (rng.randint(-amplitude, amplitude) for _ in range(n))).tobytes()


def run(audio, chunk=4099):
    detector = SstvEndDetector()
    ended = []
    for i in range(0, len(audio), chunk):
        ended += detector.feed(audio[i : i + chunk])
    return ended


def test_zero_crossings_of_a_tone():
    assert abs(zero_crossings(tone(1, hz=1900)) - 3800) < 10


def test_noise_is_not_sstv():
    assert run(noise(60)) == []


def test_image_end_is_reported_once():
    ended = run(noise(5) + tone(70) + noise(17) + tone(70) + noise(5))
    assert len(ended) == 2
    assert all(abs(duration - 70) <= 1 for duration in ended)


def test_aprs_packets_are_ignored():
    assert run((noise(10) + tone(1.5, hz=1700)) * 5 + noise(10)) == []


def test_image_still_in_progress_is_not_reported():
    assert run(noise(5) + tone(60)) == []


def test_single_glitch_does_not_split_an_image():
    ended = run(tone(35) + noise(0.5) + tone(35) + noise(5))
    assert len(ended) == 1
    assert ended[0] >= 69

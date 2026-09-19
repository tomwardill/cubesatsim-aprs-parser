import numpy as np

from sstv_decode import GAP, HEIGHT, SAMPLE_RATE, SCAN, SYNC, WIDTH, ScottieDecoder


def scottie_2(image, sample_rate=SAMPLE_RATE, rate_error=0.0):
    """Encode a (lines, 320, 3) image the way pisstvpp does, as 16 bit audio."""
    segments = [(1900, 0.3), (1200, 0.01), (1900, 0.3), (1200, 0.03)]
    bits = [56 >> i & 1 for i in range(7)]
    bits.append(sum(bits) % 2)
    segments += [(1100 if bit else 1300, 0.03) for bit in bits]
    segments += [(1200, 0.03), (1200, SYNC)]
    for row in image:
        for channel in (1, 2, 0):
            if channel == 0:
                segments += [(1200, SYNC)]
            segments += [(1500, GAP)]
            segments += [(1500 + 800 * value / 255, SCAN / WIDTH) for value in row[:, channel].astype(float)]

    fs = sample_rate * (1 + rate_error)
    edges = np.cumsum([0.0] + [seconds for _, seconds in segments])
    tones = np.array([hz for hz, _ in segments])
    t = np.arange(int(edges[-1] * fs)) / fs
    hz = tones[np.searchsorted(edges, t, side="right") - 1]
    phase = 2 * np.pi * np.cumsum(hz) / fs
    return (3000 * np.sin(phase)).astype("<i2").tobytes()


def noise(seconds):
    rng = np.random.default_rng(1)
    return rng.integers(-9000, 9000, int(SAMPLE_RATE * seconds)).astype("<i2").tobytes()


def colour_bars(lines=HEIGHT):
    image = np.zeros((lines, WIDTH, 3), dtype=np.uint8)
    image[:, :, 0] = np.linspace(0, 255, WIDTH)  # red ramp, left to right
    image[:, :, 1] = np.linspace(0, 255, lines)[:, None]  # green ramp, top to bottom
    image[:, WIDTH // 2 :, 2] = 200  # blue on the right half
    return image


def decode(audio, chunk=8191):
    decoder = ScottieDecoder()
    events = []
    for i in range(0, len(audio), chunk):
        events += decoder.feed(audio[i : i + chunk])
    return events


def picture(events):
    rows = [np.frombuffer(e[2], np.uint8).reshape(WIDTH, 3) for e in events if e[0] == "line"]
    return np.array(rows).astype(int)


def test_decodes_a_whole_image():
    image = colour_bars()
    events = decode(noise(2) + scottie_2(image) + noise(2))
    assert events[0][0] == "start" and events[0][1]["mode"] == "Scottie 2"
    assert [e[1] for e in events if e[0] == "line"] == list(range(HEIGHT))
    assert events[-1] == ("end", HEIGHT)
    # ignore the pixels either side of the hard blue edge
    error = np.abs(picture(events) - image)
    error[:, WIDTH // 2 - 3 : WIDTH // 2 + 3] = 0
    assert error.mean() < 3
    assert np.percentile(error, 99) < 12


def test_lines_arrive_as_they_are_received():
    audio = scottie_2(colour_bars())
    decoder = ScottieDecoder()
    half = len(audio) // 4 * 2
    lines = [e for e in decoder.feed(audio[:half]) if e[0] == "line"]
    assert HEIGHT // 2 - 4 <= len(lines) <= HEIGHT // 2


def test_chunk_size_does_not_matter():
    audio = noise(1) + scottie_2(colour_bars(20)) + noise(3)
    assert decode(audio, chunk=1001) == decode(audio, chunk=65536)


def test_follows_a_sound_card_running_fast():
    image = colour_bars()
    events = decode(scottie_2(image, rate_error=300e-6) + noise(2))
    error = np.abs(picture(events) - image)[-20:]  # drift is worst at the bottom
    error[:, WIDTH // 2 - 3 : WIDTH // 2 + 3] = 0
    assert error.mean() < 4


def test_noise_and_aprs_are_not_images():
    tone = (3000 * np.sin(2 * np.pi * 1200 * np.arange(SAMPLE_RATE) / SAMPLE_RATE)).astype("<i2")
    assert decode(noise(30) + tone.tobytes() + noise(30)) == []


def test_image_that_stops_early_ends():
    events = decode(noise(1) + scottie_2(colour_bars(40)) + noise(5))
    assert events[-1][0] == "end"
    assert 38 <= events[-1][1] <= 42


def test_two_images_in_a_row():
    audio = scottie_2(colour_bars(10)) + noise(3) + scottie_2(colour_bars(10)) + noise(3)
    starts = [e[1]["image"] for e in decode(audio) if e[0] == "start"]
    assert starts == [1, 2]

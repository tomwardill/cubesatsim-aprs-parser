import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("GPIOZERO_PIN_FACTORY", "mock")

import buttons  # noqa: E402


def message(topic):
    return SimpleNamespace(topic=topic, payload=b"{}")


class Result:
    def __init__(self, returncode):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = "No such device" if returncode else ""


@pytest.fixture
def rig(monkeypatch):
    """A working radio. rig.fail(name) makes that command start failing."""
    commands = []
    broken = set()
    monkeypatch.setattr(
        buttons.subprocess, "run",
        lambda cmd, **kw: (commands.append(cmd), Result(1 if cmd[0] in broken else 0))[1],
    )
    monkeypatch.setattr(buttons, "sleep", lambda seconds: None)
    monkeypatch.setattr(buttons, "action_mqtt_client", MagicMock())
    buttons.clear_requests()
    rig = SimpleNamespace(
        commands=commands,
        fail=broken.add,
        played=lambda: [cmd[-1] for cmd in commands if cmd[0] == "aplay"],
        faults=lambda: [
            json.loads(call.args[1])["fault"]
            for call in buttons.action_mqtt_client.publish.call_args_list
            if call.args[0] == buttons.fault_mqtt_topic
        ],
    )
    yield rig
    buttons.clear_requests()


@pytest.fixture
def played(rig):
    return rig.played


def test_aprs_is_sent_when_an_sstv_image_ends(played):
    buttons.aprs_button_pressed()
    assert played() == []
    buttons.on_message(None, None, message("cubesatsim/photos"))
    assert played() == ["aprs_mode.wav"]


def test_level_is_set_and_ptt_released_around_sending(rig):
    buttons.sstv_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/data"))
    assert [cmd[0] for cmd in rig.commands] == ["amixer", "rigctl", "aplay", "rigctl"]
    assert rig.commands[0][-2:] == ["Speaker", "4"]
    assert [cmd[-1] for cmd in rig.commands[1:]] == ["1", "sstv_mode.wav", "0"]


def test_a_dead_ptt_is_reported_and_nothing_is_played(rig):
    rig.fail("rigctl")
    buttons.sstv_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/data"))
    assert rig.played() == []
    assert "TRANSMITTER WILL NOT KEY - CHECK THE USB LEAD" in rig.faults()


def test_a_missing_sound_card_is_reported(rig):
    rig.fail("amixer")
    buttons.sstv_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/data"))
    assert rig.commands == [["amixer", "-q", "-c", "Device", "sset", "Speaker", "4"]]
    assert "SOUND CARD MISSING - CHECK THE USB LEAD" in rig.faults()


def test_ptt_is_released_even_when_playing_fails(rig):
    rig.fail("aplay")
    buttons.sstv_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/data"))
    assert [cmd[0] for cmd in rig.commands] == ["amixer", "rigctl", "aplay", "rigctl"]
    assert rig.commands[-1][-1] == "0", "PTT must be unkeyed after a failed transmission"
    assert "SOUND CARD WILL NOT PLAY - CHECK THE USB LEAD" in rig.faults()


def test_a_working_transmission_clears_the_fault(rig):
    buttons.sstv_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/data"))
    assert rig.faults() == [None]


def test_request_is_retried_until_the_mode_changes(played):
    buttons.aprs_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/photos"))
    buttons.on_message(None, None, message("cubesatsim/photos"))
    assert played() == ["aprs_mode.wav"] * 2
    buttons.on_message(None, None, message("cubesatsim/data"))
    assert not buttons.aprs_mode_requested
    buttons.on_message(None, None, message("cubesatsim/photos"))
    assert played() == ["aprs_mode.wav"] * 2


def test_gives_up_after_max_attempts(played):
    buttons.sstv_button_pressed()
    for _ in range(buttons.MAX_COMMAND_ATTEMPTS + 3):
        buttons.on_message(None, None, message("cubesatsim/data"))
    assert played() == ["sstv_mode.wav"] * buttons.MAX_COMMAND_ATTEMPTS
    assert not buttons.sstv_mode_requested


def test_nothing_is_sent_when_already_in_the_requested_mode(played):
    buttons.aprs_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/data"))
    buttons.sstv_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/photos"))
    assert played() == []


def test_reset_cancels_a_request(played):
    buttons.aprs_button_pressed()
    buttons.reset_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/photos"))
    assert played() == []

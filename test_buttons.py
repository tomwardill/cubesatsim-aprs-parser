import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("GPIOZERO_PIN_FACTORY", "mock")

import buttons  # noqa: E402


def message(topic):
    return SimpleNamespace(topic=topic, payload=b"{}")


@pytest.fixture
def played(monkeypatch):
    """The wav files transmitted, in order."""
    commands = []
    monkeypatch.setattr(buttons.subprocess, "run", lambda cmd: commands.append(cmd))
    monkeypatch.setattr(buttons, "sleep", lambda seconds: None)
    monkeypatch.setattr(buttons, "action_mqtt_client", MagicMock())
    buttons.clear_requests()
    yield lambda: [cmd[-1] for cmd in commands if cmd[0] == "aplay"]
    buttons.clear_requests()


def test_aprs_is_sent_when_an_sstv_image_ends(played):
    buttons.aprs_button_pressed()
    assert played() == []
    buttons.on_message(None, None, message("cubesatsim/photos"))
    assert played() == ["aprs_mode.wav"]


def test_level_is_set_and_ptt_released_around_sending(played, monkeypatch):
    commands = []
    monkeypatch.setattr(buttons.subprocess, "run", lambda cmd: commands.append(cmd))
    buttons.sstv_button_pressed()
    buttons.on_message(None, None, message("cubesatsim/data"))
    assert [cmd[0] for cmd in commands] == ["amixer", "rigctl", "aplay", "rigctl"]
    assert commands[0][-2:] == ["Speaker", "4"]
    assert [cmd[-1] for cmd in commands[1:]] == ["1", "sstv_mode.wav", "0"]


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

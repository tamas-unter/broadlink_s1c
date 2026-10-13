"""Tests of the status decoding (no Home Assistant needed)."""

from __future__ import annotations

import pytest

from custom_components.broadlink_s1c.status import (
    S1CSensor,
    SensorKind,
    decode_status,
)


@pytest.mark.parametrize(
    ("status", "active", "tamper"),
    [
        (128, False, False),  # closed (confirmed by the owner)
        (16, True, False),  # open (confirmed by the owner)
        (48, None, True),  # tampered (confirmed by the owner)
    ],
)
def test_door(status: int, active: bool | None, tamper: bool) -> None:
    """Door values."""
    decoded = decode_status(SensorKind.DOOR, status)
    assert decoded.known
    assert decoded.active is active
    assert decoded.tamper is tamper


@pytest.mark.parametrize("status", [0, 1, 144, 255])
def test_door_unlisted_values_are_unknown(status: int) -> None:
    """Values the owner did not confirm must not be guessed."""
    decoded = decode_status(SensorKind.DOOR, status)
    assert not decoded.known
    assert decoded.active is None
    assert decoded.tamper is None


@pytest.mark.parametrize(
    ("status", "active", "tamper"),
    [
        (0, False, False),
        (64, False, False),
        (128, False, False),
        (16, True, False),
        (80, True, False),
        (32, None, True),
    ],
)
def test_motion(status: int, active: bool | None, tamper: bool) -> None:
    """Motion sensor values."""
    decoded = decode_status(SensorKind.MOTION, status)
    assert decoded.known
    assert decoded.active is active
    assert decoded.tamper is tamper


@pytest.mark.parametrize(
    ("status", "button"),
    [(16, "disarm"), (32, "arm_away"), (64, "arm_home"), (128, "sos")],
)
def test_key_fob_buttons(status: int, button: str) -> None:
    """Every key fob button maps to an event type."""
    decoded = decode_status(SensorKind.KEY_FOB, status)
    assert decoded.known
    assert decoded.button == button


def test_key_fob_idle_and_unknown() -> None:
    """Idle is known without a button, anything else is unknown."""
    idle = decode_status(SensorKind.KEY_FOB, 0)
    assert idle.known
    assert idle.button is None
    assert not decode_status(SensorKind.KEY_FOB, 3).known


def test_unknown_kind() -> None:
    """Unknown accessory types are never decoded."""
    assert not decode_status(SensorKind.UNKNOWN, 0).known


def test_from_library() -> None:
    """Parse an item exactly as python-broadlink returns it."""
    sensor = S1CSensor.from_library(
        {
            "status": 16,
            "name": "Door1",
            "type": "Door Sensor",
            "order": 2,
            "serial": "3101c958",
        }
    )
    assert sensor.kind is SensorKind.DOOR
    assert sensor.decoded.active is True
    assert S1CSensor.from_library(
        {"status": 0, "name": "", "type": "Weird", "order": 9, "serial": "aabbccdd"}
    ).kind is SensorKind.UNKNOWN

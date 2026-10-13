"""Decoding of the raw S1C sensor status values.

The python-broadlink library returns the status of every sensor as a plain
integer and leaves the meaning to the caller. The tables below are the only
place where those integers are interpreted, so they are the only thing to
change if a value turns out to mean something else on your hardware.

This module is deliberately free of Home Assistant imports so that it can be
unit tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SensorKind(StrEnum):
    """Kind of accessory attached to the hub."""

    DOOR = "door"
    MOTION = "motion"
    KEY_FOB = "key_fob"
    UNKNOWN = "unknown"


# "type" strings returned by python-broadlink's S1C.get_sensors_status().
LIBRARY_TYPE_TO_KIND: dict[str, SensorKind] = {
    "Door Sensor": SensorKind.DOOR,
    "Motion Sensor": SensorKind.MOTION,
    "Key Fob": SensorKind.KEY_FOB,
}

# status -> (active, tamper)
#   door:   active = door is open
#   motion: active = motion detected
# None means "cannot tell" (shown as unknown in Home Assistant).
DoorMotionEntry = tuple[bool | None, bool | None]

# CONFIRMED on real hardware by the owner: 128 closed, 16 open, 48 tamper.
DOOR_STATUS: dict[int, DoorMotionEntry] = {
    128: (False, False),  # closed
    16: (True, False),  # open
    48: (None, True),  # tampered (housing opened)
}

# Taken from the older custom integration, not yet verified one by one.
MOTION_STATUS: dict[int, DoorMotionEntry] = {
    0: (False, False),
    64: (False, False),
    128: (False, False),
    16: (True, False),
    80: (True, False),
    32: (None, True),  # tampered
}

# Key fob: the status is the button that was pressed, 0 when idle.
KEY_FOB_IDLE: frozenset[int] = frozenset({0})
KEY_FOB_BUTTONS: dict[int, str] = {
    16: "disarm",
    32: "arm_away",
    64: "arm_home",
    128: "sos",
}
KEY_FOB_EVENT_TYPES: list[str] = list(KEY_FOB_BUTTONS.values())


@dataclass(frozen=True, slots=True)
class DecodedStatus:
    """The meaning of one raw status value."""

    known: bool
    active: bool | None = None  # door open / motion detected
    tamper: bool | None = None
    button: str | None = None  # key fob button currently reported


_UNKNOWN = DecodedStatus(known=False)


def decode_status(kind: SensorKind, status: int) -> DecodedStatus:
    """Translate a raw status integer for the given kind of sensor."""
    if kind is SensorKind.DOOR:
        entry = DOOR_STATUS.get(status)
    elif kind is SensorKind.MOTION:
        entry = MOTION_STATUS.get(status)
    elif kind is SensorKind.KEY_FOB:
        if status in KEY_FOB_IDLE:
            return DecodedStatus(known=True)
        button = KEY_FOB_BUTTONS.get(status)
        return DecodedStatus(known=True, button=button) if button else _UNKNOWN
    else:
        return _UNKNOWN

    if entry is None:
        return _UNKNOWN
    active, tamper = entry
    return DecodedStatus(known=True, active=active, tamper=tamper)


@dataclass(frozen=True, slots=True)
class S1CSensor:
    """One accessory as reported by the hub."""

    serial: str
    name: str
    kind: SensorKind
    status: int
    order: int

    @classmethod
    def from_library(cls, raw: dict[str, Any]) -> S1CSensor:
        """Build a sensor from an item of get_sensors_status()["sensors"]."""
        return cls(
            serial=str(raw["serial"]),
            name=str(raw["name"]).strip() or str(raw["serial"]),
            kind=LIBRARY_TYPE_TO_KIND.get(raw["type"], SensorKind.UNKNOWN),
            status=int(raw["status"]),
            order=int(raw["order"]),
        )

    @property
    def decoded(self) -> DecodedStatus:
        """Return the decoded status."""
        return decode_status(self.kind, self.status)

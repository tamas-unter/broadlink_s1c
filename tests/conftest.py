"""Fixtures: a fake S1C hub that is built on the real python-broadlink class."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from broadlink.alarm import S1C
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from custom_components.broadlink_s1c.const import DOMAIN

HOST = "192.168.1.131"
MAC = "34:ea:34:c8:46:d2"

# Exactly what the owner's hub reported in the first diagnostic run.
MOTION = "2102b091"
DOOR1 = "3101c958"
DOOR2 = "3101f060"
FOB = "91027cbf"


def sensor(serial: str, name: str, type_: str, order: int, status: int) -> dict[str, Any]:
    """Build one item of get_sensors_status()["sensors"]."""
    return {
        "status": status,
        "name": name,
        "type": type_,
        "order": order,
        "serial": serial,
    }


def default_sensors() -> list[dict[str, Any]]:
    """Return the four accessories of the owner's kit."""
    return [
        sensor(MOTION, "Wall-mounted IR Detec", "Motion Sensor", 1, 0),
        sensor(DOOR1, "Door1", "Door Sensor", 2, 16),
        sensor(DOOR2, "Door2", "Door Sensor", 3, 128),
        sensor(FOB, "Key Fob", "Key Fob", 4, 0),
    ]


class FakeS1C(S1C):
    """A real S1C object whose network calls are replaced."""

    def __init__(self) -> None:
        """Initialize the fake hub."""
        super().__init__((HOST, 80), bytes.fromhex(MAC.replace(":", "")), 0x2722, name="S1 Hub")
        self.sensors = default_sensors()
        self.fail_with: Exception | None = None
        self.auth_error: Exception | None = None
        self.closed = False

    def set_status(self, serial: str, status: int) -> None:
        """Change the status of one accessory."""
        for item in self.sensors:
            if item["serial"] == serial:
                item["status"] = status
                return
        raise KeyError(serial)

    async def auth(self) -> bool:
        """Pretend to authenticate."""
        if self.auth_error:
            raise self.auth_error
        return True

    async def get_fwversion(self) -> int:
        """Return a firmware version."""
        return 41

    async def get_sensors_status(self) -> dict:
        """Return the configured sensors, or fail."""
        if self.fail_with:
            raise self.fail_with
        return {"count": len(self.sensors), "sensors": [dict(s) for s in self.sensors]}

    async def aclose(self) -> None:
        """Record the close."""
        self.closed = True


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components/ from this repository."""


@pytest.fixture
def hub() -> Generator[FakeS1C]:
    """Patch the library so that every connection returns the same fake hub."""
    fake = FakeS1C()
    with (
        patch("broadlink.hello", AsyncMock(return_value=fake)),
        patch("broadlink.gendevice", return_value=fake),
    ):
        yield fake


@pytest.fixture
def entry() -> MockConfigEntry:
    """Return a config entry for the hub."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="S1 Hub",
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MAC: MAC},
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry and set it up."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

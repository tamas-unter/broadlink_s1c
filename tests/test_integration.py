"""Tests of the entities, driven by a fake hub."""

from __future__ import annotations

from broadlink import exceptions as e
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.broadlink_s1c.const import DOMAIN

from .conftest import DOOR1, DOOR2, FOB, MAC, MOTION, FakeS1C, sensor, setup_entry


def _state(hass: HomeAssistant, domain: str, serial: str, key: str):
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{MAC}_{serial}_{key}"
    )
    assert entity_id, f"no {domain} entity for {serial}/{key}"
    return hass.states.get(entity_id)


async def _poll(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_entities_for_the_owners_kit(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Initial states match the first diagnostic run of the real hub."""
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    # Door1 reported 16 (open), Door2 reported 128 (closed).
    assert _state(hass, "binary_sensor", DOOR1, "state").state == STATE_ON
    assert _state(hass, "binary_sensor", DOOR2, "state").state == STATE_OFF
    assert _state(hass, "binary_sensor", MOTION, "state").state == STATE_OFF
    for serial in (DOOR1, DOOR2, MOTION):
        assert _state(hass, "binary_sensor", serial, "tamper").state == STATE_OFF
    assert _state(hass, "event", FOB, "button").state == STATE_UNKNOWN

    door1 = _state(hass, "binary_sensor", DOOR1, "state")
    assert door1.attributes["device_class"] == "door"
    assert door1.attributes["raw_status"] == 16
    assert _state(hass, "binary_sensor", MOTION, "state").attributes["device_class"] == "motion"
    assert _state(hass, "binary_sensor", DOOR1, "tamper").attributes["device_class"] == "tamper"


async def test_devices(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """The hub and each accessory are separate devices linked together."""
    await setup_entry(hass, entry)
    registry = dr.async_get(hass)

    hub_device = registry.async_get_device(identifiers={(DOMAIN, MAC)})
    assert hub_device is not None
    assert hub_device.manufacturer == "Broadlink"
    assert hub_device.sw_version == "41"

    door = registry.async_get_device(identifiers={(DOMAIN, f"{MAC}_{DOOR1}")})
    assert door is not None
    assert door.name == "Door1"
    assert door.via_device_id == hub_device.id
    assert door.serial_number == DOOR1


async def test_door_and_motion_follow_the_hub(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Open, closed, tamper and motion values are reflected."""
    await setup_entry(hass, entry)

    hub.set_status(DOOR1, 128)
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", DOOR1, "state").state == STATE_OFF

    hub.set_status(DOOR1, 16)
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", DOOR1, "state").state == STATE_ON

    hub.set_status(DOOR1, 48)
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", DOOR1, "tamper").state == STATE_ON
    assert _state(hass, "binary_sensor", DOOR1, "state").state == STATE_UNKNOWN

    hub.set_status(MOTION, 16)
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", MOTION, "state").state == STATE_ON
    hub.set_status(MOTION, 0)
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", MOTION, "state").state == STATE_OFF


async def test_unmapped_status_is_unknown_and_logged_once(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry, caplog
) -> None:
    """A value nobody has confirmed is never guessed."""
    await setup_entry(hass, entry)
    hub.set_status(DOOR2, 144)
    await _poll(hass, entry)
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", DOOR2, "state").state == STATE_UNKNOWN
    assert caplog.text.count("reported status 144") == 1


async def test_key_fob_buttons(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Each button press fires one event; going back to idle fires none."""
    await setup_entry(hass, entry)

    for status, expected in ((64, "arm_home"), (32, "arm_away"), (16, "disarm"), (128, "sos")):
        hub.set_status(FOB, status)
        await _poll(hass, entry)
        state = _state(hass, "event", FOB, "button")
        assert state.attributes["event_type"] == expected
        stamp = state.state
        assert stamp != STATE_UNKNOWN

        hub.set_status(FOB, 0)  # released: no new event
        await _poll(hass, entry)
        assert _state(hass, "event", FOB, "button").state == stamp


async def test_no_stale_event_at_startup(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """A button still latched when Home Assistant starts is not reported."""
    hub.set_status(FOB, 16)
    await setup_entry(hass, entry)
    assert _state(hass, "event", FOB, "button").state == STATE_UNKNOWN

    hub.set_status(FOB, 0)
    await _poll(hass, entry)
    hub.set_status(FOB, 16)
    await _poll(hass, entry)
    assert _state(hass, "event", FOB, "button").attributes["event_type"] == "disarm"


async def test_unavailable_when_the_hub_does_not_answer(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """A dead hub makes everything unavailable and it recovers by itself."""
    await setup_entry(hass, entry)

    hub.fail_with = e.NetworkTimeoutError(-4000, "Network timeout", "no reply")
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", DOOR1, "state").state == STATE_UNAVAILABLE
    assert _state(hass, "event", FOB, "button").state == STATE_UNAVAILABLE

    hub.fail_with = None
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", DOOR1, "state").state == STATE_ON


async def test_sensor_removed_and_added(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Accessories dropped by the hub go unavailable; new ones appear by themselves."""
    await setup_entry(hass, entry)

    hub.sensors = [s for s in hub.sensors if s["serial"] != DOOR2]
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", DOOR2, "state").state == STATE_UNAVAILABLE

    hub.sensors.append(sensor("3101aaaa", "Door3", "Door Sensor", 5, 128))
    hub.sensors.append(sensor("9102bbbb", "Key Fob 2", "Key Fob", 6, 0))
    await _poll(hass, entry)
    assert _state(hass, "binary_sensor", "3101aaaa", "state").state == STATE_OFF
    assert _state(hass, "event", "9102bbbb", "button").state == STATE_UNKNOWN


async def test_setup_retries_when_the_hub_is_unreachable(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Setup is retried later instead of failing for good."""
    hub.auth_error = e.NetworkTimeoutError(-4000, "Network timeout", "no reply")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_closes_the_connection(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Unloading removes the entities and closes the UDP endpoint."""
    await setup_entry(hass, entry)
    assert not hub.closed
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hub.closed
    assert _state(hass, "binary_sensor", DOOR1, "state").state == STATE_UNAVAILABLE


async def test_diagnostics_redacts_identifiers(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Diagnostics can be shared without exposing the network details."""
    from custom_components.broadlink_s1c.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    await setup_entry(hass, entry)
    data = await async_get_config_entry_diagnostics(hass, entry)
    text = str(data)
    assert "192.168.1.131" not in text
    assert MAC not in text
    assert DOOR1 not in text
    assert data["firmware"] == 41
    assert {s["status"] for s in data["sensors"]} == {0, 16, 128}

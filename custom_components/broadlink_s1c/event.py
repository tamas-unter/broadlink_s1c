"""Event entities: the buttons of the key fob."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import S1CConfigEntry, S1CCoordinator
from .entity import S1CEntity
from .status import KEY_FOB_EVENT_TYPES, SensorKind


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S1CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an event entity for every key fob, now and when new ones appear."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_fobs() -> None:
        new = [
            S1CKeyFobEvent(coordinator, serial)
            for serial, sensor in coordinator.data.items()
            if serial not in known and sensor.kind is SensorKind.KEY_FOB
        ]
        known.update(entity._serial for entity in new)  # noqa: SLF001
        if new:
            async_add_entities(new)

    _add_new_fobs()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_fobs))


class S1CKeyFobEvent(S1CEntity, EventEntity):
    """Fires an event whenever a button of the key fob is pressed.

    The hub is polled, so a press is only seen if the hub still reports it at
    the next poll. Pressing the same button again while the hub still shows
    the previous press cannot be told apart from the first press.
    """

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = KEY_FOB_EVENT_TYPES
    _attr_translation_key = "button"

    def __init__(self, coordinator: S1CCoordinator, serial: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, serial, "button")
        # Remember the status at startup so that a button that was pressed
        # before Home Assistant started does not fire a stale event.
        self._last_status = coordinator.data[serial].status

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire an event when the status changes to a button press."""
        sensor = self.sensor
        if sensor is not None and sensor.status != self._last_status:
            self._last_status = sensor.status
            if (button := sensor.decoded.button) is not None:
                self._trigger_event(button, {"raw_status": sensor.status})
        super()._handle_coordinator_update()

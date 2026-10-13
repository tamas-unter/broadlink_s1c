"""Binary sensors: door contacts, motion detectors and their tamper switches."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import S1CConfigEntry, S1CCoordinator
from .entity import S1CEntity
from .status import SensorKind


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S1CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for every door and motion sensor, now and when new ones appear."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_sensors() -> None:
        new: list[S1CEntity] = []
        for serial, sensor in coordinator.data.items():
            if serial in known or sensor.kind not in (
                SensorKind.DOOR,
                SensorKind.MOTION,
            ):
                continue
            known.add(serial)
            new.append(S1CStateSensor(coordinator, serial))
            new.append(S1CTamperSensor(coordinator, serial))
        if new:
            async_add_entities(new)

    _add_new_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_sensors))


class S1CStateSensor(S1CEntity, BinarySensorEntity):
    """Door open/closed or motion detected, depending on the accessory."""

    _attr_name = None  # use the name of the accessory itself

    def __init__(self, coordinator: S1CCoordinator, serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial, "state")
        if coordinator.data[serial].kind is SensorKind.DOOR:
            self._attr_device_class = BinarySensorDeviceClass.DOOR
        else:
            self._attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def is_on(self) -> bool | None:
        """Return true when the door is open or motion is detected."""
        sensor = self.sensor
        return sensor.decoded.active if sensor else None


class S1CTamperSensor(S1CEntity, BinarySensorEntity):
    """Tamper switch of a door or motion sensor."""

    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: S1CCoordinator, serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial, "tamper")

    @property
    def is_on(self) -> bool | None:
        """Return true when the housing was opened."""
        sensor = self.sensor
        return sensor.decoded.tamper if sensor else None

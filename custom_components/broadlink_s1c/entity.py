"""Base entity for the accessories of the S1C hub."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import S1CCoordinator
from .status import S1CSensor, SensorKind

_MODEL_NAMES = {
    SensorKind.DOOR: "Door sensor",
    SensorKind.MOTION: "Motion sensor",
    SensorKind.KEY_FOB: "Key fob",
}


class S1CEntity(CoordinatorEntity[S1CCoordinator]):
    """One entity of one accessory; each accessory is its own device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: S1CCoordinator, serial: str, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._serial = serial
        sensor = coordinator.data[serial]
        self._attr_unique_id = f"{coordinator.mac}_{serial}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.mac}_{serial}")},
            via_device=(DOMAIN, coordinator.mac),
            name=sensor.name,
            manufacturer=MANUFACTURER,
            model=_MODEL_NAMES.get(sensor.kind),
            serial_number=serial,
        )

    @property
    def sensor(self) -> S1CSensor | None:
        """Return the latest data of this accessory, if the hub still lists it."""
        return self.coordinator.data.get(self._serial)

    @property
    def available(self) -> bool:
        """Unavailable when the hub cannot be reached or dropped the accessory."""
        return super().available and self.sensor is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the raw status, handy for checking the mapping."""
        if (sensor := self.sensor) is None:
            return None
        return {"raw_status": sensor.status}

"""Polling coordinator for the S1C alarm hub."""

from __future__ import annotations

from datetime import timedelta
import logging

from broadlink import exceptions as e
from broadlink.alarm import S1C

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .status import S1CSensor, SensorKind

_LOGGER = logging.getLogger(__name__)

type S1CConfigEntry = ConfigEntry[S1CCoordinator]


class S1CCoordinator(DataUpdateCoordinator[dict[str, S1CSensor]]):
    """Poll the hub and keep the state of every accessory, keyed by serial."""

    config_entry: S1CConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: S1CConfigEntry, device: S1C
    ) -> None:
        """Initialize the coordinator."""
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(seconds=interval),
            # Only wake the entities when something actually changed.
            always_update=False,
        )
        self.device = device
        self.mac = format_mac(device.mac.hex())
        self.fw_version: int | None = None
        self._warned: set[tuple[str, int]] = set()

    async def _async_update_data(self) -> dict[str, S1CSensor]:
        """Read all sensors from the hub."""
        try:
            raw = await self.device.get_sensors_status()
            sensors = [S1CSensor.from_library(item) for item in raw["sensors"]]
        # ValueError covers a sensor name the library cannot decode.
        except (e.BroadlinkException, OSError, ValueError, KeyError) as err:
            raise UpdateFailed(f"Error communicating with the hub: {err}") from err

        for sensor in sensors:
            key = (sensor.serial, sensor.status)
            if (
                sensor.kind is not SensorKind.UNKNOWN
                and not sensor.decoded.known
                and key not in self._warned
            ):
                self._warned.add(key)
                _LOGGER.warning(
                    "%s %r (serial %s) reported status %d, which has no known "
                    "meaning; please report it so the mapping can be extended",
                    sensor.kind.value,
                    sensor.name,
                    sensor.serial,
                    sensor.status,
                )
        return {sensor.serial: sensor for sensor in sensors}

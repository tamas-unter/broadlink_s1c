"""Diagnostics for the Broadlink S1C Alarm Hub integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .coordinator import S1CConfigEntry

TO_REDACT = {CONF_HOST, CONF_MAC, "serial", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: S1CConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "firmware": coordinator.fw_version,
        "sensors": [
            async_redact_data(
                {**asdict(sensor), "decoded": asdict(sensor.decoded)}, TO_REDACT
            )
            for sensor in (coordinator.data or {}).values()
        ],
    }

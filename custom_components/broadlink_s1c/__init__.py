"""The Broadlink S1C Alarm Hub integration."""

from __future__ import annotations

from broadlink import exceptions as e

from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .api import CannotConnect, InvalidAuth, async_connect
from .const import DOMAIN, HUB_MODEL, MANUFACTURER
from .coordinator import S1CConfigEntry, S1CCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: S1CConfigEntry) -> bool:
    """Set up the hub from a config entry."""
    try:
        device = await async_connect(entry.data[CONF_HOST], entry.data[CONF_MAC])
    except (CannotConnect, InvalidAuth) as err:
        raise ConfigEntryNotReady(f"Cannot reach the hub: {err}") from err
    # Runs on unload and also when the setup fails further down.
    entry.async_on_unload(device.aclose)

    coordinator = S1CCoordinator(hass, entry, device)
    try:
        coordinator.fw_version = await device.get_fwversion()
    except (e.BroadlinkException, OSError):
        coordinator.fw_version = None  # informational only
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.mac)},
        connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac)},
        manufacturer=MANUFACTURER,
        model=HUB_MODEL,
        name=entry.title,
        sw_version=str(coordinator.fw_version) if coordinator.fw_version else None,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: S1CConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: S1CConfigEntry) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)

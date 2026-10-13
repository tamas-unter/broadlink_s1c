"""Config flow for the Broadlink S1C Alarm Hub integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from .api import (
    CannotConnect,
    InvalidAuth,
    InvalidMac,
    NotSupported,
    async_connect,
)
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_MAC, default=""): str,
    }
)


class S1CConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup of a hub."""

    VERSION = 1

    async def _async_try_connect(
        self, host: str, mac: str
    ) -> tuple[dict[str, str], Any]:
        """Connect to the hub; return (errors, device)."""
        try:
            device = await async_connect(host, mac or None)
        except InvalidMac:
            return {CONF_MAC: "invalid_mac"}, None
        except CannotConnect:
            return {"base": "cannot_connect"}, None
        except InvalidAuth:
            return {"base": "invalid_auth"}, None
        except NotSupported:
            return {"base": "not_supported"}, None
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while connecting to the hub")
            return {"base": "unknown"}, None
        return {}, device

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the host (and optionally the MAC) of the hub."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            errors, device = await self._async_try_connect(
                host, user_input.get(CONF_MAC, "").strip()
            )
            if device is not None:
                mac = format_mac(device.mac.hex())
                name = device.name or "S1C Alarm Hub"
                await device.aclose()
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=name, data={CONF_HOST: host, CONF_MAC: mac}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of an existing hub."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            errors, device = await self._async_try_connect(host, entry.data[CONF_MAC])
            if device is not None:
                await device.aclose()
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_HOST): str}),
                user_input or {CONF_HOST: entry.data[CONF_HOST]},
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> S1COptionsFlow:
        """Return the options flow."""
        return S1COptionsFlow()


class S1COptionsFlow(OptionsFlow):
    """Options: how often the hub is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )

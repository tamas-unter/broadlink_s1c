"""Tests of the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from broadlink import exceptions as e
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.broadlink_s1c.const import DOMAIN

from .conftest import HOST, MAC, FakeS1C, setup_entry


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow_discovers_mac(hass: HomeAssistant, hub: FakeS1C) -> None:
    """Only the host is entered; the MAC comes from the hub."""
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.broadlink_s1c.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "S1 Hub"
    assert result["data"] == {CONF_HOST: HOST, CONF_MAC: MAC}
    assert result["result"].unique_id == MAC
    assert hub.closed  # the probe connection is closed again


async def test_user_flow_with_manual_mac(hass: HomeAssistant, hub: FakeS1C) -> None:
    """A MAC address skips the discovery step."""
    result = await _start(hass)
    with patch(
        "custom_components.broadlink_s1c.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_MAC: "34-EA-34-C8-46-D2"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == MAC


@pytest.mark.parametrize(
    ("setup", "field", "error"),
    [
        ("hello_timeout", "base", "cannot_connect"),
        ("auth_denied", "base", "invalid_auth"),
        ("auth_timeout", "base", "cannot_connect"),
        ("bad_mac", CONF_MAC, "invalid_mac"),
        ("wrong_device", "base", "not_supported"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, hub: FakeS1C, setup: str, field: str, error: str
) -> None:
    """Every failure shows an error and the flow can be retried."""
    user_input = {CONF_HOST: HOST}
    patches = []
    if setup == "hello_timeout":
        patches.append(
            patch(
                "broadlink.hello",
                AsyncMock(side_effect=e.NetworkTimeoutError(-4000, "Network timeout")),
            )
        )
    elif setup == "auth_denied":
        hub.auth_error = e.AuthenticationError(-1, "Authentication failed")
    elif setup == "auth_timeout":
        hub.auth_error = e.NetworkTimeoutError(-4000, "Network timeout")
    elif setup == "bad_mac":
        user_input[CONF_MAC] = "not a mac"
    elif setup == "wrong_device":
        # A plain Device is what the library returns for unknown products.
        from broadlink.device import Device

        other = Device((HOST, 80), bytes(6), 0x1234)
        patches.append(patch("broadlink.hello", AsyncMock(return_value=other)))

    result = await _start(hass)
    for p in patches:
        p.start()
    try:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    finally:
        for p in patches:
            p.stop()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}

    # The user fixes the problem and the flow completes.
    hub.auth_error = None
    with patch(
        "custom_components.broadlink_s1c.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured_updates_host(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """Adding the same hub twice aborts and keeps the entry, with the new host."""
    entry.add_to_hass(hass)
    result = await _start(hass)
    with patch(
        "custom_components.broadlink_s1c.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.200"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.200"


async def test_reconfigure(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """The address of a configured hub can be changed."""
    await setup_entry(hass, entry)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.201"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.201"


async def test_options_flow(
    hass: HomeAssistant, hub: FakeS1C, entry: MockConfigEntry
) -> None:
    """The polling interval can be changed and is applied."""
    await setup_entry(hass, entry)
    assert entry.runtime_data.update_interval.total_seconds() == 2

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_SCAN_INTERVAL] == 5
    assert entry.runtime_data.update_interval.total_seconds() == 5

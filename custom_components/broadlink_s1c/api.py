"""Connection helper for the S1C alarm hub."""

from __future__ import annotations

import broadlink
from broadlink import exceptions as e
from broadlink.alarm import S1C

from .const import DEFAULT_PORT, DEVICE_TIMEOUT, DEVICE_TYPE_S2KIT


class S1CError(Exception):
    """Base class for connection problems."""


class CannotConnect(S1CError):
    """The hub did not answer."""


class InvalidAuth(S1CError):
    """The hub refused the authentication (for example because it is locked)."""


class InvalidMac(S1CError):
    """The MAC address is not valid."""


class NotSupported(S1CError):
    """The device at this address is not an S1C alarm hub."""


def parse_mac(mac: str) -> bytes:
    """Convert a MAC address in any usual notation to 6 bytes."""
    cleaned = mac.replace(":", "").replace("-", "").replace(".", "").strip()
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError as err:
        raise InvalidMac(mac) from err
    if len(raw) != 6:
        raise InvalidMac(mac)
    return raw


async def async_connect(
    host: str, mac: str | None = None, port: int = DEFAULT_PORT
) -> S1C:
    """Return an authenticated S1C device.

    With a MAC address the device object is built directly, without any
    discovery. Without one, the hub is asked for its details first.
    """
    if mac:
        device = broadlink.gendevice(DEVICE_TYPE_S2KIT, (host, port), parse_mac(mac))
    else:
        try:
            device = await broadlink.hello(host, port=port, timeout=DEVICE_TIMEOUT)
        except (e.BroadlinkException, OSError) as err:
            raise CannotConnect(str(err)) from err

    if not isinstance(device, S1C):
        await device.aclose()
        raise NotSupported(f"{host} is a {device.type!r}, not an S1C hub")

    device.timeout = DEVICE_TIMEOUT
    try:
        await device.auth()
    except (e.AuthenticationError, e.AuthorizationError) as err:
        await device.aclose()
        raise InvalidAuth(str(err)) from err
    except (e.BroadlinkException, OSError) as err:
        await device.aclose()
        raise CannotConnect(str(err)) from err
    return device

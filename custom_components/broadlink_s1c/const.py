"""Constants for the Broadlink S1C Alarm Hub integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "broadlink_s1c"

# Broadlink product ID of the S2KIT alarm kit hub (handled by the S1C class).
DEVICE_TYPE_S2KIT: Final = 0x2722
DEFAULT_PORT: Final = 80

# Network timeout (seconds) used for the hub. The library default is 10 s,
# which makes an offline hub block each poll for far too long.
DEVICE_TIMEOUT: Final = 5

DEFAULT_SCAN_INTERVAL: Final = 2  # seconds
MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 60

MANUFACTURER: Final = "Broadlink"
HUB_MODEL: Final = "S2KIT alarm hub (S1C)"

<p align="center">
  <img src="assets/logo.svg" alt="S1C Alarm Hub, DIY Home Assistant integration" width="440">
</p>

# Broadlink S1C Alarm Hub for Home Assistant

A custom integration for the **Broadlink S1C / S2KIT alarm hub** and its accessories (door sensors, PIR motion sensors, key fobs). The official Broadlink integration does not support this hub.

It is written from scratch on top of [python-broadlink](https://github.com/mjg59/python-broadlink) 1.0.6 (fully asyncio) and talks to the hub locally over UDP. No cloud is involved.

> **Not affiliated with Broadlink.** "Broadlink" is a trademark of its owner and is used here only to say which hardware this works with. The icon in this repository is an original drawing.

## Features

- Set up from the UI with the **IP address** of the hub. The MAC address is read from the hub (you can enter it by hand if detection fails).
- Every accessory the hub knows about becomes its own device, linked to the hub, identified by its serial number.
- New accessories paired later show up by themselves, no reload needed.
- Entities are marked unavailable while the hub cannot be reached, and recover on their own.
- Adjustable polling interval (1 to 60 seconds, default 2).
- Diagnostics download with IP, MAC and serial numbers redacted.

## Entities

| Accessory | Entities |
|---|---|
| Door sensor | `binary_sensor` (device class *door*, on = open) and a *tamper* `binary_sensor` (diagnostic) |
| Motion sensor | `binary_sensor` (device class *motion*) and a *tamper* `binary_sensor` (diagnostic) |
| Key fob | one `event` entity, event types `disarm`, `arm_away`, `arm_home`, `sos` |

Each entity also has a `raw_status` attribute with the number reported by the hub, which is handy when checking the mapping below.

### Status mapping

The hub only reports a number per accessory. This is how the integration reads it (see `custom_components/broadlink_s1c/status.py`, the only place to change):

| Accessory | Status | Meaning | Verified |
|---|---|---|---|
| Door | 128 | closed | yes |
| Door | 16 | open | yes |
| Door | 48 | tampered | taken from the owner's notes, tamper not physically tested |
| Motion | 0, 64, 128 | no motion | taken from an older integration |
| Motion | 16, 80 | motion detected | taken from an older integration |
| Motion | 32 | tampered | taken from an older integration |
| Key fob | 0 | idle | observed |
| Key fob | 16 / 32 / 64 / 128 | disarm / arm away / arm home / SOS | taken from an older integration |

Any other number is shown as *unknown* (never guessed) and logged once as a warning with the raw value. If you see that warning, please open an issue with the value and what the accessory was doing.

### Key fob behaviour

The hub is polled, it does not push. A button press is turned into one event when the status changes to that button's value. A very short press can fall between two polls, and pressing the same button again while the hub still shows the previous press looks like no change. If you miss presses, lower the polling interval in the integration options.

A button that is still reported when Home Assistant starts does not fire a stale event.

## Installation

### HACS (custom repository)

1. HACS, then the three dots, then **Custom repositories**.
2. Add `https://github.com/tamas-unter/broadlink_s1c` with category **Integration**.
3. Install **Broadlink S1C Alarm Hub (DIY)** and restart Home Assistant.

### Manual

Copy `custom_components/broadlink_s1c` into the `custom_components` folder of your Home Assistant configuration and restart.

## Setup

1. **Settings, Devices & services, Add integration, Broadlink S1C Alarm Hub.**
2. Enter the IP address of the hub. Give it a fixed address (DHCP reservation) in your router.
3. Leave the MAC empty unless detection fails.

If the hub is locked in the Broadlink app, authentication is refused. Unlock it there first.

## Requirements

- Tested against Home Assistant 2026.2.3. `hacs.json` asks for 2025.1.0 or newer, but older releases than the tested one have not been tried. Brand images in the integration's `brand/` folder are used from 2026.3.
- `python-broadlink==1.0.6`, installed by Home Assistant from `manifest.json`. The core Broadlink integration pins its own version of the same package. If a future Home Assistant release pins a different one and the two conflict, relax the pin in `manifest.json` (for example to `python-broadlink>=1.0.6`).

## Known limitations

- Read only. The library has no command to arm or disarm the hub, so there is no alarm control panel.
- The library decodes accessory names as text. A name containing characters that get cut in the middle of a multi-byte sequence (for example long non-Latin names) makes the whole poll fail. If all entities stay unavailable, check the log and rename the accessory in the Broadlink app.
- Firmware 53 and newer reportedly needs a ping every 2 minutes when the hub cannot reach its cloud. The development hub runs firmware 41, so this is not implemented.

## Development

```bash
pip install -r requirements_test.txt
python -m pytest
```

The tests run a real Home Assistant core against a fake hub built on the real `S1C` class. Pull requests are checked by `hassfest` and the HACS action (`.github/workflows`).

## License

MIT, see [LICENSE](LICENSE).

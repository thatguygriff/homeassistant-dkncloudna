# DKN Cloud NA — Home Assistant Integration

[![HACS][hacs-badge]][hacs-url]
[![Validate][validate-badge]][validate-url]

Control your Daikin mini-split air conditioners through Home Assistant using the DKN Cloud NA cloud service.

This integration is a port of the [homebridge-dkncloudna](https://github.com/plecong/homebridge-dkncloudna) plugin by [@plecong](https://github.com/plecong), adapted for Home Assistant and distributed via HACS.

---

## Supported Hardware

Any Daikin mini-split system connected to the **DKN Cloud NA** WiFi adapter (North America). The adapter must be set up and working in the official DKN Cloud NA mobile app before using this integration.

---

## Prerequisites

- A working [DKN Cloud NA](https://dkncloudna.com) account
- Your Daikin unit(s) already set up and visible in the DKN Cloud NA app
- Home Assistant 2024.1 or later
- HACS 2.0 or later

---

## Installation

### Via HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations**
3. Click the **⋮** menu → **Custom repositories**
4. Add `https://github.com/thatguygriff/homeassistant-dkncloudna` as an **Integration**
5. Search for **DKN Cloud NA** and install it
6. Restart Home Assistant

### Manual

Copy the `custom_components/dkncloudna/` directory into your Home Assistant `config/custom_components/` directory and restart.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **DKN Cloud NA**
3. Enter your DKN Cloud NA email and password
4. Optionally adjust the scan interval (default: 60 seconds)
5. Optionally enable **Show tokens after login** to view your access and refresh tokens

All discovered devices are added automatically.

---

## Entities

Each device exposes the following entities:

| Entity | Type | Description |
|---|---|---|
| AC unit | `climate` | On/off, mode (auto/cool/heat/dry/fan), target temperature, fan speed, swing |
| Room temperature | `sensor` | Current room temperature (°C) |
| Exterior temperature | `sensor` | Outdoor temperature (°C) — disabled by default |
| Wi-Fi signal | `sensor` | RSSI in dBm — diagnostic |
| Error code | `sensor` | Active error code — diagnostic |
| Connected | `binary_sensor` | Whether the device is online — diagnostic |
| Machine ready | `binary_sensor` | Whether the device is ready to receive commands — diagnostic |

---

## How It Works

- **Authentication.** The integration exchanges your DKN Cloud NA credentials for access + refresh tokens on first setup, then uses the refresh token to keep the session alive. Refreshed tokens are persisted to the config entry so they survive restarts.
- **Device discovery and polling.** All installations and their devices are fetched from the REST API on a configurable interval (default 60 seconds). The poll establishes the device list and acts as a heartbeat against the cloud.
- **Live updates via Socket.IO.** While the integration is running, it maintains a Socket.IO connection to dkncloudna.com and applies `device-data` events to entity state in near real-time — no waiting for the next poll cycle.
- **Control via Socket.IO.** Mode, target temperature, fan speed, and swing commands are sent as Socket.IO machine events. Local changes are reflected optimistically in Home Assistant and reconciled when the cloud echoes the new state back.
- **Temperature units.** Home Assistant always presents temperatures in Celsius. Devices reporting in Fahrenheit are transparently converted in both directions — values you set in HA are sent to the device in its native units.

## Known Limitations

- Reauthentication is required if your refresh token expires (e.g. you change your DKN Cloud NA password). Home Assistant will surface a "Reconfigure" prompt when this happens.
- Multi-zone systems are exposed as one climate entity per indoor unit; there is no aggregate "installation" entity.

---

## Credits

- Original Homebridge plugin: [homebridge-dkncloudna](https://github.com/plecong/homebridge-dkncloudna) by [@plecong](https://github.com/plecong)
- EU counterpart inspiration: [DKNCloud-HASS](https://github.com/eXPerience83/DKNCloud-HASS) by [@eXPerience83](https://github.com/eXPerience83)

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[hacs-url]: https://github.com/hacs/integration
[validate-badge]: https://github.com/lavoiesl/homeassistant-dkncloudna/actions/workflows/validate.yml/badge.svg
[validate-url]: https://github.com/lavoiesl/homeassistant-dkncloudna/actions/workflows/validate.yml

# DKN Cloud NA — Home Assistant Integration: Design

**Date:** 2026-03-29
**Status:** Approved
**Scope:** Scaffolding only — no live Daikin API calls yet

---

## Background

This integration ports the [homebridge-dkncloudna](https://github.com/plecong/homebridge-dkncloudna) plugin to Home Assistant as a HACS custom integration. It targets Daikin mini-split AC systems connected via the DKN Cloud NA WiFi adapter.

The EU counterpart [DKNCloud-HASS](https://github.com/eXPerience83/DKNCloud-HASS) (airzone) provided reference patterns for coordinator structure, config flow hygiene, and optimistic overlays. We diverge where the NA API differs or where simpler approaches suffice.

---

## Source References

- **Homebridge plugin (NA):** `/Users/slavoie2/src/github.com/plecong/homebridge-dkncloudna`
- **EU HA reference:** `/Users/slavoie2/src/github.com/eXPerience83/DKNCloud-HASS`
- **Target repo:** `https://github.com/lavoiesl/homeassistant-dkncloudna`

---

## Architecture

```
Config Entry
  data:    { username }
  options: { user_token, refresh_token, scan_interval, expose_pii }
      ↓
DknCoordinator  (DataUpdateCoordinator, default 60s)
      ↓
DknCloudNaClient  (login, token refresh, fetch_installations)
      ↓
Platforms: climate · sensor · binary_sensor
```

**Key decisions:**
- **Cloud polling only** — no Socket.IO. Simpler, more maintainable, idiomatic for HA cloud integrations.
- **60s default poll interval** — reasonable for an AC unit; configurable 30–300s.
- **Password never persisted** — cleared after login; only tokens stored in `entry.options`.
- **Optimistic overlays** — 2.5s TTL bridges write→poll latency, borrowed from EU reference.
- **Per-device async locks** — serializes concurrent writes per device.

---

## DKN Cloud NA API (from homebridge plugin)

**Base URL:** `https://dkncloudna.com/api/v1`

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/login/dknUsa` | POST | Login (email + password → token + refreshToken) |
| `/users/isLoggedIn/dknUsa` | GET | Validate token |
| `/auth/refreshToken/{refreshToken}/dknUsa` | GET | Refresh expired token |
| `/installations/dknUsa` | GET | Fetch all installations + devices |

**Auth:** Bearer token. User-Agent spoofs iPhone iOS 15.5 (required by the API).

**Device control:** Socket.IO `create-machine-event` — deferred to implementation phase.

---

## File Structure

```
custom_components/dkncloudna/
├── __init__.py          # async_setup_entry, async_unload_entry
├── manifest.json        # domain, codeowners, version, iot_class
├── const.py             # DOMAIN, BASE_URL, API paths, timing constants
├── api.py               # DknCloudNaClient (stub)
├── coordinator.py       # DknCoordinator (stub data)
├── config_flow.py       # user → token_display → options / reauth
├── entity.py            # DknEntity base class (CoordinatorEntity)
├── climate.py           # DknClimateEntity stub
├── sensor.py            # DknSensorEntity stubs
├── binary_sensor.py     # DknBinarySensorEntity stubs
├── strings.json         # mirrors en.json
└── translations/
    └── en.json          # config flow + entity strings

hacs.json
README.md
.github/workflows/validate.yml
```

---

## Config Flow

### Steps

1. **`user`** — email, password, scan_interval (30–300s, default 60)
2. **`token_display`** — shows access_token + refresh_token read-only (skipped if `expose_pii=False`)
3. **Options flow** — scan_interval, expose_pii toggle
4. **Reauth** — re-presents `user` step; clears password after new token obtained

### Data storage

- `entry.data`: `{ username }`
- `entry.options`: `{ user_token, refresh_token, scan_interval, expose_pii }`
- Password: never stored, cleared immediately after token exchange

---

## Entities Per Device

### Climate (1 per device)

- **HVAC modes:** OFF, COOL, HEAT, AUTO, DRY, FAN_ONLY
- **Features:** TARGET_TEMPERATURE, FAN_MODE, SWING_MODE, TURN_ON, TURN_OFF
- **Dynamic:** TARGET_TEMPERATURE hidden in DRY / FAN_ONLY / OFF modes
- **Unique ID:** `dkncloudna_{mac}`

### Sensors (per device)

| Entity | Key | Unit | Category | Default |
|---|---|---|---|---|
| Room temperature | `work_temp` | °C | — | enabled |
| Exterior temperature | `ext_temp` | °C | — | disabled |
| WiFi signal | `stat_rssi` | dBm | diagnostic | enabled |
| Error code | `error_ascii1/2` | — | diagnostic | enabled |

### Binary sensors (per device)

| Entity | Key | Category |
|---|---|---|
| Connected | `isConnected` | diagnostic |
| Machine ready | `machineready` | diagnostic |

---

## Patterns from EU Reference (Adopted)

| Pattern | Source | Notes |
|---|---|---|
| Optimistic overlay (2.5s TTL) | EU ref | Bridges write→poll latency |
| Per-device asyncio.Lock | EU ref | Serializes concurrent writes |
| Password cleared post-login | EU ref | Security hygiene |
| Reauth on 401 | EU ref | Standard HA pattern |
| Dynamic supported_features | EU ref | Mode-aware feature set |
| Backoff + jitter retry | EU ref + homebridge | Robust API resilience |

## Patterns Omitted

| Pattern | Reason |
|---|---|
| persistent_notification | Legacy — use HA issue API in future |
| Switch entity (power proxy) | Redundant with climate turn_on/off |
| Number entities (sleep/unoccupied) | NA API has no such concepts |
| 40+ sensor dump | Only expose meaningful entities |

---

## README Sections

1. What it is + supported devices
2. Prerequisites (DKN Cloud NA account)
3. Installation via HACS
4. Configuration walkthrough (config flow steps)
5. Entities reference table
6. Known limitations & roadmap
7. Credits (homebridge plugin by @plecong, EU reference by @eXPerience83)

---

## Validation CI

Two jobs in `.github/workflows/validate.yml`:
- `hassfest` — validates manifest against HA schema
- `hacs` — validates HACS requirements (with `ignore: brands` until icon added)

# DKN Cloud NA — Scaffolding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a complete, HACS-valid integration scaffolding with stub entities, working config flow, and README — no live Daikin API calls yet.

**Architecture:** Cloud-polling integration under `custom_components/dkncloudna/`. A `DataUpdateCoordinator` drives all entity updates. Config flow collects email+password, exchanges for tokens (stub), displays tokens, and stores only tokens+settings in `entry.options`. Per-device `asyncio.Lock` + optimistic overlays handle write latency.

**Tech Stack:** Python 3.12+, Home Assistant 2024.1+, HACS 2.0+, `aiohttp` (via HA's client session), `voluptuous` for schema validation.

---

## Reference Files

- Homebridge plugin (NA API): `/Users/slavoie2/src/github.com/plecong/homebridge-dkncloudna/src/`
- EU HA reference: `/Users/slavoie2/src/github.com/eXPerience83/DKNCloud-HASS/custom_components/airzoneclouddaikin/`
- Design doc: `docs/plans/2026-03-29-hacs-plugin-design.md`

---

## Task 1: Repo skeleton + CI

**Files:**
- Create: `hacs.json`
- Create: `.github/workflows/validate.yml`
- Create: `custom_components/dkncloudna/` (directory)

**Step 1: Create `hacs.json`**

```json
{
  "name": "DKN Cloud NA",
  "homeassistant": "2024.1.0",
  "hacs": "2.0.0"
}
```

**Step 2: Create `.github/workflows/validate.yml`**

```yaml
name: Validate

on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions: {}

jobs:
  hassfest:
    name: Hassfest validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    name: HACS validation
    runs-on: ubuntu-latest
    steps:
      - uses: hacs/action@main
        with:
          category: integration
          ignore: brands
```

**Step 3: Commit**

```bash
git add hacs.json .github/workflows/validate.yml
git commit -m "feat: add HACS and hassfest CI validation"
```

---

## Task 2: `manifest.json` + `const.py`

**Files:**
- Create: `custom_components/dkncloudna/manifest.json`
- Create: `custom_components/dkncloudna/const.py`

**Step 1: Create `manifest.json`**

```json
{
  "domain": "dkncloudna",
  "name": "DKN Cloud NA",
  "codeowners": ["@lavoiesl"],
  "config_flow": true,
  "documentation": "https://github.com/lavoiesl/homeassistant-dkncloudna",
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/lavoiesl/homeassistant-dkncloudna/issues",
  "version": "0.1.0"
}
```

Notes:
- No `"dependencies"` key — we don't use `persistent_notification`.
- `"integration_type": "hub"` because one config entry manages multiple devices.
- `"requirements"` omitted (empty) — no extra pip packages yet.

**Step 2: Create `const.py`**

```python
"""Constants for DKN Cloud NA integration."""

from __future__ import annotations

import logging

DOMAIN = "dkncloudna"
LOGGER = logging.getLogger(__package__)
MANUFACTURER = "Daikin"

# API
BASE_URL = "https://dkncloudna.com/api/v1"
API_LOGIN = "/auth/login/dknUsa"
API_IS_LOGGED_IN = "/users/isLoggedIn/dknUsa"
API_REFRESH_TOKEN = "/auth/refreshToken/{refresh_token}/dknUsa"
API_INSTALLATIONS = "/installations/dknUsa"

# The DKN Cloud NA API requires a mobile-like User-Agent.
# This matches what the official DKN Cloud NA iOS app sends.
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)

REQUEST_TIMEOUT = 30  # seconds

# Config/options keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_EXPOSE_PII = "expose_pii"
CONF_USER_TOKEN = "user_token"
CONF_REFRESH_TOKEN = "refresh_token"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 300

# Optimistic overlay: how long to hold a locally-set value before trusting
# the next coordinator refresh. Must exceed the write→cloud→poll round-trip.
OPTIMISTIC_TTL_SEC: float = 2.5

# Post-write coordinator refresh: coalesced delay after a device command.
POST_WRITE_REFRESH_DELAY_SEC: float = 1.0

# Device modes (from homebridge plugin src/types.ts)
# DeviceMode: 1=Auto, 2=Cool, 3=Heat, 4=Fan, 5=Dry
DEVICE_MODE_AUTO = 1
DEVICE_MODE_COOL = 2
DEVICE_MODE_HEAT = 3
DEVICE_MODE_FAN = 4
DEVICE_MODE_DRY = 5

# Fan speeds (SpeedState)
SPEED_AUTO = 0
SPEED_20 = 2
SPEED_40 = 3
SPEED_60 = 4
SPEED_80 = 5
SPEED_100 = 6

# Temperature units
TEMP_CELSIUS = 0
TEMP_FAHRENHEIT = 1
```

**Step 3: Commit**

```bash
git add custom_components/dkncloudna/manifest.json custom_components/dkncloudna/const.py
git commit -m "feat: add manifest.json and constants"
```

---

## Task 3: API client stub (`api.py`)

**Files:**
- Create: `custom_components/dkncloudna/api.py`

This is a stub — methods raise `NotImplementedError` or return hardcoded test data. The real HTTP calls come in a future phase.

**Step 1: Create `api.py`**

```python
"""DKN Cloud NA API client stub.

Real HTTP calls are implemented in a future phase. This stub defines the
interface and returns hardcoded data so the rest of the integration can be
developed and tested without live credentials.
"""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession

from .const import LOGGER


class DknAuthError(Exception):
    """Raised when authentication fails (401)."""


class DknConnectionError(Exception):
    """Raised when the API cannot be reached."""


class DknCloudNaClient:
    """Async client for the DKN Cloud NA REST API.

    Instantiated once per config entry. Password is cleared after login and
    never stored beyond the initial token exchange.
    """

    def __init__(
        self,
        username: str,
        session: ClientSession,
        *,
        password: str | None = None,
        token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self._username = username
        self._session = session
        self._password = password
        self.token = token
        self.refresh_token = refresh_token

    def clear_password(self) -> None:
        """Discard password from memory after token exchange."""
        self._password = None

    async def login(self) -> None:
        """Exchange email+password for access and refresh tokens.

        Sets self.token and self.refresh_token on success.
        Raises DknAuthError on bad credentials, DknConnectionError on network failure.
        """
        # TODO: implement real POST to API_LOGIN
        LOGGER.debug("DknCloudNaClient.login() stub called for %s", self._username)
        raise NotImplementedError("login() not yet implemented")

    async def is_logged_in(self) -> bool:
        """Return True if the current token is still valid."""
        # TODO: implement real GET to API_IS_LOGGED_IN
        raise NotImplementedError("is_logged_in() not yet implemented")

    async def refresh_access_token(self) -> None:
        """Use the refresh token to obtain a new access token.

        Updates self.token on success.
        Raises DknAuthError if the refresh token is also expired.
        """
        # TODO: implement real GET to API_REFRESH_TOKEN
        raise NotImplementedError("refresh_access_token() not yet implemented")

    async def fetch_installations(self) -> list[dict[str, Any]]:
        """Return all installations and their devices.

        Each installation contains a list of DeviceInfo dicts.
        Returns stub data for scaffolding.
        """
        LOGGER.debug("DknCloudNaClient.fetch_installations() stub — returning fake data")
        return [
            {
                "_id": "stub-installation-1",
                "name": "My Home",
                "devices": [
                    {
                        "mac": "aa:bb:cc:dd:ee:ff",
                        "name": "Living Room AC",
                        "power": False,
                        "mode": 1,
                        "real_mode": 1,
                        "work_temp": 22.0,
                        "ext_temp": 18.0,
                        "units": 0,
                        "setpoint_air_auto": 22.0,
                        "setpoint_air_cool": 24.0,
                        "setpoint_air_heat": 20.0,
                        "range_sp_auto_air_min": 16,
                        "range_sp_auto_air_max": 32,
                        "range_sp_cool_air_min": 16,
                        "range_sp_cool_air_max": 32,
                        "range_sp_hot_air_min": 16,
                        "range_sp_hot_air_max": 32,
                        "speed_state": 0,
                        "speed_available": [0, 2, 3, 4, 5, 6],
                        "slats_vertical_1": 0,
                        "machineready": True,
                        "isConnected": True,
                        "tsensor_error": False,
                        "stat_rssi": -65,
                        "stat_ssid": "MyWiFi",
                        "version": "1.0.0",
                        "error_value": 0,
                        "error_ascii1": "",
                        "error_ascii2": "",
                    }
                ],
            }
        ]

    def __repr__(self) -> str:
        first = self._username[0] if self._username else "?"
        token_state = "set" if self.token else "none"
        return f"DknCloudNaClient(u={first}***, token={token_state})"
```

**Step 2: Commit**

```bash
git add custom_components/dkncloudna/api.py
git commit -m "feat: add DknCloudNaClient stub"
```

---

## Task 4: Coordinator (`coordinator.py`)

**Files:**
- Create: `custom_components/dkncloudna/coordinator.py`

**Step 1: Create `coordinator.py`**

```python
"""DataUpdateCoordinator for DKN Cloud NA."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DknAuthError, DknCloudNaClient, DknConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class DknCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls all installations and exposes a flat device map.

    ``data`` is ``{mac_address: device_dict}`` where device_dict matches the
    shape returned by DknCloudNaClient.fetch_installations() device entries.

    The coordinator owns the client instance used across all platforms.
    Per-device asyncio.Lock objects for write serialization are stored in
    ``hass.data[DOMAIN][entry_id]["device_locks"]``.
    """

    client: DknCloudNaClient

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DknCloudNaClient,
    ) -> None:
        scan_interval = int(entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self._entry = entry

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch all installations and flatten into {mac: device_dict}."""
        try:
            installations = await self.client.fetch_installations()
        except DknAuthError as err:
            # 401 — trigger the reauth UI and mark entities unavailable.
            raise ConfigEntryAuthFailed("Token invalid or expired") from err
        except DknConnectionError as err:
            raise UpdateFailed(f"Cannot reach DKN Cloud NA: {err}") from err
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {type(err).__name__}") from err

        devices: dict[str, dict[str, Any]] = {}
        for installation in installations or []:
            inst_id = installation.get("_id", "")
            for device in installation.get("devices", []):
                mac = str(device.get("mac") or "").strip().lower()
                if not mac:
                    continue
                device["_installation_id"] = inst_id
                devices[mac] = device

        return devices
```

**Step 2: Commit**

```bash
git add custom_components/dkncloudna/coordinator.py
git commit -m "feat: add DknCoordinator"
```

---

## Task 5: Base entity (`entity.py`)

**Files:**
- Create: `custom_components/dkncloudna/entity.py`

**Step 1: Create `entity.py`**

```python
"""Shared base entity for DKN Cloud NA."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, OPTIMISTIC_TTL_SEC, POST_WRITE_REFRESH_DELAY_SEC
from .coordinator import DknCoordinator


class DknEntity(CoordinatorEntity[DknCoordinator]):
    """Base class for all DKN Cloud NA entities.

    Provides:
    - device_info populated from the device's MAC and name.
    - Per-device asyncio.Lock for serializing concurrent writes.
    - Optimistic overlay: set_optimistic() / get_optimistic() / clear_optimistic()
      so entities can show a locally-set value until the coordinator refreshes.
    - schedule_refresh(): coalesced post-write coordinator refresh.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: DknCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac

    @property
    def _device_data(self) -> dict[str, Any]:
        """Return raw device dict from coordinator, or empty dict if unavailable."""
        return (self.coordinator.data or {}).get(self._mac, {})

    @property
    def device_info(self) -> DeviceInfo:
        data = self._device_data
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            name=data.get("name") or self._mac,
            manufacturer=MANUFACTURER,
            sw_version=data.get("version"),
        )

    # ------------------------------------------------------------------
    # Per-device write lock
    # ------------------------------------------------------------------

    def _get_device_lock(self) -> asyncio.Lock:
        """Return (creating if needed) the asyncio.Lock for this device."""
        bucket = self.hass.data.setdefault(DOMAIN, {}).setdefault(
            self.coordinator._entry.entry_id, {}
        )
        locks: dict[str, asyncio.Lock] = bucket.setdefault("device_locks", {})
        if self._mac not in locks:
            locks[self._mac] = asyncio.Lock()
        return locks[self._mac]

    # ------------------------------------------------------------------
    # Optimistic overlays
    # ------------------------------------------------------------------

    def _optimistic_set(self, key: str, value: Any) -> None:
        """Store a locally-set value with a TTL timestamp."""
        bucket = self.hass.data.setdefault(DOMAIN, {}).setdefault(
            self.coordinator._entry.entry_id, {}
        )
        overlays: dict[str, dict[str, Any]] = bucket.setdefault("optimistic", {})
        device_overlays = overlays.setdefault(self._mac, {})
        device_overlays[key] = {"value": value, "expires": time.monotonic() + OPTIMISTIC_TTL_SEC}

    def _optimistic_get(self, key: str, fallback: Any) -> Any:
        """Return the optimistic value if still fresh, else fallback."""
        bucket = self.hass.data.get(DOMAIN, {}).get(
            self.coordinator._entry.entry_id, {}
        )
        overlays = bucket.get("optimistic", {}).get(self._mac, {})
        entry = overlays.get(key)
        if entry and time.monotonic() < entry["expires"]:
            return entry["value"]
        return fallback

    def _optimistic_clear(self, key: str) -> None:
        """Expire an optimistic overlay immediately."""
        bucket = self.hass.data.get(DOMAIN, {}).get(
            self.coordinator._entry.entry_id, {}
        )
        overlays = bucket.get("optimistic", {}).get(self._mac, {})
        overlays.pop(key, None)

    # ------------------------------------------------------------------
    # Post-write coordinator refresh (coalesced)
    # ------------------------------------------------------------------

    def _schedule_refresh(self) -> None:
        """Schedule a coordinator refresh after POST_WRITE_REFRESH_DELAY_SEC.

        Multiple calls within the window collapse into a single refresh.
        """
        bucket = self.hass.data.setdefault(DOMAIN, {}).setdefault(
            self.coordinator._entry.entry_id, {}
        )
        existing: asyncio.Task | None = bucket.get("pending_refresh")
        if existing and not existing.done():
            return

        async def _do_refresh() -> None:
            import asyncio as _asyncio
            await _asyncio.sleep(POST_WRITE_REFRESH_DELAY_SEC)
            await self.coordinator.async_request_refresh()

        bucket["pending_refresh"] = self.hass.async_create_task(_do_refresh())
```

**Step 2: Commit**

```bash
git add custom_components/dkncloudna/entity.py
git commit -m "feat: add DknEntity base with locks, overlays, and refresh"
```

---

## Task 6: Climate entity stub (`climate.py`)

**Files:**
- Create: `custom_components/dkncloudna/climate.py`

**Step 1: Create `climate.py`**

```python
"""Climate entity for DKN Cloud NA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_MODE_AUTO,
    DEVICE_MODE_COOL,
    DEVICE_MODE_DRY,
    DEVICE_MODE_FAN,
    DEVICE_MODE_HEAT,
    DOMAIN,
    LOGGER,
    SPEED_20,
    SPEED_40,
    SPEED_60,
    SPEED_80,
    SPEED_100,
    SPEED_AUTO,
)
from .coordinator import DknCoordinator
from .entity import DknEntity

# Map DKN device mode integers to HA HVACMode
_MODE_TO_HVAC: dict[int, HVACMode] = {
    DEVICE_MODE_AUTO: HVACMode.AUTO,
    DEVICE_MODE_COOL: HVACMode.COOL,
    DEVICE_MODE_HEAT: HVACMode.HEAT,
    DEVICE_MODE_FAN: HVACMode.FAN_ONLY,
    DEVICE_MODE_DRY: HVACMode.DRY,
}
_HVAC_TO_MODE: dict[HVACMode, int] = {v: k for k, v in _MODE_TO_HVAC.items()}

# Fan speed labels
_FAN_MODES = ["auto", "20%", "40%", "60%", "80%", "100%"]
_SPEED_TO_FAN: dict[int, str] = {
    SPEED_AUTO: "auto",
    SPEED_20: "20%",
    SPEED_40: "40%",
    SPEED_60: "60%",
    SPEED_80: "80%",
    SPEED_100: "100%",
}
_FAN_TO_SPEED: dict[str, int] = {v: k for k, v in _SPEED_TO_FAN.items()}

# Modes where a temperature target makes no sense
_NO_TARGET_TEMP_MODES = {HVACMode.FAN_ONLY, HVACMode.DRY, HVACMode.OFF}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    coordinator: DknCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        DknClimateEntity(coordinator, mac)
        for mac in (coordinator.data or {})
    )


class DknClimateEntity(DknEntity, ClimateEntity):
    """Climate entity representing one DKN Cloud NA AC unit."""

    _attr_name = None  # entity name = device name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = _FAN_MODES
    _attr_swing_modes = ["off", "swing"]
    _attr_min_temp = 16
    _attr_max_temp = 32
    _attr_target_temperature_step = 1

    def __init__(self, coordinator: DknCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{DOMAIN}_{mac}"

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return feature flags appropriate for the current HVAC mode."""
        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        mode = self.hvac_mode
        if mode not in _NO_TARGET_TEMP_MODES:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        features |= ClimateEntityFeature.FAN_MODE
        features |= ClimateEntityFeature.SWING_MODE
        return features

    @property
    def hvac_mode(self) -> HVACMode:
        data = self._device_data
        if not data.get("power", False):
            return HVACMode.OFF
        mode_int = data.get("real_mode") or data.get("mode", DEVICE_MODE_AUTO)
        return _MODE_TO_HVAC.get(int(mode_int), HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        return self._device_data.get("work_temp")

    @property
    def target_temperature(self) -> float | None:
        if self.hvac_mode in _NO_TARGET_TEMP_MODES:
            return None
        data = self._device_data
        mode = data.get("real_mode") or data.get("mode", DEVICE_MODE_AUTO)
        if int(mode) == DEVICE_MODE_HEAT:
            return self._optimistic_get("target_temp", data.get("setpoint_air_heat"))
        if int(mode) == DEVICE_MODE_COOL:
            return self._optimistic_get("target_temp", data.get("setpoint_air_cool"))
        return self._optimistic_get("target_temp", data.get("setpoint_air_auto"))

    @property
    def target_temperature_high(self) -> float | None:
        return None  # no range mode

    @property
    def target_temperature_low(self) -> float | None:
        return None

    @property
    def fan_mode(self) -> str | None:
        speed = self._device_data.get("speed_state", SPEED_AUTO)
        return self._optimistic_get("fan_mode", _SPEED_TO_FAN.get(int(speed), "auto"))

    @property
    def swing_mode(self) -> str | None:
        slat = self._device_data.get("slats_vertical_1", 0)
        return self._optimistic_get("swing_mode", "swing" if int(slat) == 9 else "off")

    # ------------------------------------------------------------------
    # Service handlers — all stub (raise NotImplementedError for now)
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        LOGGER.debug("set_hvac_mode(%s) stub for %s", hvac_mode, self._mac)
        raise NotImplementedError("Device control not yet implemented")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        LOGGER.debug("set_temperature(%s) stub for %s", kwargs, self._mac)
        raise NotImplementedError("Device control not yet implemented")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        LOGGER.debug("set_fan_mode(%s) stub for %s", fan_mode, self._mac)
        raise NotImplementedError("Device control not yet implemented")

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        LOGGER.debug("set_swing_mode(%s) stub for %s", swing_mode, self._mac)
        raise NotImplementedError("Device control not yet implemented")

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
```

**Step 2: Commit**

```bash
git add custom_components/dkncloudna/climate.py
git commit -m "feat: add DknClimateEntity stub"
```

---

## Task 7: Sensor + binary sensor stubs

**Files:**
- Create: `custom_components/dkncloudna/sensor.py`
- Create: `custom_components/dkncloudna/binary_sensor.py`

**Step 1: Create `sensor.py`**

```python
"""Sensor entities for DKN Cloud NA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import DknCoordinator
from .entity import DknEntity


@dataclass(frozen=True, kw_only=True)
class DknSensorEntityDescription(SensorEntityDescription):
    """Extend SensorEntityDescription with a device_data key."""
    data_key: str = ""


SENSOR_DESCRIPTIONS: tuple[DknSensorEntityDescription, ...] = (
    DknSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        data_key="work_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    DknSensorEntityDescription(
        key="exterior_temperature",
        translation_key="exterior_temperature",
        data_key="ext_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    DknSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        data_key="stat_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DknSensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        data_key="error_ascii1",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: DknCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        DknSensorEntity(coordinator, mac, desc)
        for mac in (coordinator.data or {})
        for desc in SENSOR_DESCRIPTIONS
    )


class DknSensorEntity(DknEntity, SensorEntity):
    """A single sensor for one property of a DKN device."""

    entity_description: DknSensorEntityDescription

    def __init__(
        self,
        coordinator: DknCoordinator,
        mac: str,
        description: DknSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, mac)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{mac}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self._device_data.get(self.entity_description.data_key)
```

**Step 2: Create `binary_sensor.py`**

```python
"""Binary sensor entities for DKN Cloud NA."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DknCoordinator
from .entity import DknEntity


@dataclass(frozen=True, kw_only=True)
class DknBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Extend BinarySensorEntityDescription with a device_data key."""
    data_key: str = ""


BINARY_SENSOR_DESCRIPTIONS: tuple[DknBinarySensorEntityDescription, ...] = (
    DknBinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        data_key="isConnected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DknBinarySensorEntityDescription(
        key="machine_ready",
        translation_key="machine_ready",
        data_key="machineready",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: DknCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        DknBinarySensorEntity(coordinator, mac, desc)
        for mac in (coordinator.data or {})
        for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class DknBinarySensorEntity(DknEntity, BinarySensorEntity):
    """A binary sensor for one boolean property of a DKN device."""

    entity_description: DknBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DknCoordinator,
        mac: str,
        description: DknBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, mac)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{mac}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        value = self._device_data.get(self.entity_description.data_key)
        if value is None:
            return None
        return bool(value)
```

**Step 3: Commit**

```bash
git add custom_components/dkncloudna/sensor.py custom_components/dkncloudna/binary_sensor.py
git commit -m "feat: add sensor and binary_sensor entity stubs"
```

---

## Task 8: Config flow (`config_flow.py`)

**Files:**
- Create: `custom_components/dkncloudna/config_flow.py`

**Step 1: Create `config_flow.py`**

```python
"""Config flow for DKN Cloud NA."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DknAuthError, DknCloudNaClient, DknConnectionError
from .const import (
    CONF_EXPOSE_PII,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
        vol.Optional(CONF_EXPOSE_PII, default=False): cv.boolean,
    }
)


class DknConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for DKN Cloud NA.

    Steps:
      user → (optionally) token_display → entry created
    Reauth: reauth_confirm → updates token in options
    """

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._expose_pii: bool = False
        self._token: str = ""
        self._refresh_token: str = ""

    @staticmethod
    def async_get_options_flow(
        entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return DknOptionsFlow(entry)

    # ------------------------------------------------------------------
    # Step 1: credentials
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL, "")).strip()
            password = str(user_input.get(CONF_PASSWORD, ""))

            if not email or not password:
                errors["base"] = "invalid_auth"
            else:
                normalized = email.casefold()
                await self.async_set_unique_id(normalized)
                self._abort_if_unique_id_configured()

                session = async_get_clientsession(self.hass)
                client = DknCloudNaClient(
                    email, session, password=password, token=None
                )
                try:
                    await asyncio.wait_for(client.login(), timeout=60.0)
                except TimeoutError:
                    errors["base"] = "timeout"
                except DknAuthError:
                    errors["base"] = "invalid_auth"
                except (DknConnectionError, NotImplementedError):
                    # NotImplementedError: stub not yet implemented → treat as cannot_connect
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error during login")
                    errors["base"] = "unknown"
                finally:
                    client.clear_password()

                if not errors:
                    self._email = email
                    self._scan_interval = int(
                        user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    )
                    self._expose_pii = bool(user_input.get(CONF_EXPOSE_PII, False))
                    self._token = client.token or ""
                    self._refresh_token = client.refresh_token or ""

                    if self._expose_pii:
                        return await self.async_step_token_display()
                    return self._create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_USER_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2 (optional): show tokens to user
    # ------------------------------------------------------------------

    async def async_step_token_display(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show retrieved tokens read-only, then create the entry."""
        if user_input is not None:
            return self._create_entry()

        schema = vol.Schema(
            {
                vol.Optional(
                    "access_token_display", default=self._token
                ): cv.string,
                vol.Optional(
                    "refresh_token_display", default=self._refresh_token
                ): cv.string,
            }
        )
        return self.async_show_form(
            step_id="token_display",
            data_schema=schema,
            errors={},
        )

    def _create_entry(self) -> config_entries.FlowResult:
        return self.async_create_entry(
            title=self._email,
            data={"username": self._email},
            options={
                CONF_USER_TOKEN: self._token,
                CONF_REFRESH_TOKEN: self._refresh_token,
                CONF_SCAN_INTERVAL: self._scan_interval,
                CONF_EXPOSE_PII: self._expose_pii,
            },
        )

    # ------------------------------------------------------------------
    # Reauth
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.FlowResult:
        self._reauth_entry_id = (self.context or {}).get("entry_id")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        entry = None
        if getattr(self, "_reauth_entry_id", None):
            entry = self.hass.config_entries.async_get_entry(self._reauth_entry_id)
        if entry is None:
            entries = self.hass.config_entries.async_entries(DOMAIN)
            entry = entries[0] if len(entries) == 1 else None
        if entry is None:
            return self.async_abort(reason="reauth_failed")

        username = entry.data.get("username", "")
        schema = vol.Schema({vol.Required(CONF_PASSWORD): cv.string})
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = DknCloudNaClient(
                username, session, password=str(user_input[CONF_PASSWORD])
            )
            try:
                await asyncio.wait_for(client.login(), timeout=60.0)
            except TimeoutError:
                errors["base"] = "timeout"
            except DknAuthError:
                errors["base"] = "invalid_auth"
            except (DknConnectionError, NotImplementedError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            finally:
                client.clear_password()

            if not errors:
                new_opts = dict(entry.options)
                new_opts[CONF_USER_TOKEN] = client.token or ""
                new_opts[CONF_REFRESH_TOKEN] = client.refresh_token or ""
                self.hass.config_entries.async_update_entry(entry, options=new_opts)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"username": username},
        )


class DknOptionsFlow(config_entries.OptionsFlow):
    """Options flow: scan interval + PII toggle."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        opts = self._entry.options
        defaults = {
            CONF_SCAN_INTERVAL: int(opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            CONF_EXPOSE_PII: bool(opts.get(CONF_EXPOSE_PII, False)),
        }
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Optional(
                    CONF_EXPOSE_PII, default=defaults[CONF_EXPOSE_PII]
                ): cv.boolean,
            }
        )

        if user_input is not None:
            # Preserve hidden keys (tokens) when updating options
            next_opts = dict(self._entry.options)
            next_opts[CONF_SCAN_INTERVAL] = int(
                user_input.get(CONF_SCAN_INTERVAL, defaults[CONF_SCAN_INTERVAL])
            )
            next_opts[CONF_EXPOSE_PII] = bool(
                user_input.get(CONF_EXPOSE_PII, defaults[CONF_EXPOSE_PII])
            )
            return self.async_create_entry(title="", data=next_opts)

        return self.async_show_form(step_id="init", data_schema=schema, errors={})
```

**Step 2: Commit**

```bash
git add custom_components/dkncloudna/config_flow.py
git commit -m "feat: add config flow with user, token_display, options, and reauth steps"
```

---

## Task 9: Integration entry point (`__init__.py`)

**Files:**
- Create: `custom_components/dkncloudna/__init__.py`

**Step 1: Create `__init__.py`**

```python
"""DKN Cloud NA integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DknCloudNaClient
from .const import CONF_REFRESH_TOKEN, CONF_USER_TOKEN, DOMAIN, LOGGER
from .coordinator import DknCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DKN Cloud NA from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    token = entry.options.get(CONF_USER_TOKEN)
    if not token:
        raise ConfigEntryAuthFailed("No token in options; reauthentication required")

    username = entry.data.get("username", "")
    refresh_token = entry.options.get(CONF_REFRESH_TOKEN)
    session = async_get_clientsession(hass)

    client = DknCloudNaClient(
        username,
        session,
        token=token,
        refresh_token=refresh_token,
    )

    coordinator = DknCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    LOGGER.info(
        "DKN Cloud NA set up (entry=%s, scan_interval=%ss)",
        entry.entry_id,
        coordinator.update_interval.total_seconds() if coordinator.update_interval else "?",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
```

**Step 2: Commit**

```bash
git add custom_components/dkncloudna/__init__.py
git commit -m "feat: add integration entry point"
```

---

## Task 10: Translations (`strings.json` + `translations/en.json`)

**Files:**
- Create: `custom_components/dkncloudna/strings.json`
- Create: `custom_components/dkncloudna/translations/en.json`

Both files are identical — `strings.json` is used by `hassfest` validation, `translations/en.json` is used at runtime.

**Step 1: Create both files with this content**

```json
{
  "title": "DKN Cloud NA",
  "config": {
    "step": {
      "user": {
        "title": "Sign in",
        "description": "Enter your DKN Cloud NA account credentials.",
        "data": {
          "email": "Email",
          "password": "Password",
          "scan_interval": "Scan interval (seconds)",
          "expose_pii": "Show tokens after login"
        },
        "data_description": {
          "scan_interval": "How often to poll the DKN Cloud NA API (30–300 seconds).",
          "expose_pii": "Display access and refresh tokens after login for advanced use."
        }
      },
      "token_display": {
        "title": "Tokens",
        "description": "Your tokens have been saved. You can copy them for reference.",
        "data": {
          "access_token_display": "Access token",
          "refresh_token_display": "Refresh token"
        }
      },
      "reauth_confirm": {
        "title": "Reauthenticate",
        "description": "Your session for {username} has expired. Enter your password to get a new token.",
        "data": {
          "password": "Password"
        }
      }
    },
    "error": {
      "invalid_auth": "Invalid email or password.",
      "cannot_connect": "Cannot connect to DKN Cloud NA.",
      "timeout": "The request timed out. Please try again.",
      "unknown": "Unexpected error. Check the logs for details."
    },
    "abort": {
      "already_configured": "This account is already configured.",
      "reauth_successful": "Reauthentication successful.",
      "reauth_failed": "Reauthentication failed."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Options",
        "data": {
          "scan_interval": "Scan interval (seconds)",
          "expose_pii": "Show tokens after login"
        },
        "data_description": {
          "scan_interval": "How often to poll the DKN Cloud NA API (30–300 seconds)."
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "room_temperature": {"name": "Room temperature"},
      "exterior_temperature": {"name": "Exterior temperature"},
      "wifi_signal": {"name": "Wi-Fi signal"},
      "error_code": {"name": "Error code"}
    },
    "binary_sensor": {
      "connected": {"name": "Connected"},
      "machine_ready": {"name": "Machine ready"}
    }
  }
}
```

**Step 2: Commit**

```bash
git add custom_components/dkncloudna/strings.json custom_components/dkncloudna/translations/en.json
git commit -m "feat: add translations and entity strings"
```

---

## Task 11: README

**Files:**
- Create: `README.md`

**Step 1: Create `README.md`**

```markdown
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
4. Add `https://github.com/lavoiesl/homeassistant-dkncloudna` as an **Integration**
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

## Known Limitations & Roadmap

- **Device control is not yet implemented.** This release establishes the integration scaffolding and entity structure. Setting temperature, mode, fan speed, and swing will be implemented in a future release.
- Real-time updates via Socket.IO are not used; the integration polls the cloud API on a configurable interval (default 60s).
- Temperature units follow what the device reports; Fahrenheit devices are converted to Celsius for Home Assistant.

---

## Credits

- Original Homebridge plugin: [homebridge-dkncloudna](https://github.com/plecong/homebridge-dkncloudna) by [@plecong](https://github.com/plecong)
- EU counterpart inspiration: [DKNCloud-HASS](https://github.com/eXPerience83/DKNCloud-HASS) by [@eXPerience83](https://github.com/eXPerience83)

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[hacs-url]: https://github.com/hacs/integration
[validate-badge]: https://github.com/lavoiesl/homeassistant-dkncloudna/actions/workflows/validate.yml/badge.svg
[validate-url]: https://github.com/lavoiesl/homeassistant-dkncloudna/actions/workflows/validate.yml
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with installation and entity reference"
```

---

## Task 12: Final check — HACS validation requirements

Verify these are all satisfied before pushing:

| Requirement | File/Action |
|---|---|
| `hacs.json` with `name` | ✅ Task 1 |
| `README.md` exists | ✅ Task 11 |
| `manifest.json` has domain, name, codeowners, documentation, issue_tracker, version | ✅ Task 2 |
| GitHub Issues enabled on repo | ✅ (enable in repo settings) |
| GitHub repo has a description | ✅ (add in repo settings) |
| GitHub repo has at least one topic | ✅ (add `home-assistant`, `hacs`, `daikin` in repo settings) |
| `translations/en.json` present (config_flow=true requires it) | ✅ Task 10 |

**Step 1: Push to GitHub**

```bash
git push -u origin main
```

**Step 2: On GitHub, set:**
- Repository description: "Home Assistant HACS integration for Daikin DKN Cloud NA (North America)"
- Topics: `home-assistant`, `hacs`, `daikin`, `dkn-cloud`, `climate`

**Step 3: Verify CI passes**

Check that both `hassfest` and `hacs` workflow jobs pass on the Actions tab.

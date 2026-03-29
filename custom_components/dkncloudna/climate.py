"""Climate entity for DKN Cloud NA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
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

    @callback
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

"""Climate entity for DKN Cloud NA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    DEVICE_MODE_AUTO,
    DEVICE_MODE_COOL,
    DEVICE_MODE_DRY,
    DEVICE_MODE_FAN,
    DEVICE_MODE_HEAT,
    DOMAIN,
    SPEED_20,
    SPEED_40,
    SPEED_60,
    SPEED_80,
    SPEED_100,
    SPEED_AUTO,
    TEMP_FAHRENHEIT,
)
from .coordinator import DknCoordinator
from .entity import DknEntity

_MODE_TO_HVAC: dict[int, HVACMode] = {
    DEVICE_MODE_AUTO: HVACMode.AUTO,
    DEVICE_MODE_COOL: HVACMode.COOL,
    DEVICE_MODE_HEAT: HVACMode.HEAT,
    DEVICE_MODE_FAN: HVACMode.FAN_ONLY,
    DEVICE_MODE_DRY: HVACMode.DRY,
}
_HVAC_TO_MODE: dict[HVACMode, int] = {v: k for k, v in _MODE_TO_HVAC.items()}

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

_NO_TARGET_TEMP_MODES = {HVACMode.FAN_ONLY, HVACMode.DRY, HVACMode.OFF}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    coordinator: DknCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        DknClimateEntity(coordinator, mac) for mac in (coordinator.data or {})
    )


class DknClimateEntity(DknEntity, ClimateEntity):
    """Climate entity representing one DKN Cloud NA AC unit."""

    _attr_name = None
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
        if self.hvac_mode not in _NO_TARGET_TEMP_MODES:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        return (
            features | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.SWING_MODE
        )

    @property
    def hvac_mode(self) -> HVACMode:
        data = self._device_data
        power = self._optimistic_get("power", data.get("power", False))
        if not power:
            return HVACMode.OFF
        optimistic_mode = self._optimistic_get("hvac_mode", None)
        if optimistic_mode is not None:
            return optimistic_mode
        mode_int = data.get("real_mode") or data.get("mode", DEVICE_MODE_AUTO)
        return _MODE_TO_HVAC.get(int(mode_int), HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        value = self._device_data.get("work_temp")
        if value is None:
            return None
        return self._from_device_temperature(float(value))

    @property
    def target_temperature(self) -> float | None:
        mode = self.hvac_mode
        if mode in _NO_TARGET_TEMP_MODES:
            return None
        data = self._device_data
        if mode == HVACMode.HEAT:
            value = data.get("setpoint_air_heat")
        elif mode == HVACMode.COOL:
            value = data.get("setpoint_air_cool")
        else:
            value = data.get("setpoint_air_auto")
        if value is None:
            return None
        fallback = self._from_device_temperature(float(value))
        return self._optimistic_get("target_temp", fallback)

    @property
    def target_temperature_high(self) -> float | None:
        return None

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

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        installation_id = self._installation_id
        async with self._get_device_lock():
            try:
                if hvac_mode == HVACMode.OFF:
                    await self.coordinator.client.async_send_machine_event(
                        installation_id, self._mac, "power", False
                    )
                    self._optimistic_set("power", False)
                    self._optimistic_set("hvac_mode", HVACMode.OFF)
                else:
                    mode = _HVAC_TO_MODE.get(hvac_mode)
                    if mode is None:
                        raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
                    await self.coordinator.client.async_send_machine_event(
                        installation_id, self._mac, "power", True
                    )
                    await self.coordinator.client.async_send_machine_event(
                        installation_id, self._mac, "mode", mode
                    )
                    self._optimistic_set("power", True)
                    self._optimistic_set("hvac_mode", hvac_mode)
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(f"Failed to set HVAC mode: {err}") from err

        self._schedule_refresh()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        hvac_mode = kwargs.get("hvac_mode")
        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        target_mode = hvac_mode or self.hvac_mode
        if target_mode in _NO_TARGET_TEMP_MODES:
            raise HomeAssistantError(
                f"Target temperature is not supported in {target_mode} mode"
            )

        installation_id = self._installation_id
        property_name = self._temperature_property_for_mode(target_mode)
        device_temp = self._to_device_temperature(float(temperature))

        async with self._get_device_lock():
            try:
                await self.coordinator.client.async_send_machine_event(
                    installation_id, self._mac, property_name, device_temp
                )
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(f"Failed to set temperature: {err}") from err

        self._optimistic_set("target_temp", float(temperature))
        self._schedule_refresh()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        speed = _FAN_TO_SPEED.get(fan_mode)
        if speed is None:
            raise HomeAssistantError(f"Unsupported fan mode: {fan_mode}")

        installation_id = self._installation_id
        async with self._get_device_lock():
            try:
                await self.coordinator.client.async_send_machine_event(
                    installation_id, self._mac, "speed_state", speed
                )
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(f"Failed to set fan mode: {err}") from err

        self._optimistic_set("fan_mode", fan_mode)
        self._schedule_refresh()
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        if swing_mode not in {"off", "swing"}:
            raise HomeAssistantError(f"Unsupported swing mode: {swing_mode}")

        installation_id = self._installation_id
        slat = 9 if swing_mode == "swing" else 0
        async with self._get_device_lock():
            try:
                await self.coordinator.client.async_send_machine_event(
                    installation_id, self._mac, "slats_vertical_1", slat
                )
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(f"Failed to set swing mode: {err}") from err

        self._optimistic_set("swing_mode", swing_mode)
        self._schedule_refresh()
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    def _installation_id(self) -> str:
        installation_id = str(self._device_data.get("_installation_id") or "").strip()
        if not installation_id:
            raise HomeAssistantError("Missing installation id for device")
        return installation_id

    def _temperature_property_for_mode(self, hvac_mode: HVACMode) -> str:
        if hvac_mode == HVACMode.HEAT:
            return "setpoint_air_heat"
        if hvac_mode == HVACMode.COOL:
            return "setpoint_air_cool"
        if hvac_mode not in {HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL}:
            raise HomeAssistantError(
                f"Target temperature is not supported in {hvac_mode} mode"
            )
        return "setpoint_air_auto"

    def _to_device_temperature(self, temperature_c: float) -> float | int:
        if int(self._device_data.get("units", 0)) != TEMP_FAHRENHEIT:
            return temperature_c
        fahrenheit = TemperatureConverter.convert(
            temperature_c,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        )
        return round(fahrenheit)

    def _from_device_temperature(self, value: float) -> float:
        if int(self._device_data.get("units", 0)) != TEMP_FAHRENHEIT:
            return value
        celsius = TemperatureConverter.convert(
            value,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
        )
        return round(celsius, 1)

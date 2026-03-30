"""Shared device-state helpers for DKN Cloud NA."""

from __future__ import annotations

from typing import Any

from .const import (
    DEVICE_MODE_AUTO,
    DEVICE_MODE_COOL,
    DEVICE_MODE_DRY,
    DEVICE_MODE_FAN,
    DEVICE_MODE_HEAT,
    SPEED_20,
    SPEED_40,
    SPEED_60,
    SPEED_80,
    SPEED_100,
    SPEED_AUTO,
    TEMP_FAHRENHEIT,
)


def as_bool(value: Any) -> bool | None:
    """Return a boolean for a real boolean value, else None."""
    if isinstance(value, bool):
        return value
    return None


def as_int(value: Any) -> int | None:
    """Return an integer for int-like values, else None."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return None


def to_celsius(value: Any, units: Any) -> float | None:
    """Convert a device temperature to Celsius if needed."""
    if value is None:
        return None
    temp = float(value)
    if as_int(units) != TEMP_FAHRENHEIT:
        return temp
    return round((temp - 32) * 5 / 9, 1)


def to_device_temperature(value_c: float, units: Any) -> float | int:
    """Convert a Celsius temperature to the device units."""
    if as_int(units) != TEMP_FAHRENHEIT:
        return value_c
    return round((value_c * 9 / 5) + 32)


def requested_mode(data: dict[str, Any]) -> int | None:
    """Return the requested device mode."""
    return as_int(data.get("mode"))


def live_mode(data: dict[str, Any]) -> int | None:
    """Return the live device mode, when reported."""
    return as_int(data.get("real_mode"))


def current_temperature(data: dict[str, Any]) -> float | None:
    """Return the indoor temperature in Celsius."""
    return to_celsius(data.get("work_temp", data.get("local_temp")), data.get("units"))


def exterior_temperature(data: dict[str, Any]) -> float | None:
    """Return the exterior temperature in Celsius."""
    return to_celsius(data.get("ext_temp"), data.get("units"))


def target_temperature_key(mode: int | None) -> str | None:
    """Return the setpoint key for the requested mode."""
    if mode == DEVICE_MODE_HEAT:
        return "setpoint_air_heat"
    if mode == DEVICE_MODE_COOL:
        return "setpoint_air_cool"
    if mode == DEVICE_MODE_AUTO:
        return "setpoint_air_auto"
    return None


def target_temperature(data: dict[str, Any]) -> float | None:
    """Return the requested target temperature in Celsius."""
    key = target_temperature_key(requested_mode(data))
    if key is None:
        return None
    return to_celsius(data.get(key), data.get("units"))


def inferred_hvac_action(data: dict[str, Any]) -> str:
    """Infer the active HVAC action from requested mode and temperatures."""
    power = as_bool(data.get("power"))
    if not power:
        return "off"

    mode = requested_mode(data)
    current = current_temperature(data)
    target = target_temperature(data)

    if mode == DEVICE_MODE_HEAT:
        if current is not None and target is not None and current < target:
            return "heating"
        return "idle"
    if mode == DEVICE_MODE_COOL:
        if current is not None and target is not None and current > target:
            return "cooling"
        return "idle"
    if mode == DEVICE_MODE_AUTO:
        if current is not None and target is not None:
            if current < target:
                return "heating"
            if current > target:
                return "cooling"
        return "idle"
    if mode == DEVICE_MODE_FAN:
        return "fan"
    if mode == DEVICE_MODE_DRY:
        return "drying"
    return "on"


def available_fan_speeds(data: dict[str, Any]) -> list[int]:
    """Return the supported fan speed codes for the device."""
    raw = data.get("speed_available")
    if isinstance(raw, list):
        return [speed for speed in (as_int(item) for item in raw) if speed is not None]
    return [SPEED_AUTO, SPEED_20, SPEED_40, SPEED_60, SPEED_80, SPEED_100]


def supports_swing(data: dict[str, Any]) -> bool:
    """Return whether the device appears to support vertical swing control."""
    return "slats_vertical_1" in data or as_int(data.get("slats_vnum")) not in (None, 0)

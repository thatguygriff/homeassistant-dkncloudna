"""Live smoke test for the DKN Cloud NA integration."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from aiohttp import ClientSession


def _load_integration_client() -> type:
    """Load the integration API module without importing Home Assistant."""
    root = Path(__file__).resolve().parents[1]
    package_root = root / "custom_components"
    integration_root = package_root / "dkncloudna"

    custom_components_pkg = type(sys)("custom_components")
    custom_components_pkg.__path__ = [str(package_root)]
    sys.modules.setdefault("custom_components", custom_components_pkg)

    integration_pkg = type(sys)("custom_components.dkncloudna")
    integration_pkg.__path__ = [str(integration_root)]
    sys.modules.setdefault("custom_components.dkncloudna", integration_pkg)

    for name in ("const", "api"):
        module_name = f"custom_components.dkncloudna.{name}"
        if module_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(
            module_name,
            integration_root / f"{name}.py",
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {module_name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    return sys.modules["custom_components.dkncloudna.api"].DknCloudNaClient


DknCloudNaClient = _load_integration_client()


def _temp_property(mode: int) -> str | None:
    if mode == 1:
        return "setpoint_air_auto"
    if mode == 2:
        return "setpoint_air_cool"
    if mode == 3:
        return "setpoint_air_heat"
    return None


def _temp_bounds(device: dict[str, Any], mode: int) -> tuple[Any, Any]:
    if mode == 1:
        return device.get("range_sp_auto_air_min"), device.get("range_sp_auto_air_max")
    if mode == 2:
        return device.get("range_sp_cool_air_min"), device.get("range_sp_cool_air_max")
    if mode == 3:
        return device.get("range_sp_hot_air_min"), device.get("range_sp_hot_air_max")
    return None, None


def _next_fan_speed(current: int) -> int:
    speeds = [0, 2, 3, 4, 5, 6]
    if current not in speeds:
        return 0
    return speeds[(speeds.index(current) + 1) % len(speeds)]


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return None


def _effective_state(device: dict[str, Any]) -> dict[str, Any]:
    power = _bool_or_none(device.get("power"))
    mode = _int_or_none(device.get("mode"))
    real_mode = _int_or_none(device.get("real_mode"))
    units = _int_or_none(device.get("units"))
    is_connected = _bool_or_none(device.get("isConnected"))
    machine_ready = _bool_or_none(device.get("machineready"))

    hvac_mode = "off"
    hvac_action = "off"
    if power:
        if mode == 3:
            hvac_mode = "heat"
        elif mode == 2:
            hvac_mode = "cool"
        elif mode == 1:
            hvac_mode = "auto"
        elif mode == 4:
            hvac_mode = "fan_only"
        elif mode == 5:
            hvac_mode = "dry"
        else:
            hvac_mode = "on"

        current = device.get("work_temp")
        target = None
        if mode == 3:
            target = device.get("setpoint_air_heat")
        elif mode == 2:
            target = device.get("setpoint_air_cool")
        elif mode == 1:
            target = device.get("setpoint_air_auto")

        if mode == 3:
            if current is not None and target is not None and current < target:
                hvac_action = "heating"
            else:
                hvac_action = "idle"
        elif mode == 2:
            if current is not None and target is not None and current > target:
                hvac_action = "cooling"
            else:
                hvac_action = "idle"
        elif mode == 1:
            if current is not None and target is not None:
                if current < target:
                    hvac_action = "heating"
                elif current > target:
                    hvac_action = "cooling"
                else:
                    hvac_action = "idle"
            else:
                hvac_action = "idle"
        elif mode == 4:
            hvac_action = "fan"
        elif mode == 5:
            hvac_action = "drying"
        else:
            hvac_action = "on"

    return {
        "connected": is_connected,
        "machine_ready": machine_ready,
        "power": power,
        "mode": mode,
        "real_mode": real_mode,
        "units": units,
        "hvac_mode": hvac_mode,
        "hvac_action": hvac_action,
        "work_temp": device.get("work_temp"),
        "setpoint_air_auto": device.get("setpoint_air_auto"),
        "setpoint_air_cool": device.get("setpoint_air_cool"),
        "setpoint_air_heat": device.get("setpoint_air_heat"),
        "speed_state": _int_or_none(device.get("speed_state")),
        "slats_vertical_1": _int_or_none(device.get("slats_vertical_1")),
    }


def _supports_write_verification(device: dict[str, Any], property_name: str) -> bool:
    if property_name == "slats_vertical_1":
        return "slats_vertical_1" in device or _int_or_none(
            device.get("slats_vnum")
        ) not in (None, 0)
    if property_name == "speed_state":
        available = device.get("speed_available")
        return isinstance(available, list) and len(available) > 0
    if property_name.startswith("setpoint_air_"):
        return device.get(property_name) is not None
    return True


def _has_live_state(device: dict[str, Any]) -> bool:
    state = _effective_state(device)
    return any(
        state[key] is not None
        for key in (
            "power",
            "mode",
            "real_mode",
            "units",
            "work_temp",
            "setpoint_air_auto",
            "setpoint_air_cool",
            "setpoint_air_heat",
            "speed_state",
            "slats_vertical_1",
        )
    )


async def _main() -> None:
    email = os.environ.get("DKN_CLOUD_NA_EMAIL")
    password = os.environ.get("DKN_CLOUD_NA_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing DKN_CLOUD_NA_EMAIL or DKN_CLOUD_NA_PASSWORD")

    results: dict[str, Any] = {
        "login": False,
        "discovery": None,
        "socket_connect": False,
        "write_debug": {},
        "writes": {},
    }

    current_device: dict[str, Any] = {}
    installation_id = ""
    mac = ""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async with ClientSession() as session:
        client = DknCloudNaClient(email, session, password=password)
        await client.login()
        client.clear_password()
        results["login"] = True

        async def fetch_current_device() -> dict[str, Any]:
            nonlocal current_device
            installations_now = await client.fetch_installations()
            for installation in installations_now:
                if str(installation.get("_id")) != installation_id:
                    continue
                for device in installation.get("devices", []):
                    device_mac = str(device.get("mac") or "").strip().lower()
                    if device_mac == mac:
                        current_device = {
                            **current_device,
                            **dict(device),
                            "_installation_id": installation_id,
                        }
                        return current_device
            raise RuntimeError("Selected device disappeared during smoke test")

        async def on_data(updated_mac: str, data: dict[str, Any]) -> None:
            nonlocal current_device
            if updated_mac != mac:
                return
            current_device = {**current_device, **data}
            await queue.put(data)

        async def on_refresh() -> None:
            return

        installations = await client.fetch_installations()
        selected_installation = None
        selected_device = None
        for installation in installations:
            for device in installation.get("devices", []):
                if device.get("isConnected") and device.get("machineready"):
                    selected_installation = installation
                    selected_device = device
                    break
            if selected_device is not None:
                break
        if selected_device is None:
            for installation in installations:
                devices = installation.get("devices", [])
                if devices:
                    selected_installation = installation
                    selected_device = devices[0]
                    break
        if selected_installation is None or selected_device is None:
            raise RuntimeError("No DKN devices found")

        installation_id = str(selected_installation.get("_id") or "")
        mac = str(selected_device.get("mac") or "").strip().lower()
        command_mac = str(selected_device.get("mac") or "").strip() or mac.upper()
        current_device = dict(selected_device)
        current_device["_installation_id"] = installation_id

        await client.ensure_socket_connection(installations, on_data, on_refresh)
        socket = client._socket  # noqa: SLF001
        results["socket_connect"] = bool(socket and socket.connected)
        if not results["socket_connect"]:
            raise RuntimeError("Socket.IO connection did not come up")

        async def wait_for_live_state(timeout: float = 20.0) -> bool:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while loop.time() < deadline:
                if _has_live_state(current_device):
                    return True
                remaining = max(0.1, deadline - loop.time())
                try:
                    await asyncio.wait_for(queue.get(), timeout=min(2.0, remaining))
                except asyncio.TimeoutError:
                    pass
                if _has_live_state(current_device):
                    return True
                await fetch_current_device()
            return _has_live_state(current_device)

        await wait_for_live_state()

        results["discovery"] = {
            "installation_id": installation_id,
            "device_name": selected_device.get("name"),
            "mac": mac,
            "command_mac": command_mac,
            **_effective_state(current_device),
        }

        async def wait_for_property(
            property_name: str, expected: Any, timeout: float = 20.0
        ) -> bool:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while loop.time() < deadline:
                remaining = max(0.1, deadline - loop.time())
                try:
                    await asyncio.wait_for(queue.get(), timeout=min(2.0, remaining))
                except asyncio.TimeoutError:
                    pass
                if current_device.get(property_name) == expected:
                    return True
                await fetch_current_device()
                if current_device.get(property_name) == expected:
                    return True
            return False

        async def collect_socket_deltas(window: float = 5.0) -> list[dict[str, Any]]:
            deltas: list[dict[str, Any]] = []
            loop = asyncio.get_running_loop()
            deadline = loop.time() + window
            while loop.time() < deadline:
                remaining = max(0.05, deadline - loop.time())
                try:
                    payload = await asyncio.wait_for(
                        queue.get(), timeout=min(0.5, remaining)
                    )
                except asyncio.TimeoutError:
                    continue
                deltas.append(payload)
            return deltas

        async def send(property_name: str, value: Any) -> None:
            await client.async_send_machine_event(
                installation_id, command_mac, property_name, value
            )

        async def send_and_verify(
            property_name: str, value: Any, timeout: float = 20.0
        ) -> bool | str:
            if not _supports_write_verification(current_device, property_name):
                return "unsupported_by_payload"
            baseline = current_device.get(property_name)
            await send(property_name, value)
            verified = await wait_for_property(property_name, value, timeout=timeout)
            refreshed = await fetch_current_device()
            results["write_debug"][property_name] = {
                "requested": value,
                "before": baseline,
                "after": refreshed.get(property_name),
                "acknowledged": True,
                "socket_deltas": await collect_socket_deltas(),
            }
            return verified

        restore_actions: list[tuple[str, Any]] = []
        try:
            await send("power", current_device.get("power", False))
            results["writes"]["power_emit"] = "sent_same_value"

            await send("mode", current_device.get("mode", 1))
            results["writes"]["mode_emit"] = "sent_same_value"

            original_swing = int(current_device.get("slats_vertical_1", 0) or 0)
            test_swing = 0 if original_swing == 9 else 9
            results["writes"]["swing_toggle"] = await send_and_verify(
                "slats_vertical_1", test_swing
            )
            restore_actions.append(("slats_vertical_1", original_swing))

            original_fan = int(current_device.get("speed_state", 0) or 0)
            test_fan = _next_fan_speed(original_fan)
            if test_fan == original_fan:
                results["writes"]["fan_speed"] = "skipped_no_alternate"
            else:
                results["writes"]["fan_speed"] = await send_and_verify(
                    "speed_state", test_fan
                )
                restore_actions.append(("speed_state", original_fan))

            mode = int(current_device.get("mode", 1) or 1)
            property_name = _temp_property(mode)
            if property_name is None:
                results["writes"]["temperature"] = "skipped_unsupported_mode"
            else:
                original_temp = current_device.get(property_name)
                low, high = _temp_bounds(current_device, mode)
                if original_temp is None:
                    results["writes"]["temperature"] = "skipped_missing_setpoint"
                else:
                    test_temp = original_temp
                    if low is not None and high is not None:
                        if original_temp < high:
                            test_temp = original_temp + 1
                        elif original_temp > low:
                            test_temp = original_temp - 1
                    elif original_temp < 31:
                        test_temp = original_temp + 1
                    elif original_temp > 17:
                        test_temp = original_temp - 1
                    if test_temp == original_temp:
                        results["writes"]["temperature"] = "skipped_no_room"
                    else:
                        results["writes"]["temperature"] = await send_and_verify(
                            property_name, test_temp
                        )
                        restore_actions.append((property_name, original_temp))
        finally:
            for property_name, value in reversed(restore_actions):
                with suppress(Exception):
                    await send(property_name, value)
                    await wait_for_property(property_name, value, timeout=15.0)
            with suppress(Exception):
                await client.disconnect_socket()

    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())

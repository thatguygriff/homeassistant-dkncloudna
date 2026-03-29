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
    - Optimistic overlay: _optimistic_set() / _optimistic_get() / _optimistic_clear()
      so entities can show a locally-set value until the coordinator refreshes.
    - _schedule_refresh(): coalesced post-write coordinator refresh.
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
            self.coordinator.entry_id, {}
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
            self.coordinator.entry_id, {}
        )
        overlays: dict[str, dict[str, Any]] = bucket.setdefault("optimistic", {})
        device_overlays = overlays.setdefault(self._mac, {})
        device_overlays[key] = {"value": value, "expires": time.monotonic() + OPTIMISTIC_TTL_SEC}

    def _optimistic_get(self, key: str, fallback: Any) -> Any:
        """Return the optimistic value if still fresh, else fallback."""
        bucket = self.hass.data.get(DOMAIN, {}).get(
            self.coordinator.entry_id, {}
        )
        overlays = bucket.get("optimistic", {}).get(self._mac, {})
        entry = overlays.get(key)
        if entry and time.monotonic() < entry["expires"]:
            return entry["value"]
        return fallback

    def _optimistic_clear(self, key: str) -> None:
        """Expire an optimistic overlay immediately."""
        bucket = self.hass.data.get(DOMAIN, {}).get(
            self.coordinator.entry_id, {}
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
            self.coordinator.entry_id, {}
        )
        existing: asyncio.Task | None = bucket.get("pending_refresh")
        if existing and not existing.done():
            return

        async def _do_refresh() -> None:
            await asyncio.sleep(POST_WRITE_REFRESH_DELAY_SEC)
            await self.coordinator.async_request_refresh()

        bucket["pending_refresh"] = self.hass.async_create_task(_do_refresh())

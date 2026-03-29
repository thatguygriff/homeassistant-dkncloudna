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
        self.entry_id = entry.entry_id

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

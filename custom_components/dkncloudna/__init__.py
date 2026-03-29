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

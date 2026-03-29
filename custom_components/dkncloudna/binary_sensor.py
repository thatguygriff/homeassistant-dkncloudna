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

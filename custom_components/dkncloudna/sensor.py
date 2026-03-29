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

from .const import DOMAIN
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

"""Sensor platform for Awqaat MT."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COLUMNS, CONF_NAME, DOMAIN
from .coordinator import AwqaatCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AwqaatCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for column, cfg in entry.data.get(CONF_COLUMNS, {}).items():
        if not cfg.get("enabled"):
            continue
        entities.append(
            AwqaatTimeSensor(coordinator, entry, column, cfg.get("friendly_name", column))
        )

    entities.append(AwqaatLastUpdatedSensor(coordinator, entry))
    entities.append(AwqaatActiveDateSensor(coordinator, entry))

    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME, entry.title),
        manufacturer="Mullatech",
        model="Awqaat MT sheet",
    )


class AwqaatTimeSensor(CoordinatorEntity[AwqaatCoordinator], SensorEntity):
    """A single mapped column, e.g. Fajr, exposed as a timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AwqaatCoordinator, entry: ConfigEntry, column: str, friendly_name: str
    ) -> None:
        super().__init__(coordinator)
        self._column = column
        self._attr_name = friendly_name
        self._attr_unique_id = f"{entry.entry_id}_{column}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.data["values"].get(self._column)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data["values"].get(self._column) is not None
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {"sheet_column": self._column}


class AwqaatLastUpdatedSensor(CoordinatorEntity[AwqaatCoordinator], SensorEntity):
    """Diagnostic: when the sheet was last successfully fetched."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_name = "Last updated"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AwqaatCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_updated"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.data.get("last_updated")


class AwqaatActiveDateSensor(CoordinatorEntity[AwqaatCoordinator], SensorEntity):
    """Diagnostic: which sheet date row is currently active (spot a stale sheet)."""

    _attr_has_entity_name = True
    _attr_name = "Active sheet date"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AwqaatCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_date"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        active_date = self.coordinator.data.get("active_date")
        return active_date.isoformat() if active_date else None

    @property
    def extra_state_attributes(self) -> dict:
        return {"is_fallback": self.coordinator.data.get("is_fallback", False)}

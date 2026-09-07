"""Button platform for Awqaat MT — manual refresh."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, DOMAIN
from .coordinator import AwqaatCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AwqaatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AwqaatRefreshButton(coordinator, entry)])


class AwqaatRefreshButton(ButtonEntity):
    """Force an immediate re-fetch of the sheet, outside the midnight schedule."""

    _attr_has_entity_name = True
    _attr_name = "Refresh"

    def __init__(self, coordinator: AwqaatCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, entry.title),
            manufacturer="Mullatech",
            model="Awqaat MT sheet",
        )

    async def async_press(self) -> None:
        await self._coordinator.async_refresh()

"""Support for controllable Jablotron PG sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import DEVICE_ID, DOMAIN, SERVICE_TYPE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jablotron Cloud from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    services = coordinator.data
    entities = []

    if not services:
        return

    for service_id, service_data in services.items():

        thermo_data = service_data["thermo"]
        if not thermo_data:
            continue

        for thermo_unit in thermo_data:
            device_id = thermo_unit[DEVICE_ID]

            _LOGGER.debug("Jablotron discovered thermo device: %s", device_id)
            entities.append(
                JablotronSensor(
                    coordinator,
                    service_id,
                    device_id,
                )
            )

    async_add_entities(entities, True)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


class JablotronSensor(CoordinatorEntity[JablotronDataCoordinator], SensorEntity):
    """Representation of Jablotron temperature sensor."""

    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self: JablotronSensor,
        coordinator: JablotronDataCoordinator,
        service_id: int,
        device_id: str,
    ) -> None:
        """Initialize an Advantage Air Zone Temp Sensor."""
        super().__init__(coordinator)
        self._service_id = service_id
        self._device_id = device_id
        self._attr_unique_id = f"{service_id} {device_id}"
        self._attr_name = device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, str(self._service_id))
            },
            name=self.coordinator.data[self._service_id]["service"]["name"],
            manufacturer="Jablotron",
            model=self.coordinator.data[self._service_id]["service"][SERVICE_TYPE],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._service_id not in self.coordinator.data:
            _LOGGER.error("Invalid gate data. Maybe session expired")
            return

        thermo_data = self.coordinator.data[self._service_id].get("thermo", {})
        for device in thermo_data:
            if device[DEVICE_ID] == self._device_id:
                _LOGGER.debug("Updating thermo device with data: %s", str(device))
                temperature = float(device["temperature"])
                self._attr_native_value = temperature
                self.async_write_ha_state()
                return

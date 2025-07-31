"""Support for Jablotron thermo device sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from jablotronpy import JablotronThermoDevice

from . import JablotronConfigEntry, JablotronData, JablotronDataCoordinator, JablotronClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: F841
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Register sensor entity for each Jablotron service thermo device."""

    _LOGGER.debug("Adding Jablotron sensor entities")
    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    # Get thermo devices for each service
    entities: list[JablotronSensor] = []
    for service_id, service_data in client.services.items():
        # Get service details
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        # Add all thermo device entities
        _LOGGER.debug("Getting available thermo devices for service '%s'", service_name)
        thermo_devices = service_data["thermo"]
        for thermo_device in thermo_devices:
            # Get thermo device details
            thermo_device_id = thermo_device["object-device-id"]
            current_temperature = thermo_device["temperature"]

            # Add thermo device entity
            _LOGGER.debug("Adding thermo device '%s'", thermo_device_id)
            entities.append(
                JablotronSensor(
                    coordinator,
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    thermo_device_id,
                    current_temperature
                )
            )

    async_add_entities(entities)


async def async_unload_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:  # noqa: F841
    """Unload sensor entities."""

    return True


class JablotronSensor(CoordinatorEntity[JablotronDataCoordinator], SensorEntity):
    """Representation of Jablotron Cloud sensor entity."""

    # Allow custom entity names
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self: JablotronSensor,
        coordinator: JablotronDataCoordinator,
        client: JablotronClient,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
        thermo_device_id: str,
        current_temperature: float
    ) -> None:
        """Initialize Jablotron sensor."""

        # Define entity attributes
        self._client = client
        self._service_id = service_id
        self._service_name = service_name
        self._service_type = service_type
        self._service_firmware = service_firmware
        self._thermo_device_id = thermo_device_id

        # Define sensor attributes
        self._attr_name = f"{thermo_device_id}_temperature"
        self._attr_unique_id = f"{service_id}_{thermo_device_id}"
        self._attr_native_value = current_temperature

        # Initialize sensor
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about device."""

        return DeviceInfo(
            identifiers={(DOMAIN, str(self._service_id))},
            name=self._service_name,
            manufacturer="Jablotron",
            model=self._service_type,
            sw_version=self._service_firmware
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""

        # Get corresponding service data
        _LOGGER.debug("Updating thermo device state for device '%s'", self._thermo_device_id)
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)

            return

        # Get service devices
        thermo_devices = service["thermo"]
        if not thermo_devices:
            _LOGGER.warning("No thermo devices available for service '%d'!", self._service_id)

            return

        # Get device
        thermo_device: JablotronThermoDevice | None = next(
            filter(lambda device: device["object-device-id"] == self._thermo_device_id, thermo_devices),
            None
        )
        if not thermo_device:
            _LOGGER.warning("No thermo device found with id '%s'!", self._thermo_device_id)

            return

        # Set current thermo device state
        self._attr_native_value = thermo_device["temperature"]
        self.async_write_ha_state()

        _LOGGER.debug("Successfully updated thermo device state for device '%s'", self._thermo_device_id)

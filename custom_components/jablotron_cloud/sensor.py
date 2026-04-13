"""Support for Jablotron thermo device sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JablotronClient, JablotronConfigEntry, JablotronData, JablotronDataCoordinator
from .entity import JablotronEntity
from .utils import get_component_state, get_thermo_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register sensor entities for each Jablotron service thermo device and non-controllable sections."""

    _LOGGER.debug("Adding Jablotron sensor entities")
    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    entities: list[SensorEntity] = []
    for service_id, service_data in client.services.items():
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        # Add thermo device entities
        _LOGGER.debug("Getting available thermo devices for service '%s'", service_name)
        thermo_devices = service_data.get("thermo", [])
        for thermo_device in thermo_devices:
            # Skip controllable thermo devices — handled by the climate platform
            if thermo_device.get("thermo-device", {}).get("can-control", False):
                continue

            thermo_device_id = thermo_device["object-device-id"]
            current_temperature = thermo_device.get("temperature")

            _LOGGER.debug(
                "Adding thermo device '%s' with initial temperature %s", thermo_device_id, current_temperature
            )
            entities.append(
                JablotronSensor(
                    coordinator,
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    thermo_device_id,
                    current_temperature,
                )
            )

        # Add non-controllable section state sensors
        _LOGGER.debug("Getting available sections for service '%s'", service_name)
        alarm = service_data.get("alarm", {})
        for section in alarm.get("sections", []):
            section_name = section.get("name")
            section_id = section.get("cloud-component-id")

            # Only register sensors for sections that are NOT controllable
            if section.get("can-control", True):
                _LOGGER.debug("Section '%s' is controllable, ignoring for state-only sensor", section_name)
                continue

            # Get initial state (may be None)
            section_state = get_component_state(section_id, alarm.get("states", []))

            _LOGGER.debug("Adding non-controllable section state sensor '%s'", section_name)
            entities.append(
                JablotronSectionStateSensor(
                    coordinator,
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    section_id,
                    section_name,
                    section_state,
                )
            )

    async_add_entities(entities)


class JablotronSensor(JablotronEntity, SensorEntity):
    """Representation of Jablotron Cloud sensor entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: JablotronDataCoordinator,
        client: JablotronClient,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
        thermo_device_id: str,
        current_temperature: float,
    ) -> None:
        """Initialize Jablotron sensor."""
        self._thermo_device_id = thermo_device_id
        self._attr_name = f"{thermo_device_id}_temperature"
        self._attr_unique_id = f"{service_id}_{thermo_device_id}"
        self._attr_native_value = current_temperature
        super().__init__(coordinator, client, service_id, service_name, service_type, service_firmware)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)
            return

        thermo_devices = service["thermo"]
        if not thermo_devices:
            _LOGGER.warning("No thermo devices available for service '%d'!", self._service_id)
            return

        thermo_device = get_thermo_device(self._thermo_device_id, thermo_devices)
        if not thermo_device:
            _LOGGER.warning("No thermo device found with id '%s'!", self._thermo_device_id)
            return

        temperature = thermo_device["temperature"]
        _LOGGER.debug("Device '%s' received temperature %s", self._thermo_device_id, temperature)
        self._attr_native_value = temperature
        self.async_write_ha_state()


class JablotronSectionStateSensor(JablotronEntity, SensorEntity):
    """Representation of a Jablotron section state sensor for non-controllable sections."""

    def __init__(
        self,
        coordinator: JablotronDataCoordinator,
        client: JablotronClient,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
        section_id: str,
        section_name: str,
        initial_state: str | None,
    ) -> None:
        """Initialize Jablotron section state sensor."""
        self._section_id = section_id
        self._section_name = section_name
        self._attr_name = f"{section_name}_state"
        self._attr_unique_id = f"{service_id}_{section_id}_state"
        self._attr_native_value = initial_state if initial_state is not None else STATE_UNKNOWN
        super().__init__(coordinator, client, service_id, service_name, service_type, service_firmware)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator and update sensor state."""
        _LOGGER.debug("Updating section state for '%s'", self._section_name)
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)
            return

        service_states = service.get("alarm", {}).get("states")
        if not service_states:
            _LOGGER.warning("No states data available for service '%d'!", self._service_id)
            return

        section_state = get_component_state(self._section_id, service_states)
        if section_state is None:
            _LOGGER.warning("No state available for section '%s'!", self._section_name)
            return

        # Expose the raw section state string (e.g. "ARM", "DISARM", "PARTIAL_ARM")
        self._attr_native_value = section_state
        self.async_write_ha_state()

        _LOGGER.debug("Successfully updated section state for '%s' to '%s'", self._section_name, section_state)

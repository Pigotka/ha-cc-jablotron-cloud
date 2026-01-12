"""Support for Jablotron thermo device sensors and state-only section sensors."""

from __future__ import annotations

import logging

from jablotronpy import JablotronThermoDevice

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronClient, JablotronConfigEntry, JablotronData, JablotronDataCoordinator
from .const import DOMAIN
from .utils import get_component_state

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

    # Collect entities (thermo devices + non-controllable section state sensors)
    entities: list[SensorEntity] = []

    for service_id, service_data in client.services.items():
        # Get service details
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        # Add thermo device entities
        _LOGGER.debug("Getting available thermo devices for service '%s'", service_name)
        thermo_devices = service_data.get("thermo", [])
        for thermo_device in thermo_devices:
            # Get thermo device details
            thermo_device_id = thermo_device["object-device-id"]
            current_temperature = thermo_device.get("temperature")

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


async def async_unload_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:
    """Unload sensor entities."""

    return True


class JablotronSensor(CoordinatorEntity[JablotronDataCoordinator], SensorEntity):
    """Representation of Jablotron Cloud thermometer sensor entity."""

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
        current_temperature: float,
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

        # Initialize coordinator entity
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about device."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._service_id))},
            name=self._service_name,
            manufacturer="Jablotron",
            model=self._service_type,
            sw_version=self._service_firmware,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""
        _LOGGER.debug("Updating thermo sensor for '%s'", self._thermo_device_id)
        service = self._client.services.get(self._service_id)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)
            return

        thermo_devices = service.get("thermo", [])
        for thermo in thermo_devices:
            if thermo.get("object-device-id") == self._thermo_device_id:
                self._attr_native_value = thermo.get("temperature")
                self.async_write_ha_state()
                _LOGGER.debug("Successfully updated thermo sensor '%s' to '%s'", self._thermo_device_id, self._attr_native_value)
                return

        _LOGGER.warning("No thermo device '%s' found for service '%d'", self._thermo_device_id, self._service_id)


class JablotronSectionStateSensor(CoordinatorEntity[JablotronDataCoordinator], SensorEntity):
    """Representation of a Jablotron section state sensor for non-controllable sections."""

    # Allow custom entity names
    _attr_has_entity_name = True

    def __init__(
        self: JablotronSectionStateSensor,
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

        # Define entity attributes
        self._client = client
        self._service_id = service_id
        self._service_name = service_name
        self._service_type = service_type
        self._service_firmware = service_firmware
        self._section_id = section_id
        self._section_name = section_name

        # Define sensor attributes
        # Name identifies this is the section state
        self._attr_name = f"{section_name}_state"
        # Avoid unique_id collision with alarm control panel entities
        self._attr_unique_id = f"{service_id}_{section_id}_state"
        # Initial value (may be None)
        self._attr_native_value = initial_state if initial_state is not None else STATE_UNKNOWN

        # Initialize coordinator entity
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about device."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._service_id))},
            name=self._service_name,
            manufacturer="Jablotron",
            model=self._service_type,
            sw_version=self._service_firmware,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator and update sensor state."""
        _LOGGER.debug("Updating section state for '%s'", self._section_name)
        service = self._client.services.get(self._service_id)
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

"""Support for Jablotron PG binary sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from jablotronpy import JablotronProgrammableGatesGate

from . import JablotronConfigEntry, JablotronData, JablotronDataCoordinator, JablotronClient
from .const import DOMAIN
from .utils import get_component_state, pg_state_to_binary_state

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: F841
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Register binary sensor entity for each Jablotron service uncontrollable programmable gate."""

    _LOGGER.debug("Adding Jablotron binary sensor entities")
    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    # Get programmable gates for each service
    entities: list[JablotronProgrammableGate] = []
    for service_id, service_data in client.services.items():
        # Get service details
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        # Add all uncontrollable programmable gate entities
        _LOGGER.debug("Getting available programmable gates for service '%s'", service_name)
        gates = service_data["gates"]
        for gate in gates.get("programmableGates", []):
            # Get gate details
            gate: JablotronProgrammableGatesGate
            gate_name = gate["name"]
            gate_id = gate["cloud-component-id"]
            gate_state = get_component_state(gate_id, gates["states"])
            is_on = pg_state_to_binary_state(gate_state)

            # Check whether programmable gate is NOT controllable
            if gate["can-control"]:
                _LOGGER.debug("Programmable gate '%s' is controllable, ignoring!", gate_name)

                continue

            # Add uncontrollable programmable gate entity
            _LOGGER.debug("Adding uncontrollable programmable gate '%s'", gate_name)
            entities.append(
                JablotronProgrammableGate(
                    coordinator,
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    gate_id,
                    gate_name,
                    is_on
                )
            )

    async_add_entities(entities)


async def async_unload_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:  # noqa: F841
    """Unload binary sensor entities."""

    return True


class JablotronProgrammableGate(CoordinatorEntity[JablotronDataCoordinator], BinarySensorEntity):
    """Representation of Jablotron Cloud binary sensor entity."""

    # Allow custom entity names
    _attr_has_entity_name = True

    def __init__(
        self: JablotronProgrammableGate,
        coordinator: JablotronDataCoordinator,
        client: JablotronClient,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
        gate_id: str,
        gate_name: str,
        is_on: bool
    ) -> None:
        """Initialize Jablotron binary sensor."""

        # Define entity attributes
        self._client = client
        self._service_id = service_id
        self._service_name = service_name
        self._service_type = service_type
        self._service_firmware = service_firmware
        self._gate_id = gate_id
        self._gate_name = gate_name

        # Define sensor attributes
        self._attr_name = gate_name
        self._attr_unique_id = f"{service_id}_{gate_id}"
        self._attr_is_on = is_on

        # Initialize binary sensor
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

    # noinspection DuplicatedCode
    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""

        # Get corresponding service data
        _LOGGER.debug("Updating gate state for gate '%s'", self._gate_name)
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)

            return

        # Get service states
        service_states = service["gates"]["states"]
        if not service_states:
            _LOGGER.warning("No states data available for service '%d'!", self._service_id)

            return

        # Get gate state
        gate_state = get_component_state(self._gate_id, service_states)
        if not gate_state:
            _LOGGER.warning("No state available for gate '%s'!", self._gate_name)

            return

        # Set current programmable gate state
        self._attr_is_on = pg_state_to_binary_state(gate_state)
        self.async_write_ha_state()

        _LOGGER.debug("Successfully updated gate state for gate '%s'", self._gate_name)

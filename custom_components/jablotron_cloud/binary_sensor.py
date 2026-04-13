"""Support for Jablotron PG binary sensors."""

from __future__ import annotations

import logging

from jablotronpy import JablotronProgrammableGatesGate

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JablotronClient, JablotronConfigEntry, JablotronData, JablotronDataCoordinator
from .entity import JablotronEntity
from .utils import get_component_state, pg_state_to_binary_state

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register binary sensor entity for each Jablotron service uncontrollable programmable gate."""

    _LOGGER.debug("Adding Jablotron binary sensor entities")
    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    entities: list[JablotronProgrammableGate] = []
    for service_id, service_data in client.services.items():
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        _LOGGER.debug("Getting available programmable gates for service '%s'", service_name)
        gates = service_data["gates"]
        for gate in gates.get("programmableGates", []):
            gate: JablotronProgrammableGatesGate
            gate_name = gate["name"]
            gate_id = gate["cloud-component-id"]
            gate_state = get_component_state(gate_id, gates["states"])
            is_on = pg_state_to_binary_state(gate_state)

            if gate["can-control"]:
                _LOGGER.debug("Programmable gate '%s' is controllable, ignoring!", gate_name)
                continue

            _LOGGER.debug("Adding uncontrollable programmable gate '%s' with initial state '%s'", gate_name, gate_state)
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
                    is_on,
                )
            )

    async_add_entities(entities)


class JablotronProgrammableGate(JablotronEntity, BinarySensorEntity):
    """Representation of Jablotron Cloud binary sensor entity."""

    def __init__(
        self,
        coordinator: JablotronDataCoordinator,
        client: JablotronClient,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
        gate_id: str,
        gate_name: str,
        is_on: bool,
    ) -> None:
        """Initialize Jablotron binary sensor."""
        self._gate_id = gate_id
        self._gate_name = gate_name
        self._attr_name = gate_name
        self._attr_unique_id = f"{service_id}_{gate_id}"
        self._attr_is_on = is_on
        super().__init__(coordinator, client, service_id, service_name, service_type, service_firmware)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)
            return

        service_states = service["gates"]["states"]
        if not service_states:
            _LOGGER.warning("No states data available for service '%d'!", self._service_id)
            return

        gate_state = get_component_state(self._gate_id, service_states)
        if not gate_state:
            _LOGGER.warning("No state available for gate '%s'!", self._gate_name)
            return

        _LOGGER.debug("Gate '%s' received state '%s'", self._gate_name, gate_state)
        self._attr_is_on = pg_state_to_binary_state(gate_state)
        self.async_write_ha_state()

"""Support for Jablotron PG sensors."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import COMP_ID, DOMAIN, PG_STATE, PG_STATE_OFF, SERVICE_TYPE

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

        gates_data = service_data["gates"]
        if not gates_data:
            continue

        gates = gates_data["programmableGates"]
        for gate in gates:
            can_control = gate["can-control"]
            if can_control:
                continue

            gate_id = gate[COMP_ID]
            gate_friendly_name = gate["name"]

            _LOGGER.debug(
                "Jablotron discovered uncontrollable programmable gate: %s:%s",
                gate_id,
                gate_friendly_name,
            )
            entities.append(
                ProgrammableGate(coordinator, service_id, gate_id, gate_friendly_name)
            )

    async_add_entities(entities, True)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


class ProgrammableGate(CoordinatorEntity[JablotronDataCoordinator], BinarySensorEntity):
    """Representation of programmable gate in jablotron system."""

    _attr_has_entity_name = True

    def __init__(
        self: ProgrammableGate,
        coordinator: JablotronDataCoordinator,
        service_id: int,
        gate_id: str,
        friendly_name: str,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._service_id = service_id
        self._gate_id = gate_id
        self._attr_unique_id = f"{service_id} {gate_id}"
        self._attr_name = friendly_name

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
        if not self.coordinator.data or self._service_id not in self.coordinator.data:
            _LOGGER.error("Invalid gate data. Maybe session expired")
            return

        gates_data = self.coordinator.data[self._service_id].get("gates", {})
        states = gates_data.get("states", [])
        for state in states:
            if state[COMP_ID] == self._gate_id:
                _LOGGER.debug("Updating programmable gate with data: %s", str(state))
                self._attr_is_on = not state[PG_STATE] == PG_STATE_OFF
                self.async_write_ha_state()
                return

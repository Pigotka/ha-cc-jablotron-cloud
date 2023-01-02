"""Support for Jablotron PG sensors."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import DOMAIN, PG_ID, PG_STATE, PG_STATE_OFF, SERVICE_TYPE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


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

        gates = service_data["gates"]
        if not gates:
            continue

        for gate in gates:
            gate_id = gate[PG_ID]
            _LOGGER.debug("Jablotron discovered programmable gate: %s", gate_id)
            entities.append(ProgrammableGate(coordinator, service_id, gate_id))

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
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._service_id = service_id
        self._gate_id = gate_id
        self._attr_unique_id = gate_id

    @property
    def name(self) -> str:
        """Return name of programmable gate."""
        return self._gate_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, str(self._service_id))
            },
            name=str(self._service_id),  # use service id or check if name is unique
            manufacturer="Jablotron",
            model=self.coordinator.data[self._service_id][SERVICE_TYPE],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._service_id not in self.coordinator.data:
            _LOGGER.error("Invalid gate data. Maybe session expired")
            return

        gates_data = self.coordinator.data[self._service_id]["gates"]
        for data in gates_data:
            if data[PG_ID] == self._gate_id:
                _LOGGER.debug("Jablotron gate update data: %s", str(data))
                self._attr_is_on = not data[PG_STATE] == PG_STATE_OFF
                self.async_write_ha_state()
                return

"""Support for Jablotron PG binary sensors and section bypass indicators."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from jablotronpy import JablotronProgrammableGatesGate

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from . import JablotronClient, JablotronConfigEntry, JablotronData, JablotronDataCoordinator
from .const import BYPASS_SIGNAL_DURATION, SIGNAL_SECTION_BYPASSED
from .entity import JablotronEntity
from .utils import get_component_state, pg_state_to_binary_state

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register a bypass indicator per section and a binary sensor per uncontrollable PG."""

    _LOGGER.debug("Adding Jablotron binary sensor entities")
    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    entities: list[BinarySensorEntity] = []
    for service_id, service_data in client.services.items():
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        # One bypass indicator per controllable section. A bypass is only ever reported while
        # answering a control request, so these entities are driven by those replies instead of
        # by the coordinator.
        _LOGGER.debug("Getting available sections for service '%s'", service_name)
        for section in service_data["alarm"].get("sections", []):
            if not section["can-control"]:
                continue

            _LOGGER.debug("Adding bypass indicator for section '%s'", section["name"])
            entities.append(
                JablotronSectionBypass(
                    coordinator,
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    section["cloud-component-id"],
                    section["name"],
                )
            )

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


class JablotronSectionBypass(JablotronEntity, BinarySensorEntity):
    """Short lived indicator that a section was armed with active devices bypassed.

    The cloud never volunteers this; it only surfaces while a control request is answered, so
    the entity pulses for ``BYPASS_SIGNAL_DURATION`` and is meant to trigger a notification or
    a dashboard pop-up. Its attributes keep the details of the last bypass after it clears.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:shield-alert-outline"

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
    ) -> None:
        """Initialize Jablotron section bypass indicator."""
        self._section_id = section_id
        self._section_name = section_name
        self._attr_name = f"{section_name} bypass"
        self._attr_unique_id = f"{service_id}_{section_id}_bypass"
        self._attr_is_on = False
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._cancel_auto_off: CALLBACK_TYPE | None = None
        super().__init__(coordinator, client, service_id, service_name, service_type, service_firmware)

    async def async_added_to_hass(self) -> None:
        """Start listening for bypasses reported by the alarm panel entities."""
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_SECTION_BYPASSED, self._handle_bypass))
        self.async_on_remove(self._cancel_pending_auto_off)

    @callback
    def _handle_bypass(self, payload: dict[str, Any]) -> None:
        """Pulse when the bypass belongs to this section."""
        if payload["service_id"] != self._service_id or payload["section_id"] != self._section_id:
            return

        # Restart the full duration when bypasses overlap, so the pulse never ends early.
        self._cancel_pending_auto_off()
        self._attr_is_on = True
        self._attr_extra_state_attributes = {
            "section_name": payload["section_name"],
            "section_id": payload["section_id"],
            "control_error": payload["control_error"],
            "bypassed_at": dt_util.now().isoformat(),
        }
        self.async_write_ha_state()
        self._cancel_auto_off = async_call_later(self.hass, BYPASS_SIGNAL_DURATION, self._clear_bypass)

    @callback
    def _clear_bypass(self, _now: datetime) -> None:
        """Clear the indicator once the signal duration elapsed, keeping the attributes."""
        self._cancel_auto_off = None
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _cancel_pending_auto_off(self) -> None:
        """Drop a scheduled clear, if one is still pending."""
        if self._cancel_auto_off is not None:
            self._cancel_auto_off()
            self._cancel_auto_off = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Ignore polled data: this entity is driven purely by control responses."""


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

"""Support for Jablotron PG switches."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from jablotronpy import (
    BadRequestException,
    IncorrectPinCodeException,
    JablotronProgrammableGatesGate,
    UnauthorizedException,
)

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JablotronClient, JablotronConfigEntry, JablotronData, JablotronDataCoordinator
from .const import DOMAIN
from .entity import JablotronEntity
from .utils import get_component_state, pg_state_to_binary_state

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register switch entity for each Jablotron service controllable programmable gate."""

    _LOGGER.debug("Adding Jablotron switch entities")
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

            if not gate["can-control"]:
                _LOGGER.debug("Programmable gate '%s' is uncontrollable, ignoring!", gate_name)
                continue

            _LOGGER.debug("Adding controllable programmable gate '%s' with initial state '%s'", gate_name, gate_state)
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


class JablotronProgrammableGate(JablotronEntity, SwitchEntity):
    """Representation of Jablotron Cloud switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

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
        """Initialize Jablotron switch."""
        self._gate_id = gate_id
        self._gate_name = gate_name
        self._attr_name = gate_name
        self._attr_unique_id = f"{service_id}_{gate_id}"
        self._attr_is_on = is_on
        super().__init__(coordinator, client, service_id, service_name, service_type, service_firmware)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send turn on request."""
        try:
            _LOGGER.debug("Sending turn on for gate '%s' (service %d)", self._gate_name, self._service_id)
            bridge = await self.hass.async_add_executor_job(self._client.get_bridge)
            turn_on_successful = await self.hass.async_add_executor_job(
                partial(
                    bridge.control_programmable_gate,
                    service_id=self._service_id,
                    service_type=self._service_type,
                    component_id=self._gate_id,
                    state="ON",
                    pin_code=self._client.get_default_pin(),
                )
            )
            if turn_on_successful:
                self._attr_is_on = True
                self.async_write_ha_state()
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except IncorrectPinCodeException as ex:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="invalid_pin") from ex
        except BadRequestException as ex:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="switch_control_failed") from ex

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send turn off request."""
        try:
            _LOGGER.debug("Sending turn off for gate '%s' (service %d)", self._gate_name, self._service_id)
            bridge = await self.hass.async_add_executor_job(self._client.get_bridge)
            turn_off_successful = await self.hass.async_add_executor_job(
                partial(
                    bridge.control_programmable_gate,
                    service_id=self._service_id,
                    service_type=self._service_type,
                    component_id=self._gate_id,
                    state="OFF",
                    pin_code=self._client.get_default_pin(),
                )
            )
            if turn_off_successful:
                self._attr_is_on = False
                self.async_write_ha_state()
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except IncorrectPinCodeException as ex:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="invalid_pin") from ex
        except BadRequestException as ex:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="switch_control_failed") from ex

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

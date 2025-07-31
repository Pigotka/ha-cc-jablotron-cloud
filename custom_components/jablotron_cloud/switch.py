"""Support for Jablotron PG switches."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from jablotronpy import JablotronProgrammableGatesGate, UnauthorizedException, IncorrectPinCodeException

from . import JablotronConfigEntry, JablotronData, JablotronDataCoordinator, JablotronClient
from .const import DOMAIN
from .utils import get_component_state, pg_state_to_binary_state

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: F841
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Register switch entity for each Jablotron service controllable programmable gate."""

    _LOGGER.debug("Adding Jablotron switch entities")
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

        # Add all controllable programmable gate entities
        _LOGGER.debug("Getting available programmable gates for service '%s'", service_name)
        gates = service_data["gates"]
        for gate in gates.get("programmableGates", []):
            # Get gate details
            gate: JablotronProgrammableGatesGate
            gate_name = gate["name"]
            gate_id = gate["cloud-component-id"]
            gate_state = get_component_state(gate_id, gates["states"])
            is_on = pg_state_to_binary_state(gate_state)

            # Check whether programmable gate is controllable
            if not gate["can-control"]:
                _LOGGER.debug("Programmable gate '%s' is uncontrollable, ignoring!", gate_name)

                continue

            # Add controllable programmable gate entity
            _LOGGER.debug("Adding controllable programmable gate '%s'", gate_name)
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
    """Unload switch entities."""

    return True


class JablotronProgrammableGate(CoordinatorEntity[JablotronDataCoordinator], SwitchEntity):
    """Representation of Jablotron Cloud switch entity."""

    # Allow custom entity names
    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

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
        """Initialize Jablotron switch."""

        # Define entity attributes
        self._client = client
        self._service_id = service_id
        self._service_name = service_name
        self._service_type = service_type
        self._service_firmware = service_firmware
        self._gate_id = gate_id
        self._gate_name = gate_name

        # Define switch attributes
        self._attr_name = gate_name
        self._attr_unique_id = f"{service_id}_{gate_id}"
        self._attr_is_on = is_on

        # Initialize switch
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

    def turn_on(self, **kwargs) -> None:
        """Send turn on request."""

        try:
            # Send turn on request to gate
            bridge = self._client.get_bridge()
            turn_on_successful = bridge.control_programmable_gate(
                service_id=self._service_id,
                service_type=self._service_type,
                component_id=self._gate_id,
                state="ON"
            )

            # Set state to on if turn on action was successful
            if turn_on_successful:
                self._attr_is_on = True
                self.schedule_update_ha_state()
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except IncorrectPinCodeException:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_pin"
            )

    def turn_off(self, **kwargs) -> None:
        """Send turn off request."""

        try:
            # Send turn off request to gate
            bridge = self._client.get_bridge()
            turn_off_successful = bridge.control_programmable_gate(
                service_id=self._service_id,
                service_type=self._service_type,
                component_id=self._gate_id,
                state="OFF"
            )

            # Set state to off if turn off action was successful
            if turn_off_successful:
                self._attr_is_on = False
                self.schedule_update_ha_state()
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except IncorrectPinCodeException:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_pin"
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

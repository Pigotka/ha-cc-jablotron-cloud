"""Support for Jablotron alarm control panels."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from jablotronpy import IncorrectPinCodeException, UnauthorizedException

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JablotronClient, JablotronConfigEntry, JablotronData, JablotronDataCoordinator
from .const import DOMAIN
from .entity import JablotronEntity
from .utils import find_section_alarm_event, get_component_state, section_state_to_alarm_state

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register alarm panel entity for each Jablotron service section."""

    _LOGGER.debug("Adding Jablotron alarm control panel entities")
    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    entities: list[JablotronAlarmControlPanel] = []
    for service_id, service_data in client.services.items():
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        _LOGGER.debug("Getting available sections for service '%s'", service_name)
        alarm = service_data["alarm"]
        for section in alarm["sections"]:
            section_name = section["name"]
            section_id = section["cloud-component-id"]
            partial_arm_enabled = section["partial-arm-enabled"]
            requires_authorization = section["need-authorization"]
            if not section["can-control"]:
                _LOGGER.debug("Section '%s' is not controllable, ignoring!", section_name)
                continue

            if find_section_alarm_event(alarm, section_name) is not None:
                current_state = AlarmControlPanelState.TRIGGERED
            else:
                section_state = get_component_state(section_id, alarm["states"])
                current_state = section_state_to_alarm_state(section_state)

            _LOGGER.debug("Adding controllable section '%s' with initial state '%s'", section_name, current_state)
            entities.append(
                JablotronAlarmControlPanel(
                    coordinator,
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    section_id,
                    section_name,
                    partial_arm_enabled,
                    requires_authorization,
                    current_state,
                )
            )

    async_add_entities(entities)


class JablotronAlarmControlPanel(JablotronEntity, AlarmControlPanelEntity):
    """Representation of Jablotron Cloud alarm panel entity."""

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
        partial_arm_enabled: bool,
        requires_authorization: bool,
        current_state: AlarmControlPanelState,
    ) -> None:
        """Initialize Jablotron alarm panel."""
        self._section_id = section_id
        self._section_name = section_name
        self._attr_name = section_name
        self._attr_unique_id = f"{service_id}_{section_id}"
        self._supports_partial_arm = partial_arm_enabled
        self._authorization_required = requires_authorization
        self._attr_alarm_state = current_state
        # Set supported features once during initialization
        self._attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
        if partial_arm_enabled:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_HOME
        super().__init__(coordinator, client, service_id, service_name, service_type, service_firmware)

    @property
    def code_format(self) -> CodeFormat | None:
        """Disable code for sections that don't require it."""
        return CodeFormat.NUMBER if self._authorization_required else None

    @property
    def code_arm_required(self) -> bool:
        """Whether code is required for arm actions."""
        return self._authorization_required

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm request."""
        try:
            code = self.code_or_default_code(code)
            _LOGGER.debug("Sending disarm for section '%s' (service %d)", self._section_name, self._service_id)
            bridge = await self.hass.async_add_executor_job(self._client.get_bridge)
            disarm_successful = await self.hass.async_add_executor_job(
                partial(
                    bridge.control_section,
                    service_id=self._service_id,
                    service_type=self._service_type,
                    component_id=self._section_id,
                    state="DISARM",
                    pin_code=code,
                )
            )
            if disarm_successful:
                self._attr_alarm_state = AlarmControlPanelState.DISARMING
                self.async_write_ha_state()
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except IncorrectPinCodeException as ex:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="invalid_pin") from ex

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm request."""
        try:
            code = self.code_or_default_code(code)
            _LOGGER.debug(
                "Sending arm away for section '%s' (service %d, force=%s)",
                self._section_name,
                self._service_id,
                self._client.force_arm,
            )
            bridge = await self.hass.async_add_executor_job(self._client.get_bridge)
            arm_successful = await self.hass.async_add_executor_job(
                partial(
                    bridge.control_section,
                    service_id=self._service_id,
                    service_type=self._service_type,
                    component_id=self._section_id,
                    state="ARM",
                    pin_code=code,
                    force=self._client.force_arm,
                )
            )
            if arm_successful:
                self._attr_alarm_state = AlarmControlPanelState.ARMING
                self.async_write_ha_state()
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except IncorrectPinCodeException as ex:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="invalid_pin") from ex

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send partial arm request."""
        if not self._supports_partial_arm:
            return

        try:
            code = self.code_or_default_code(code)
            _LOGGER.debug(
                "Sending arm home for section '%s' (service %d, force=%s)",
                self._section_name,
                self._service_id,
                self._client.force_arm,
            )
            bridge = await self.hass.async_add_executor_job(self._client.get_bridge)
            arm_successful = await self.hass.async_add_executor_job(
                partial(
                    bridge.control_section,
                    service_id=self._service_id,
                    service_type=self._service_type,
                    component_id=self._section_id,
                    state="PARTIAL_ARM",
                    pin_code=code,
                    force=self._client.force_arm,
                )
            )
            if arm_successful:
                self._attr_alarm_state = AlarmControlPanelState.ARMING
                self.async_write_ha_state()
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except IncorrectPinCodeException as ex:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="invalid_pin") from ex

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the matching alarm event details while this section is triggered."""
        service = self._client.services.get(self._service_id)
        if not service:
            return None

        event = find_section_alarm_event(service["alarm"], self._section_name)
        if event is None:
            return None

        return {
            "last_alarm_date": event.get("date"),
            "last_alarm_message": event.get("message"),
            "last_alarm_type": event.get("type"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)
            return

        alarm = service["alarm"]
        event = find_section_alarm_event(alarm, self._section_name)
        if event is not None:
            _LOGGER.debug("Section '%s' triggered: %s", self._section_name, event.get("message"))
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
            self.async_write_ha_state()
            return

        service_states = alarm["states"]
        if not service_states:
            _LOGGER.warning("No states data available for service '%d'!", self._service_id)
            return

        section_state = get_component_state(self._section_id, service_states)
        if not section_state:
            _LOGGER.warning("No state available for section '%s'!", self._section_name)
            return

        _LOGGER.debug("Section '%s' received state '%s'", self._section_name, section_state)
        self._attr_alarm_state = section_state_to_alarm_state(section_state)
        self.async_write_ha_state()

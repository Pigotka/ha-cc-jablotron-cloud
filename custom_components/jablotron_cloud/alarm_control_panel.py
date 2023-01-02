"""Support for Jablotron alarm control panels."""
from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import DOMAIN, SERVICE_TYPE, Actions

_LOGGER = logging.getLogger(__name__)


def get_sections(bridge, service_id):
    """Pools section data from Jablotron cloud."""
    return bridge.get_sections(service_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up alarm panel from Jablotron Cloud from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    services = coordinator.data
    entities = []

    if not services:
        return

    for service_id in services:
        _LOGGER.debug("Jablotron discovered one service: %s", service_id)

        sections = await hass.async_add_executor_job(
            get_sections, coordinator.bridge, service_id
        )

        if not sections:
            return

        for section in sections:
            can_control = section["can-control"]
            if can_control:
                _LOGGER.debug("Controllable section discovered: %s", section["name"])
                component_id = section["cloud-component-id"]
                partial_arm_enabled = bool(section["partial-arm-enabled"])
                need_authorization = bool(section["need-authorization"])
                friendly_name = section["name"]
                entities.append(
                    JablotronAlarmControlPanel(
                        coordinator,
                        service_id,
                        component_id,
                        partial_arm_enabled,
                        need_authorization,
                        friendly_name,
                    )
                )

    async_add_entities(entities, True)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


class JablotronAlarmControlPanel(
    CoordinatorEntity[JablotronDataCoordinator],
    AlarmControlPanelEntity,
):
    """Representation of an Jablotron cloud based alarm panel."""

    _attr_name = "Jablotron Alarm Panel"
    _attr_code_format = CodeFormat.NUMBER
    _attr_has_entity_name = True

    def __init__(
        self: JablotronAlarmControlPanel,
        coordinator: JablotronDataCoordinator,
        service_id: int,
        component_id: str,
        partial_arm_enabled: bool,
        need_authorization: bool,
        friendly_name: str,
    ) -> None:
        """Initialize Jablotron alarm panel."""
        super().__init__(coordinator)
        self._service_id = service_id
        self._component_id = component_id
        self._can_partial_arm = partial_arm_enabled
        self._need_authorization = need_authorization
        self._attr_unique_id = f"{service_id} {component_id}"
        self._attr_name = friendly_name
        self._use_configured_pin = len(self.coordinator.bridge.pin_code) > 0

    @property
    def code_arm_required(self) -> bool:
        """Whether the code is required for arm actions."""
        return self._need_authorization and not self._use_configured_pin

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        if self._can_partial_arm:
            return (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
            )

        return AlarmControlPanelEntityFeature.ARM_AWAY

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not self._validate_and_setup_code(code):
            return

        service_type = self.coordinator.data[self._service_id][SERVICE_TYPE]
        self.coordinator.bridge.control_component(
            self._service_id, self._component_id, Actions.DISARM, service_type
        )
        self._attr_state = STATE_ALARM_DISARMING
        self.async_write_ha_state()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if not self._validate_and_setup_code(code):
            return

        service_type = self.coordinator.data[self._service_id][SERVICE_TYPE]
        self.coordinator.bridge.control_component(
            self._service_id, self._component_id, Actions.ARM, service_type
        )
        self._attr_state = STATE_ALARM_ARMING
        self.async_write_ha_state()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm away command."""
        if not self._can_partial_arm:
            _LOGGER.error("This action should not be triggered for this section")
            return

        if not self._validate_and_setup_code(code):
            return

        service_type = self.coordinator.data[self._service_id][SERVICE_TYPE]
        self.coordinator.bridge.control_component(
            self._service_id, self._component_id, Actions.PARTIAL_ARM, service_type
        )
        self._attr_state = STATE_ALARM_ARMING
        self.async_write_ha_state()

    def _validate_and_setup_code(self, code: str | None) -> bool:
        if self.code_arm_required:
            if code is None:
                _LOGGER.error("Code expected by the section but not provided")
                return False
            self.coordinator.bridge.pin_code = code
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._service_id not in self.coordinator.data:
            _LOGGER.error("Invalid gate data. Maybe session expired")
            return

        service_data = self.coordinator.data[self._service_id]
        states = service_data["extended-states"]
        _LOGGER.debug("Alarm panel update state: %s", str(states))
        disarm_state = next(filter(lambda data: data["type"] == "DISARM", states))
        self._attr_state = (
            STATE_ALARM_DISARMED
            if int(disarm_state["value"])
            else STATE_ALARM_ARMED_AWAY
        )
        self.async_write_ha_state()

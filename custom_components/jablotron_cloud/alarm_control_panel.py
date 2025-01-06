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
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronDataCoordinator
from .const import COMP_ID, DOMAIN, SERVICE_TYPE, Actions

_LOGGER = logging.getLogger(__name__)


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

    for service_id, service_data in services.items():
        service = service_data["service"]
        _LOGGER.debug(
            "Jablotron discovered service: %s:%s", service_id, service["name"]
        )

        sections_data = service_data["sections"]
        if not sections_data:
            _LOGGER.debug(
                "Jablotron sections date are empty, skipping service: %s:%s", service_id, service["name"]
            )
            continue

        sections = sections_data["sections"]
        if not sections:
            _LOGGER.debug(
                "Jablotron section date are empty, skipping service: %s:%s", service_id, service["name"]
            )            
            continue

        for section in sections:
            can_control = section["can-control"]
            if can_control:
                friendly_name = section["name"]
                component_id = section[COMP_ID]
                partial_arm_enabled = bool(section["partial-arm-enabled"])
                need_authorization = bool(section["need-authorization"])
                _LOGGER.debug("Controllable section discovered: %s", friendly_name)
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

    _attr_has_entity_name = True

    _actions_to_state_alarm = {
        Actions.ARM: STATE_ALARM_ARMED_AWAY,
        Actions.DISARM: STATE_ALARM_DISARMED,
        Actions.PARTIAL_ARM: STATE_ALARM_ARMED_HOME,
    }

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
        self._service_type = self.coordinator.data[service_id]["service"][SERVICE_TYPE]

    @property
    def code_format(self) -> CodeFormat | None:
        """Disable code for sections that don't require it."""
        return CodeFormat.NUMBER if self.code_arm_required else None

    @property
    def code_arm_required(self) -> bool:
        """Whether the code is required for arm actions."""
        return self._need_authorization

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        if self._can_partial_arm:
            return (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
            )

        return AlarmControlPanelEntityFeature.ARM_AWAY

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

    def alarm_disarm(self, code: str | None = None) -> None:
        """Disarm section."""
        self._setup_pin(code)

        self.coordinator.bridge.control_component(
            self._service_id, self._component_id, Actions.DISARM, self._service_type
        )
        self._attr_state = STATE_ALARM_DISARMING
        self.schedule_update_ha_state()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Arm section."""
        self._setup_pin(code)

        self.coordinator.bridge.control_component(
            self._service_id, self._component_id, Actions.ARM, self._service_type, force=True
        )
        self._attr_state = STATE_ALARM_ARMING
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Partial arm section if allowed."""
        if not self._can_partial_arm:
            _LOGGER.error("This action should not be available for this section")
            return

        self._setup_pin(code)
        self.coordinator.bridge.control_component(
            self._service_id,
            self._component_id,
            Actions.PARTIAL_ARM,
            self._service_type,
            force=True
        )
        self._attr_state = STATE_ALARM_ARMING
        self.schedule_update_ha_state()

    def _setup_pin(self, code: str | None) -> None:
        self.coordinator.bridge.pin_code = self.code_or_default_code(code)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data or self._service_id not in self.coordinator.data:
            _LOGGER.error("Invalid section data. Maybe session expired")
            return

        sections_data = self.coordinator.data[self._service_id].get("sections", {})
        states = sections_data.get("states", [])
        if not states:
            _LOGGER.warning("States data not found")
            return

        state = next(filter(lambda data: data[COMP_ID] == self._component_id, states))
        _LOGGER.debug("Updating section state: %s", str(state))
        self._attr_state = self._actions_to_state_alarm.get(
            state["state"], STATE_ALARM_DISARMED
        )
        self.schedule_update_ha_state()

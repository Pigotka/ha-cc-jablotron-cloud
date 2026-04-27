"""Utils for Jablotron Cloud integration."""

import logging

from jablotronpy import (
    JablotronProgrammableGatesState,
    JablotronSections,
    JablotronSectionsState,
    JablotronThermoDevice,
)

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import ALARM_EVENT_TYPE, PG_STATE_AS_BINARY_STATE, SECTION_STATE_AS_ALARM_STATE

_LOGGER = logging.getLogger(__name__)

SECTION_TOKEN = ", Section "


@callback
def update_unique_id(entity_entry: RegistryEntry) -> dict | None:
    """Migrate unique id of existing entities to the new schema."""

    # Check whether unique id contains space
    if " " in entity_entry.unique_id:
        _LOGGER.info("Migrating entity '%s' to the new unique id schema", entity_entry.entity_id)

        return {"new_unique_id": entity_entry.unique_id.replace(" ", "_")}

    return None


def get_component_state(
    component_id: str,
    states: list[JablotronSectionsState | JablotronProgrammableGatesState],
) -> str | None:
    """Return Jablotron component state."""

    # Get component state dict
    component_state: JablotronSectionsState | JablotronProgrammableGatesState | None = next(
        filter(lambda state: state["cloud-component-id"] == component_id, states),
        None,
    )
    if not component_state:
        return None

    return component_state["state"]


def section_state_to_alarm_state(state: str | None) -> AlarmControlPanelState:
    """Convert section state to AlarmControlPanelState."""

    return SECTION_STATE_AS_ALARM_STATE.get(state, STATE_UNKNOWN)


def pg_state_to_binary_state(state: str | None) -> bool:
    """Convert programmable gate state to boolean value."""

    return PG_STATE_AS_BINARY_STATE.get(state, False)


def get_service_alarm_events(alarm: JablotronSections) -> list[dict]:
    """Return active service-level events from sections payload, or empty list."""

    return alarm.get("service-states", {}).get("events", []) or []


def find_section_alarm_event(alarm: JablotronSections, section_name: str) -> dict | None:
    """Return the most recent ALARM event whose message references the given section, or None.

    The Jablotron event message format is 'Alarm - <detector>, Section <section name>'.
    The section is identified by the substring after the literal ', Section ' token.
    """

    matches = [
        event
        for event in get_service_alarm_events(alarm)
        if event.get("type") == ALARM_EVENT_TYPE
        and event.get("message", "").rsplit(SECTION_TOKEN, 1)[-1].strip() == section_name
    ]

    return matches[-1] if matches else None


def get_thermo_device(
    device_id: str,
    devices: list[JablotronThermoDevice],
) -> JablotronThermoDevice | None:
    """Return Jablotron thermo device by ID."""

    return next(
        filter(lambda device: device["object-device-id"] == device_id, devices),
        None,
    )

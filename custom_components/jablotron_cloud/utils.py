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


def get_event_section_name(message: str, section_names: list[str]) -> str | None:
    """Return the name of the section the event message refers to, or None when it names no known section.

    The Jablotron event message ends with the section name, e.g. 'Alarm - <detector>, Section <section name>',
    but the wording before the name is localized ('Sezione', 'Sekce', ...) and the section part can be missing
    entirely. Only the trailing section name is therefore matched; the longest match wins so that
    'Guest House' is not mistaken for 'House'.
    """

    normalized_message = message.strip().casefold()
    matches: list[str] = []
    for section_name in section_names:
        normalized_name = section_name.strip().casefold()
        if not normalized_name or not normalized_message.endswith(normalized_name):
            continue

        # Require a word boundary so that section 'House' does not match 'Section Warehouse'.
        preceding = normalized_message[: -len(normalized_name)]
        if not preceding or not preceding[-1].isalnum():
            matches.append(section_name)

    return max(matches, key=len, default=None)


def find_section_alarm_event(alarm: JablotronSections, section_name: str) -> dict | None:
    """Return the most recent ALARM event that applies to the given section, or None.

    An event applies to the section its message ends with. An ALARM event that names no known section
    cannot be attributed, so it is ignored and the raw event is logged to help identify its format.
    """

    section_names = [section["name"] for section in alarm.get("sections", [])]
    matches: list[dict] = []
    for event in get_service_alarm_events(alarm):
        if event.get("type") != ALARM_EVENT_TYPE:
            continue

        event_section_name = get_event_section_name(event.get("message", ""), section_names)
        if event_section_name is None:
            _LOGGER.warning("Ignoring alarm event that names no known section (%s): %s", section_names, event)
        elif event_section_name == section_name:
            matches.append(event)

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

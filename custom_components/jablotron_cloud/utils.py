"""Utils for Jablotron Cloud integration."""

import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import RegistryEntry
from jablotronpy import JablotronSectionsState, JablotronProgrammableGatesState

from .const import SECTION_STATE_AS_ALARM_STATE, PG_STATE_AS_BINARY_STATE

_LOGGER = logging.getLogger(__name__)


@callback
def update_unique_id(entity_entry: RegistryEntry) -> dict | None:
    """Migrate unique id of existing entities to the new schema."""

    # Check whether unique id contains space
    if " " in entity_entry.unique_id:
        _LOGGER.info("Migrating entity '%s' to the new unique id schema", entity_entry.entity_id)

        return {
            "new_unique_id": entity_entry.unique_id.replace(" ", "_")
        }

    return None


def get_component_state(
    component_id: str,
    states: list[JablotronSectionsState | JablotronProgrammableGatesState]
) -> str | None:
    """Return Jablotron component state."""

    # Get component state dict
    component_state = next(filter(lambda state: state["cloud-component-id"] == component_id, states), None)
    if not component_state:
        return None

    # Return component state value
    component_state: JablotronSectionsState | JablotronProgrammableGatesState
    return component_state["state"]


def section_state_to_alarm_state(state: str | None) -> AlarmControlPanelState:
    """Convert section state to AlarmControlPanelState."""

    return SECTION_STATE_AS_ALARM_STATE.get(state, STATE_UNKNOWN)


def pg_state_to_binary_state(state: str | None) -> bool:
    """Convert programmable gate state to boolean value."""

    return PG_STATE_AS_BINARY_STATE.get(state, False)

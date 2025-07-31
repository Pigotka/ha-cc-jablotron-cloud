"""Constants for Jablotron Cloud integration."""

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import Platform

# Integration constants
DOMAIN = "jablotron_cloud"
UNSUPPORTED_SERVICES = ["FUTURA2", "AMBIENTA", "VOLTA", "LOGBOOK"]
PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SENSOR,
]

# Jablotron states as Home Assistant states
SECTION_STATE_AS_ALARM_STATE = {
    "ARM": AlarmControlPanelState.ARMED_AWAY,
    "PARTIAL_ARM": AlarmControlPanelState.ARMED_HOME,
    "DISARM": AlarmControlPanelState.DISARMED,
}

PG_STATE_AS_BINARY_STATE = {
    "ON": True,
    "OFF": False
}

"""Constants for Jablotron Cloud integration."""

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.climate import HVACMode
from homeassistant.const import Platform

# Integration constants
ALARM_EVENT_TYPE = "ALARM"
DOMAIN = "jablotron_cloud"
UNSUPPORTED_SERVICES = ["FUTURA2", "AMBIENTA", "VOLTA", "LOGBOOK"]
PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Jablotron states as Home Assistant states
SECTION_STATE_AS_ALARM_STATE = {
    "ARM": AlarmControlPanelState.ARMED_AWAY,
    "PARTIAL_ARM": AlarmControlPanelState.ARMED_HOME,
    "DISARM": AlarmControlPanelState.DISARMED,
}

PG_STATE_AS_BINARY_STATE = {"ON": True, "OFF": False}

# Jablotron thermo device heating modes as HVAC modes
THERMO_STATE_TO_HVAC_MODE = {
    "OFF": HVACMode.OFF,
    "STAND_BY": HVACMode.OFF,
    "MANUAL": HVACMode.HEAT,
    "MANUAL_TEMP": HVACMode.HEAT,
    "SCHEDULED": HVACMode.AUTO,
    "ON": HVACMode.HEAT,
}

HVAC_MODE_TO_THERMO_STATE = {
    HVACMode.OFF: "OFF",
    HVACMode.HEAT: "MANUAL",
    HVACMode.AUTO: "SCHEDULED",
}

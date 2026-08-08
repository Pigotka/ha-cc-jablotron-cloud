"""Constants for Jablotron Cloud integration."""

from datetime import timedelta

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

# Section bypass constants
# Control errors meaning "devices in this section are active and must be bypassed to arm".
# The cloud reports them against the section only; the API exposes no endpoint listing
# detectors, so a bypass can never be attributed to the door or window that caused it.
BYPASS_CONTROL_ERRORS = ("BYPASS", "BYPASS-TIMED")

# How long a section's bypass binary sensor stays on after an arm that required a bypass.
# A bypass is only ever reported in the reply to a control request, so the sensor is a short
# pulse meant to drive a notification or a pop-up rather than a lasting state.
BYPASS_SIGNAL_DURATION = timedelta(seconds=30)

# Fired on the Home Assistant bus for every arm that required active devices to be bypassed.
EVENT_SECTION_BYPASSED = f"{DOMAIN}_section_bypassed"

# Dispatcher signal telling a section's bypass binary sensor to pulse.
SIGNAL_SECTION_BYPASSED = f"{DOMAIN}_section_bypassed_signal"

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

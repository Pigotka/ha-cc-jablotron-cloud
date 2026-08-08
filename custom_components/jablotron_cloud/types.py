"""Types for Jablotron Cloud integration."""

from dataclasses import dataclass
from typing import TypedDict

from jablotronpy import JablotronProgrammableGates, JablotronSections, JablotronThermoDevice


@dataclass(frozen=True)
class JablotronServiceCapabilities:
    """Endpoints a Jablotron service actually provides data for (discovered during setup)."""

    has_gates: bool
    has_sections: bool
    has_thermo: bool


@dataclass(frozen=True)
class JablotronSectionControlResult:
    """Outcome of a single section control request.

    ``bypassed`` is True when the section could only reach the requested state because active
    devices were bypassed; ``control_error`` then carries the code the cloud reported for the
    first, un-forced attempt (``BYPASS-TIMED`` for example). The cloud identifies only the
    section in that error, never the detector that triggered it, so nothing more specific than
    the section can be reported to Home Assistant.
    """

    success: bool
    bypassed: bool = False
    control_error: str | None = None


class JablotronServiceData(TypedDict):
    """Typed dictionary representing data for a single Jablotron service."""

    name: str
    type: str
    firmware: str
    alarm: JablotronSections
    gates: JablotronProgrammableGates
    thermo: list[JablotronThermoDevice]

"""Types for Jablotron Cloud integration."""

from typing import TypedDict

from jablotronpy import JablotronProgrammableGates, JablotronSections, JablotronThermoDevice


class JablotronServiceData(TypedDict):
    name: str
    type: str
    firmware: str
    alarm: JablotronSections
    gates: JablotronProgrammableGates
    thermo: list[JablotronThermoDevice]

from typing import TypedDict

from jablotronpy import (
    JablotronProgrammableGates,
    JablotronSections,
    JablotronThermoDevice,
)

JablotronServiceData = TypedDict(
    "JablotronServiceData",
    {
        "name": str,
        "type": str,
        "firmware": str,
        "alarm": JablotronSections,
        "gates": JablotronProgrammableGates,
        "thermo": list[JablotronThermoDevice],
    },
)

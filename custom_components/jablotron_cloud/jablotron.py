"""Client for Jablotron Cloud API."""

from jablotronpy import Jablotron

from .types import JablotronServiceData


class JablotronClient:
    """Client for Jablotron Cloud API."""

    services: dict[int, JablotronServiceData] = {}

    def __init__(self, username: str, password: str, default_pin: str | None = None, force_arm: bool = True) -> None:
        """Initialize Jablotron client."""

        self._username = username
        self._password = password
        self._default_pin = default_pin
        self.force_arm = force_arm

    def get_bridge(self) -> Jablotron:
        """Return Jablotron bridge instance."""

        bridge = Jablotron(self._username, self._password, self._default_pin)
        bridge.perform_login()

        return bridge

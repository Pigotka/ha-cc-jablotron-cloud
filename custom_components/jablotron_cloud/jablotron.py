"""Client for Jablotron Cloud API."""

from collections.abc import Callable
import logging
import threading
from typing import Literal

from jablotronpy import (
    Jablotron,
    JablotronProgrammableGates,
    JablotronSections,
    JablotronService,
    JablotronServiceInformation,
    JablotronThermoDevice,
    SessionExpiredException,
    UnauthorizedException,
)

from .const import THERMO_CONFIRM_INTERVAL, THERMO_CONFIRM_TIMEOUT
from .types import JablotronServiceData

_LOGGER = logging.getLogger(__name__)


class JablotronClient:
    """Client for Jablotron Cloud API with a persistent, self-healing session."""

    def __init__(
        self,
        username: str,
        password: str,
        default_pin: str | None = None,
        force_arm: bool = True,
    ) -> None:
        """Initialize Jablotron client."""

        self.services: dict[int, JablotronServiceData] = {}
        self.force_arm = force_arm
        self._username = username
        self._password = password
        self._default_pin = default_pin
        # The bridge doubles as the session marker: None means not logged in, and a
        # bridge instance carries the session cookie set by perform_login().
        self._bridge: Jablotron | None = None
        self._login_lock = threading.Lock()

    def get_default_pin(self) -> str | None:
        """Return the default PIN code."""

        return self._default_pin

    def validate_login(self) -> None:
        """Validate credentials by performing a login."""

        self._ensure_logged_in()

    def _ensure_logged_in(self) -> Jablotron:
        """Return a logged-in bridge, performing a login when there is none.

        The session is reused until an API call fails with an expired session;
        there is no time-based refresh, so no login request is spent while the
        session stays valid. Must only be called from executor threads.
        """

        with self._login_lock:
            if self._bridge is None:
                _LOGGER.debug("Logging in to Jablotron Cloud")
                # A fresh bridge is created for every login so the login request is not sent
                # with a stale session cookie, and it is assigned only after the login
                # succeeds, so a failed login never leaves a broken session behind.
                bridge = Jablotron(self._username, self._password, self._default_pin)
                bridge.perform_login()
                self._bridge = bridge
            return self._bridge

    def _invalidate_session(self, bridge: Jablotron) -> None:
        """Drop the bridge unless another thread already re-logged in with a new one."""

        with self._login_lock:
            if self._bridge is bridge:
                self._bridge = None

    def _api_call[T](self, func: Callable[[Jablotron], T]) -> T:
        """Run an API call, transparently re-logging in once when the session is no longer valid.

        An expired session and bad credentials both surface as UnauthorizedException, so the
        re-login disambiguates them: with bad credentials the re-login itself raises
        UnauthorizedException, which is the only way an auth error propagates to callers.
        """

        bridge = self._ensure_logged_in()
        try:
            return func(bridge)
        except (SessionExpiredException, UnauthorizedException):
            _LOGGER.debug("Jablotron Cloud session is no longer valid, re-logging in and retrying")
            self._invalidate_session(bridge)
            return func(self._ensure_logged_in())

    def get_services(self) -> list[JablotronService]:
        """Return list of services associated with the Jablotron Cloud account."""

        return self._api_call(lambda bridge: bridge.get_services())

    def get_service_information(self, service_id: int) -> JablotronServiceInformation:
        """Return information about the specified service."""

        return self._api_call(lambda bridge: bridge.get_service_information(service_id))

    def get_sections(self, service_id: int, service_type: str = "JA100") -> JablotronSections:
        """Return sections and their states for the specified service."""

        return self._api_call(lambda bridge: bridge.get_sections(service_id, service_type))

    def get_programmable_gates(self, service_id: int, service_type: str = "JA100") -> JablotronProgrammableGates:
        """Return programmable gates and their states for the specified service."""

        return self._api_call(lambda bridge: bridge.get_programmable_gates(service_id, service_type))

    def get_thermo_devices(self, service_id: int, service_type: str = "JA100") -> list[JablotronThermoDevice]:
        """Return list of thermo devices for the specified service."""

        return self._api_call(lambda bridge: bridge.get_thermo_devices(service_id, service_type))

    def control_section(
        self,
        service_id: int,
        component_id: str,
        state: Literal["ARM", "PARTIAL_ARM", "DISARM"],
        pin_code: str | None = None,
        service_type: str = "JA100",
        force: bool = False,
    ) -> bool:
        """Set section of the specified service to the desired state."""

        return self._api_call(
            lambda bridge: bridge.control_section(service_id, component_id, state, pin_code, service_type, force)
        )

    def control_programmable_gate(
        self,
        service_id: int,
        component_id: str,
        state: Literal["ON", "OFF"],
        pin_code: str | None = None,
        service_type: str = "JA100",
        force: bool = False,
    ) -> bool:
        """Set programmable gate of the specified service to the desired state."""

        return self._api_call(
            lambda bridge: bridge.control_programmable_gate(
                service_id, component_id, state, pin_code, service_type, force
            )
        )

    def control_thermo_device(
        self,
        service_id: int,
        object_device_id: str,
        heating_mode: Literal["MANUAL", "SCHEDULED", "OFF", "ON"] | None = None,
        temperature: float | None = None,
        service_type: str = "JA100",
    ) -> bool:
        """Set thermo device of the specified service to the desired heating mode or temperature.

        After a 502/504 response the device is polled until it reflects the change, so this call can block
        for up to THERMO_CONFIRM_TIMEOUT seconds.
        """

        return self._api_call(
            lambda bridge: bridge.control_thermo_device(
                service_id,
                object_device_id,
                heating_mode,
                temperature,
                service_type,
                confirm_timeout=THERMO_CONFIRM_TIMEOUT,
                confirm_interval=THERMO_CONFIRM_INTERVAL,
            )
        )

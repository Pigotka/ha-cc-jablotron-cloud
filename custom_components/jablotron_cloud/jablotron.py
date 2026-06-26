"""Client for Jablotron Cloud API."""

import logging
import threading
from datetime import datetime, timedelta

from jablotronpy import Jablotron

from .types import JablotronServiceData

_LOGGER = logging.getLogger(__name__)

# How long a cached session is considered valid (Jablotron sessions last ~30 min,
# we refresh proactively at 25 min to avoid edge-case expiry mid-request)
_SESSION_TTL_MINUTES = 25


class JablotronClient:
    """Client for Jablotron Cloud API."""

    services: dict[int, JablotronServiceData] = {}

    def __init__(
        self,
        username: str,
        password: str,
        default_pin: str | None = None,
        force_arm: bool = True,
    ) -> None:
        """Initialize Jablotron client."""

        self._username = username
        self._password = password
        self._default_pin = default_pin
        self.force_arm = force_arm

        # Session cache — shared across all callers (coordinator + entities)
        self._bridge: Jablotron | None = None
        self._session_expires: datetime | None = None
        self._lock = threading.Lock()

    def get_bridge(self) -> Jablotron:
        """Return a cached Jablotron bridge instance, logging in only when necessary.

        A single shared session is reused for the lifetime of the TTL so that
        the integration never hammers userAuthorize.json on every poll cycle or
        every entity action, which is what causes the Jablotron Cloud 429 ban.
        """

        with self._lock:
            now = datetime.now()

            # Return the cached bridge if it is still valid
            if self._bridge is not None and self._session_expires is not None:
                if now < self._session_expires:
                    _LOGGER.debug(
                        "Reusing cached Jablotron session (expires in %.0f s)",
                        (self._session_expires - now).total_seconds(),
                    )
                    return self._bridge

            # Session is missing or expired — create a fresh one
            _LOGGER.debug("Creating new Jablotron session (performing login)")
            bridge = Jablotron(self._username, self._password, self._default_pin)
            bridge.perform_login()

            self._bridge = bridge
            self._session_expires = now + timedelta(minutes=_SESSION_TTL_MINUTES)
            _LOGGER.debug(
                "Jablotron session established, valid until %s",
                self._session_expires.strftime("%H:%M:%S"),
            )

            return self._bridge

    def invalidate_session(self) -> None:
        """Force the next get_bridge() call to perform a fresh login.

        Call this whenever an API call fails with an auth/session error so that
        the stale cached bridge is discarded immediately instead of being reused
        for the remaining TTL.
        """

        with self._lock:
            _LOGGER.debug("Invalidating cached Jablotron session")
            self._bridge = None
            self._session_expires = None

    def get_default_pin(self) -> str | None:
        """Return the default PIN code."""

        return self._default_pin

"""The Jablotron Cloud integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from jablotronpy import Jablotron

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SERVICE_ID

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.ALARM_CONTROL_PANEL]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jablotron Cloud from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    pin = entry.data.get(CONF_PIN, "")

    _LOGGER.debug("Preparing Jablotron data update coordinator")

    bridge = Jablotron(username, password, pin)
    coordinator = JablotronDataCoordinator(hass, bridge)

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


class JablotronDataCoordinator(DataUpdateCoordinator):
    """Data coordinator around jablotron cloud API."""

    def __init__(self, hass, bridge):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Jablotron",
            update_interval=timedelta(seconds=30),
        )
        self.bridge = bridge
        self.session_id = None

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                if self.session_id is None:
                    self.session_id = await self.hass.async_add_executor_job(
                        self.bridge.get_session_id
                    )

                services = await self.hass.async_add_executor_job(
                    self.bridge.get_services
                )

                data = {}
                for service in services:
                    service_id = service[SERVICE_ID]
                    gates = await self.hass.async_add_executor_job(
                        self.bridge.get_programmable_gates, service_id
                    )
                    service["gates"] = gates
                    data[service_id] = service

                return data
        except Exception:  # pylint: disable=broad-except
            self.session_id = None

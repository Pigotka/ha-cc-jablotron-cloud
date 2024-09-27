"""The Jablotron Cloud integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from jablotronpy import Jablotron, UnexpectedResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SERVICE_ID, SERVICE_TYPE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SENSOR,
]

ASYNC_TIMEOUT = 120

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jablotron Cloud from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    pin = entry.data[CONF_PIN]

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
            name="Jablotron Cloud",
            update_interval=timedelta(seconds=30),
        )
        self.bridge = bridge
        self.is_first_update = True
        self.api_fail_count = 0

    async def _recreate_bridge(self):
        # recreate bridge to restart connection until it is fixed on bridge side
        self.bridge = Jablotron(self.bridge.username, self.bridge.password, self.bridge.pin_code)
        _LOGGER.warning("Bridge recreated.")

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        data = {}
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(ASYNC_TIMEOUT):                        

            # API is failing, try to recreate session
            if self.api_fail_count > 0:
                try:
                    session_id = await self.hass.async_add_executor_job(
                        self.bridge.get_session_id
                    )
                except UnexpectedResponse as error:
                    _LOGGER.debug("Unable to get session id.")
                    await self._recreate_bridge()
                    raise UpdateFailed("Unable to get session ID. JablotronPy bridge recreated.") from error

                if not session_id:
                    _LOGGER.debug("Invalid session id.")
                    await self._recreate_bridge()
                    return

                # session is valid reset fail counter and continue
                self.api_fail_count = 0

            services = None
            try:
                services = await self.hass.async_add_executor_job(
                    self.bridge.get_services
                )
            except UnexpectedResponse as error:
                self.api_fail_count += 1
                _LOGGER.debug("Failed to get services!")
                raise UpdateFailed("Failed to get services!") from error

            if not services:
                _LOGGER.info("No services discovered for this jablotron account. No entities will be generated.")
                return data

            for service in services:
                service_id = service[SERVICE_ID]
                service_type = service[SERVICE_TYPE]

                _LOGGER.debug("Loading data for service %d", service_id)
                if service_type == 'LOGBOOK':
                    _LOGGER.debug("Service type %s not supported. Skipping service %d", service_type, service_id)
                    continue
                
                try:
                    gates = await self.hass.async_add_executor_job(
                        self.bridge.get_programmable_gates, service_id, service_type
                    )
                except UnexpectedResponse as error:
                    self.api_fail_count += 1
                    _LOGGER.debug(f"Failed to get gates data for service {service_id}")
                    raise UpdateFailed(f"Failed to get gates data for service {service_id}") from error
            
                try:
                    sections = await self.hass.async_add_executor_job(
                        self.bridge.get_sections, service_id, service_type
                    )
                except UnexpectedResponse as error:                    
                    self.api_fail_count += 1
                    _LOGGER.debug(f"Failed to get section data for service {service_id}")
                    raise UpdateFailed(f"Failed to get section data for service {service_id}") from error                                        

                try:
                    thermo_devices = await self.hass.async_add_executor_job(
                        self.bridge.get_thermo_devices, service_id, service_type
                    )
                except UnexpectedResponse as error:
                    self.api_fail_count += 1
                    _LOGGER.debug(f"Failed to get thermo data for service {service_id}")
                    raise UpdateFailed(f"Failed to get thermo data for service {service_id}") from error

                
                data[service_id] = {}
                data[service_id]["service"] = service
                data[service_id]["gates"] = gates
                data[service_id]["sections"] = sections
                data[service_id]["thermo"] = thermo_devices

                _LOGGER.debug("Service %d successfuly updated.", service_id)
                if self.is_first_update:                    
                    _LOGGER.debug("Service %d discovered. Data: %s", service_id, str(data[service_id]))

            self.is_first_update = False            
            return data


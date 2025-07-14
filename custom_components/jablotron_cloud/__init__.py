"""Jablotron Cloud integration."""

from __future__ import annotations

import logging
from asyncio import timeout
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_FORCE_UPDATE,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_registry import async_migrate_entries
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from jablotronpy import Jablotron, UnauthorizedException

from .const import PLATFORMS, UNSUPPORTED_SERVICES
from .jablotron import JablotronClient
from .types import JablotronServiceData
from .utils import update_unique_id

_LOGGER = logging.getLogger(__name__)

type JablotronConfigEntry = ConfigEntry[JablotronData]


async def async_setup_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:
    """Set up Jablotron Cloud from config entry."""

    _LOGGER.debug("Preparing Jablotron API client")
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    default_pin: str = entry.data[CONF_PIN]
    force_arm: bool = entry.data[CONF_FORCE_UPDATE]
    client = JablotronClient(username, password, default_pin, force_arm)

    _LOGGER.debug("Preparing Jablotron data update coordinator")
    scan_interval: int = entry.data[CONF_SCAN_INTERVAL]
    scan_timeout: int = entry.data[CONF_TIMEOUT]
    coordinator = JablotronDataCoordinator(hass, client, scan_interval, scan_timeout)

    # Prepare runtime data
    entry.runtime_data = JablotronData(client, coordinator)

    # Fetch initial data for platforms initialization
    await coordinator.async_config_entry_first_refresh()

    # Listen for configuration changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Setup all supported platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:
    """Unload Jablotron Cloud integration."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: JablotronConfigEntry) -> None:
    """Handle configuration changes."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: JablotronConfigEntry) -> bool:
    """Handle migration of config entry data."""

    # Get current config version
    version = config_entry.version
    minor_version = config_entry.minor_version

    # Ignore that user downgraded from newer version of integration
    if version > 3:
        return False

    # Modify config entry based on previous version
    _LOGGER.debug("Migrating configuration from version %s.%s", version, minor_version)
    new_data: dict = config_entry.data.copy()
    if version == 2:
        # Add default values for 'force_update', 'scan_interval' and 'timeout'
        new_data[CONF_PIN] = config_entry.data.get(CONF_PIN, "")
        new_data[CONF_FORCE_UPDATE] = True
        new_data[CONF_SCAN_INTERVAL] = 30
        new_data[CONF_TIMEOUT] = 15

        # Migrate existing entities to the new schema
        await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    # Set config entry version to the latest one
    hass.config_entries.async_update_entry(config_entry, data=new_data, minor_version=1, version=3)
    _LOGGER.info("Migrated configuration to version %s.%s", config_entry.version, config_entry.minor_version)

    return True


@dataclass
class JablotronData:
    """Integration runtime data."""

    client: JablotronClient
    coordinator: JablotronDataCoordinator


class JablotronDataCoordinator(DataUpdateCoordinator):
    """Data coordinator for Jablotron Cloud integration."""

    def __init__(self, hass: HomeAssistant, client: JablotronClient, scan_interval: int, scan_timeout: int) -> None:
        """Initialize Home Assistant data update coordinator."""

        # Define coordinator attributes
        self._client = client
        self._scan_timeout = scan_timeout

        # Initialize data update coordinator
        super().__init__(
            hass,
            _LOGGER,
            name="Jablotron Cloud",
            update_interval=timedelta(seconds=scan_interval)
        )

    async def _async_setup(self) -> None:
        """Fetch initial data for all platforms."""

        try:
            # Get available services from Jablotron Cloud
            _LOGGER.debug("Discovering available Jablotron services")
            bridge: Jablotron = await self.hass.async_add_executor_job(self._client.get_bridge)  # noqa
            services = await self.hass.async_add_executor_job(bridge.get_services)  # noqa

            # Log that no services were discovered
            if not services:
                _LOGGER.warning("No services were discovered and therefore no entities will be generated!")

            # Get all available platforms and their states for each service
            for service in services:
                # Get service details
                service_name = service["name"]
                service_id = service["service-id"]
                service_type = service["service-type"]

                # Check whether service type is supported
                if service_type in UNSUPPORTED_SERVICES:
                    _LOGGER.debug("Service '%s' is not supported, ignoring!", service_type)

                    continue

                # Initialize service data
                self._client.services[service_id] = JablotronServiceData(name=service_name, type=service_type)  # noqa

                # Get additional service data
                _LOGGER.debug("Fetching additional data for service '%d'", service_id)
                self._client.services[service_id]["firmware"] = (await self.hass.async_add_executor_job(
                    bridge.get_service_information,
                    service_id
                )).get("device", {}).get("firmware", "N/A")

                # Get available sections from Jablotron Cloud
                _LOGGER.debug("Discovering available sections for service '%d'", service_id)
                self._client.services[service_id]["alarm"] = await self.hass.async_add_executor_job(
                    bridge.get_sections,
                    service_id,
                    service_type
                )

                # Get available gates from Jablotron Cloud
                _LOGGER.debug("Discovering available gates for service '%d'", service_id)
                self._client.services[service_id]["gates"] = await self.hass.async_add_executor_job(
                    bridge.get_programmable_gates,
                    service_id,
                    service_type
                )

                # Get available thermo devices from Jablotron Cloud
                _LOGGER.debug("Discovering available thermo devices for service '%d'", service_id)
                self._client.services[service_id]["thermo"] = await self.hass.async_add_executor_job(
                    bridge.get_thermo_devices,
                    service_id,
                    service_type
                )

                _LOGGER.debug("Successfully discovered available platforms for service '%d'", service_id)
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex

    async def _async_update_data(self) -> None:
        """Update data for all platforms."""

        try:
            # Update data within a certain time limit
            async with timeout(self._scan_timeout):
                # Get fresh Jablotron Cloud session
                _LOGGER.debug("Updating data for available Jablotron services")
                bridge: Jablotron = await self.hass.async_add_executor_job(self._client.get_bridge)  # noqa

                # Update data for all available services
                for service_id in self._client.services:
                    # Get service details
                    service_type = self._client.services[service_id]["type"]

                    # Update sections data from Jablotron Cloud
                    _LOGGER.debug("Updating sections data for service '%d'", service_id)
                    self._client.services[service_id]["alarm"] = await self.hass.async_add_executor_job(
                        bridge.get_sections,
                        service_id,
                        service_type
                    )

                    # Update gates data from Jablotron Cloud
                    _LOGGER.debug("Updating gates data for service '%d'", service_id)
                    self._client.services[service_id]["gates"] = await self.hass.async_add_executor_job(
                        bridge.get_programmable_gates,
                        service_id,
                        service_type
                    )

                    # Update thermo devices data from Jablotron Cloud
                    _LOGGER.debug("Updating thermo devices data for service '%d'", service_id)
                    self._client.services[service_id]["thermo"] = await self.hass.async_add_executor_job(
                        bridge.get_thermo_devices,
                        service_id,
                        service_type
                    )

                    _LOGGER.debug("Successfully updated platforms data for service '%d'", service_id)
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except TimeoutError:
            # Warn that timeout occurred that will cause data to not be up-to-date
            _LOGGER.warning("Timeout while updating data for available services, data may be out of date!")

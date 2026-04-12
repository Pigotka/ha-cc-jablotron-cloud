"""Support for Jablotron thermo device climate controls."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from jablotronpy import UnauthorizedException

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JablotronConfigEntry, JablotronData
from .const import DOMAIN, HVAC_MODE_TO_THERMO_STATE, THERMO_STATE_TO_HVAC_MODE
from .entity import JablotronEntity
from .utils import get_thermo_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register climate entity for each Jablotron service thermo device."""

    runtime_data: JablotronData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    entities: list[JablotronClimate] = []
    for service_id, service_data in client.services.items():
        service_name = service_data["name"]
        service_type = service_data["type"]
        service_firmware = service_data["firmware"]

        thermo_devices = service_data["thermo"]
        for thermo_device in thermo_devices:
            thermo_device_id = thermo_device["object-device-id"]
            thermo_state = thermo_device.get("thermo-device", {})
            state = thermo_device.get("state", {})

            # Skip thermometers (can-control: false)
            if not thermo_state.get("can-control", False):
                continue

            current_temperature = thermo_device.get("temperature")
            target_temperature = state.get("temperature-set")
            heating_mode = state.get("mode", "OFF")
            min_temp = thermo_state.get("temperature-range-min")
            max_temp = thermo_state.get("temperature-range-max")

            entities.append(
                JablotronClimate(
                    coordinator,
                    client,
                    service_id,
                    service_name,
                    service_type,
                    service_firmware,
                    thermo_device_id,
                    current_temperature,
                    target_temperature,
                    heating_mode,
                    min_temp,
                    max_temp,
                )
            )

    async_add_entities(entities)


class JablotronClimate(JablotronEntity, ClimateEntity):
    """Representation of Jablotron Cloud climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _enable_turn_on_off_backwards_compat = False
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        coordinator,
        client,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
        thermo_device_id: str,
        current_temperature: float | None,
        target_temperature: float | None,
        heating_mode: str,
        min_temp: float | None = None,
        max_temp: float | None = None,
    ) -> None:
        """Initialize Jablotron climate entity."""
        self._thermo_device_id = thermo_device_id
        self._attr_name = f"{thermo_device_id}_climate"
        self._attr_unique_id = f"{service_id}_{thermo_device_id}_climate"
        self._attr_current_temperature = current_temperature
        self._attr_target_temperature = target_temperature
        self._attr_hvac_mode = THERMO_STATE_TO_HVAC_MODE.get(heating_mode, HVACMode.OFF)
        self._attr_hvac_action = HVACAction.OFF if self._attr_hvac_mode == HVACMode.OFF else HVACAction.IDLE

        if min_temp is not None:
            self._attr_min_temp = min_temp
        if max_temp is not None:
            self._attr_max_temp = max_temp

        super().__init__(coordinator, client, service_id, service_name, service_type, service_firmware)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        try:
            heating_mode = HVAC_MODE_TO_THERMO_STATE.get(hvac_mode)
            if heating_mode is None:
                _LOGGER.warning("Unsupported HVAC mode: %s", hvac_mode)
                return

            bridge = await self.hass.async_add_executor_job(self._client.get_bridge)

            # When turning on from OFF/STAND_BY, wake the device first before setting the actual mode
            if self._attr_hvac_mode == HVACMode.OFF and hvac_mode != HVACMode.OFF:
                wake_success = await self.hass.async_add_executor_job(
                    partial(
                        bridge.control_thermo_device,
                        service_id=self._service_id,
                        object_device_id=self._thermo_device_id,
                        heating_mode="ON",
                        service_type=self._service_type,
                    )
                )
                if not wake_success:
                    _LOGGER.error("Failed to wake thermo device '%s'", self._thermo_device_id)
                    return

            success = await self.hass.async_add_executor_job(
                partial(
                    bridge.control_thermo_device,
                    service_id=self._service_id,
                    object_device_id=self._thermo_device_id,
                    heating_mode=heating_mode,
                    service_type=self._service_type,
                )
            )

            if success:
                self._attr_hvac_mode = hvac_mode
                self.async_write_ha_state()
            else:
                _LOGGER.error("Failed to set heating mode for device '%s'", self._thermo_device_id)
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except Exception as ex:
            _LOGGER.exception("Failed to control thermo device '%s'", self._thermo_device_id)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_failed",
            ) from ex

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning("No temperature provided for set_temperature")
            return

        try:
            bridge = await self.hass.async_add_executor_job(self._client.get_bridge)
            success = await self.hass.async_add_executor_job(
                partial(
                    bridge.control_thermo_device,
                    service_id=self._service_id,
                    object_device_id=self._thermo_device_id,
                    temperature=temperature,
                    service_type=self._service_type,
                )
            )

            if success:
                self._attr_target_temperature = temperature
                self.async_write_ha_state()
            else:
                _LOGGER.error("Failed to set temperature for device '%s'", self._thermo_device_id)
        except UnauthorizedException as ex:
            raise ConfigEntryAuthFailed(ex) from ex
        except Exception as ex:
            _LOGGER.exception("Failed to set temperature for thermo device '%s'", self._thermo_device_id)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_failed",
            ) from ex

    async def async_turn_on(self) -> None:
        """Turn on heating."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off heating."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data retrieved by coordinator."""
        service = self._client.services.get(self._service_id, None)
        if not service:
            _LOGGER.error("No data available for service '%d'!", self._service_id)
            return

        thermo_devices = service["thermo"]
        if not thermo_devices:
            _LOGGER.warning("No thermo devices available for service '%d'!", self._service_id)
            return

        thermo_device = get_thermo_device(self._thermo_device_id, thermo_devices)
        if not thermo_device:
            _LOGGER.warning("No thermo device found with id '%s'!", self._thermo_device_id)
            return

        self._attr_current_temperature = thermo_device.get("temperature")

        state = thermo_device.get("state", {})
        self._attr_target_temperature = state.get("temperature-set")

        heating_mode = state.get("mode", "OFF")
        self._attr_hvac_mode = THERMO_STATE_TO_HVAC_MODE.get(heating_mode, HVACMode.OFF)

        heating_state = state.get("heating-state", "HEATING_OFF")
        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif heating_state == "HEATING":
            self._attr_hvac_action = HVACAction.HEATING
        else:
            self._attr_hvac_action = HVACAction.IDLE

        self.async_write_ha_state()

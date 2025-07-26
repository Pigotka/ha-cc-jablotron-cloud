"""Config flow for Jablotron Cloud integration."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_FORCE_UPDATE,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT
)
from jablotronpy import UnauthorizedException

from .const import DOMAIN
from .jablotron import JablotronClient

_LOGGER = logging.getLogger(__name__)


def get_schema(config: dict) -> vol.Schema:
    """Return config flow schema."""

    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=config.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_PIN, default=config.get(CONF_PIN, "")): str,
            vol.Optional(CONF_FORCE_UPDATE, default=config.get(CONF_FORCE_UPDATE, True)): bool,
            vol.Optional(CONF_SCAN_INTERVAL, default=config.get(CONF_SCAN_INTERVAL, 30)): int,
            vol.Optional(CONF_TIMEOUT, default=config.get(CONF_TIMEOUT, 15)): int
        }
    )


async def handle_configuration(
    self: ConfigFlow,
    user_input: dict | None,
    step_id: str,
    config_entry_data: dict
) -> ConfigFlowResult | None:
    """Handle configuration from config flows."""

    # Open configuration dialog
    if user_input is None:
        return self.async_show_form(  # type: ignore
            step_id=step_id,
            data_schema=get_schema(config_entry_data)
        )

    # Validate interval value
    if user_input[CONF_SCAN_INTERVAL] < 20:
        return self.async_show_form(  # type: ignore
            step_id=step_id,
            data_schema=get_schema(user_input),
            errors={"base": "interval_too_short"}
        )

    # Validate timeout value
    if user_input[CONF_TIMEOUT] < 10:
        return self.async_show_form(  # type: ignore
            step_id=step_id,
            data_schema=get_schema(user_input),
            errors={"base": "timeout_too_low"}
        )

    try:
        # Validate entered credentials
        _LOGGER.debug("Validating Jablotron Cloud credentials")
        await self.hass.async_add_executor_job(validate_credentials, user_input)
    except UnauthorizedException:
        return self.async_show_form(  # type: ignore
            step_id=step_id,
            data_schema=get_schema(user_input),
            errors={"base": "invalid_auth"}
        )


def validate_credentials(user_input: dict) -> None:
    """Validate that user entered valid credentials."""

    # Initialize Jablotron client and validate entered credentials
    client = JablotronClient(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
    client.get_bridge()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Jablotron Cloud."""

    # Define configuration version
    VERSION = 3
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """User flow to configure Jablotron Cloud integration."""

        # Show configuration dialog and validate user inputs
        flow_result = await handle_configuration(self, user_input, "user", {})

        # Save configuration or reopen configuration dialog
        if flow_result is None:
            _LOGGER.info("Jablotron Cloud integration successfully configured")
            return self.async_create_entry(title="Jablotron Cloud", data=user_input)  # type: ignore
        else:
            return flow_result  # type: ignore

    async def async_step_reconfigure(self, user_input: dict | None = None) -> ConfigFlowResult:
        """User flow to reconfigure Jablotron Cloud integration."""

        # Get existing configuration
        config_entry = self._get_reconfigure_entry()

        # Show configuration dialog and validate user inputs
        flow_result = await handle_configuration(self, user_input, "reconfigure", config_entry.data)

        # Save configuration or reopen configuration dialog
        if flow_result is None:
            _LOGGER.info("Jablotron Cloud integration successfully reconfigured")
            return self.async_update_reload_and_abort(  # type: ignore
                config_entry,
                unique_id=config_entry.unique_id,
                data={**config_entry.data, **user_input}
            )
        else:
            return flow_result  # type: ignore

    async def async_step_reauth(self, entry_data: dict | None = None) -> ConfigFlowResult:  # noqa: F841
        """Handler for API authentication errors."""

        return await self.async_step_reauth_confirm()  # type: ignore

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """User flow to update credentials for Jablotron Cloud integration."""

        # Get existing configuration
        config_entry = self._get_reauth_entry()

        # Show configuration dialog and validate user inputs
        flow_result = await handle_configuration(self, user_input, "reauth_confirm", config_entry.data)

        # Save configuration or reopen configuration dialog
        if flow_result is None:
            _LOGGER.info("Jablotron Cloud integration successfully reconfigured")
            return self.async_update_reload_and_abort(  # type: ignore
                config_entry,
                unique_id=config_entry.unique_id,
                data={**config_entry.data, **user_input}
            )
        else:
            return flow_result  # type: ignore

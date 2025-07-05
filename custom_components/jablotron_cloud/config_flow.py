"""Config flow for Jablotron Cloud integration."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_PIN, CONF_FORCE_UPDATE, CONF_SCAN_INTERVAL, \
    CONF_TIMEOUT
from jablotronpy import UnauthorizedException

from .const import DOMAIN
from .jablotron import JablotronClient

_LOGGER = logging.getLogger(__name__)


def get_schema(
    username: str = "",
    pin: str = "",
    force_arm: bool = True,
    scan_interval: int = 30,
    scan_timeout: int = 15
) -> vol.Schema:
    """Return config flow schema."""

    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_PIN, default=pin): str,
            vol.Optional(CONF_FORCE_UPDATE, default=force_arm): bool,
            vol.Optional(CONF_SCAN_INTERVAL, default=scan_interval): int,
            vol.Optional(CONF_TIMEOUT, default=scan_timeout): int
        }
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

        # Open configuration dialog
        if user_input is None:
            return self.async_show_form(data_schema=get_schema())

        try:
            # Validate entered credentials and reopen dialog if they are not valid
            _LOGGER.debug("Validating Jablotron Cloud credentials")
            await self.hass.async_add_executor_job(validate_credentials, user_input)
        except UnauthorizedException:
            return self.async_show_form(
                data_schema=get_schema(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PIN],
                    user_input[CONF_FORCE_UPDATE],
                    user_input[CONF_SCAN_INTERVAL],
                    user_input[CONF_TIMEOUT]
                ),
                errors={"base": "invalid_auth"}
            )
        else:
            _LOGGER.info("Jablotron Cloud integration successfully configured")
            return self.async_create_entry(title="Jablotron Cloud", data=user_input)

    async def async_step_reconfigure(self, user_input: dict | None = None) -> ConfigFlowResult:
        """User flow to reconfigure Jablotron Cloud integration."""

        # Get existing configuration
        config_entry = self._get_reconfigure_entry()

        # Open reconfiguration dialog
        # noinspection DuplicatedCode
        if user_input is None:
            return self.async_show_form(
                data_schema=get_schema(
                    config_entry.data[CONF_USERNAME],
                    config_entry.data[CONF_PIN],
                    config_entry.data[CONF_FORCE_UPDATE],
                    config_entry.data[CONF_SCAN_INTERVAL],
                    config_entry.data[CONF_TIMEOUT]
                )
            )

        try:
            # Validate entered credentials and reopen dialog if they are not valid
            _LOGGER.debug("Validating Jablotron Cloud credentials")
            await self.hass.async_add_executor_job(validate_credentials, user_input)
        except UnauthorizedException:
            return self.async_show_form(
                data_schema=get_schema(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PIN],
                    user_input[CONF_FORCE_UPDATE],
                    user_input[CONF_SCAN_INTERVAL],
                    user_input[CONF_TIMEOUT]
                ),
                errors={"base": "invalid_auth"}
            )
        else:
            _LOGGER.info("Jablotron Cloud integration successfully reconfigured")
            return self.async_update_reload_and_abort(
                config_entry,
                unique_id=config_entry.unique_id,
                data={**config_entry.data, **user_input}
            )

    async def async_step_reauth(self, entry_data: dict | None = None) -> ConfigFlowResult:  # noqa: F841
        """Handler for API authentication errors."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """User flow to update credentials for Jablotron Cloud integration."""

        # Get existing configuration
        config_entry = self._get_reauth_entry()

        # Open reconfiguration dialog
        # noinspection DuplicatedCode
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=get_schema(
                    config_entry.data[CONF_USERNAME],
                    config_entry.data[CONF_PIN],
                    config_entry.data[CONF_FORCE_UPDATE],
                    config_entry.data[CONF_SCAN_INTERVAL],
                    config_entry.data[CONF_TIMEOUT]
                )
            )

        try:
            # Validate entered credentials and reopen dialog if they are not valid
            _LOGGER.debug("Validating Jablotron Cloud credentials")
            await self.hass.async_add_executor_job(validate_credentials, user_input)
        except UnauthorizedException:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=get_schema(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PIN],
                    user_input[CONF_FORCE_UPDATE],
                    user_input[CONF_SCAN_INTERVAL],
                    user_input[CONF_TIMEOUT]
                ),
                errors={"base": "invalid_auth"}
            )
        else:
            _LOGGER.info("Jablotron Cloud integration successfully reconfigured")
            return self.async_update_reload_and_abort(
                config_entry,
                unique_id=config_entry.unique_id,
                data={**config_entry.data, **user_input}
            )

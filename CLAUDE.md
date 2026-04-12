# Jablotron Cloud - Home Assistant Custom Integration

## Project Overview
Custom HACS integration connecting Jablotron alarm systems to Home Assistant via `jablotronpy` cloud API.
Cloud-polling hub with 5 entity platforms: alarm_control_panel, binary_sensor, climate, sensor, switch.

## Architecture
- `JablotronClient` (jablotron.py) - credential holder, `get_bridge()` creates fresh login each call
- `JablotronDataCoordinator` (__init__.py) - polls API, mutates `client.services` dict in-place; `coordinator.data` is unused (stays None)
- Entities read state from `client.services[service_id]` in `_handle_coordinator_update()`, not from `coordinator.data`
- `can-control` flag splits same data source into read-only vs read-write platforms (binary_sensor/switch, sensor/climate)
- All entities from same Jablotron service share one HA device via `identifiers={(DOMAIN, str(service_id))}`
- No shared entity base class - patterns are copy-pasted across platforms

## Code Style
- Ruff linting matching HA core rules (see pyproject.toml): line length 120, Python 3.12, Google docstrings
- `async_add_executor_job` for blocking jablotronpy calls
- Optimistic state updates after control actions
- Config flow version 3.1; migration from v2 in `async_migrate_entry`

## HA Development Guidelines
These rules come from the Home Assistant developer docs and apply to all code in this integration.

### General Style
- PEP 8 + PEP 257 enforced; Ruff is the formatter
- F-strings for formatting everywhere EXCEPT logging (use `%s` formatting in log calls)
- Comments must be complete sentences ending with a period
- Constants, list contents, and dict contents should be alphabetically ordered
- Fully typed code; use type annotations, not docstring types

### Entity Rules
- `has_entity_name = True` is mandatory for new integrations
- Entity names should use translations, not hardcoded English strings
- Use `_attr_` for static/simple values; use `@property` only when logic is needed
- Properties must NEVER do I/O — only return values from memory
- Never pass `hass` as entity constructor param — access via `self.hass` after init
- Never call `update()` inside entity constructors
- Icon should be set via `icons.json` translation, not `icon` property (unless dynamic)
- Avoid changing `device_class` or `supported_features` after initial creation
- Use `entity_category` CONFIG for config entities, DIAGNOSTIC for read-only diagnostics

### Data Coordinator Rules
- Use `async_config_entry_first_refresh()` during setup for initial data load
- Raise `ConfigEntryAuthFailed` for auth errors (halts updates, triggers reauth)
- Raise `UpdateFailed("message")` for transient API errors (allows retry)
- `asyncio.TimeoutError` and `aiohttp.ClientError` are auto-handled by coordinator
- Minimum polling interval: 5 seconds

### Config Entry Rules
- Never mutate `ConfigEntry` data directly — use `async_update_entry()`
- Forward platform setup via `async_forward_entry_setups(entry, PLATFORMS)`
- Forward unloading via `async_unload_platforms(entry, PLATFORMS)`

### Translations
- All user-facing strings must go through `strings.json` translation system
- Use `[%key:component::domain::section::key%]` references for shared HA strings
- Exception messages use `HomeAssistantError(translation_domain=DOMAIN, translation_key="...")`
- Entity names with `has_entity_name = True` support translation via `translation_key`

### Logging
- Use `_LOGGER = logging.getLogger(__name__)` — platform name is added automatically
- No periods at end of log messages
- Never log secrets (API keys, tokens, passwords, usernames)
- Prefer `_LOGGER.debug` over `_LOGGER.info` for non-user-facing messages
- Use `%s` formatting in log calls (not f-strings) to avoid evaluating suppressed messages

### Dependencies
- All API code must live in a third-party PyPI library (jablotronpy), not in this integration
- Requirements must be pinned to exact versions in manifest.json

## Commands
- `ruff check custom_components/` - lint
- `ruff format custom_components/` - format

## Dependencies
- Runtime: `jablotronpy==0.7.3` (pinned in manifest.json)
- Dev: `homeassistant>=2024.11.0`, `ruff>=0.14.10` (in pyproject.toml)
- No tests exist in this repo

"""Base entity for Jablotron Cloud integration."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JablotronClient, JablotronDataCoordinator
from .const import DOMAIN


class JablotronEntity(CoordinatorEntity[JablotronDataCoordinator]):
    """Base class for Jablotron Cloud entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JablotronDataCoordinator,
        client: JablotronClient,
        service_id: int,
        service_name: str,
        service_type: str,
        service_firmware: str,
    ) -> None:
        """Initialize Jablotron entity."""
        self._client = client
        self._service_id = service_id
        self._service_name = service_name
        self._service_type = service_type
        self._service_firmware = service_firmware
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about device."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._service_id))},
            name=self._service_name,
            manufacturer="Jablotron",
            model=self._service_type,
            sw_version=self._service_firmware,
        )

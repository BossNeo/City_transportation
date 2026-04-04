"""Binary sensor platform for Sofia Live Transport."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import COORDINATOR_KEY, DEFAULT_NAME, DOMAIN
from .transit_data import Departure, Stop

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for all nearby stops."""
    coordinator: DataUpdateCoordinator[dict] = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR_KEY
    ]
    instance_name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)

    entities: list[BinarySensorEntity] = []

    if coordinator.data:
        for stop_id, stop_info in coordinator.data.items():
            stop: Stop = stop_info["stop"]
            entities.append(
                StopHasDelaySensor(
                    coordinator=coordinator,
                    stop_id=stop_id,
                    stop=stop,
                    instance_name=instance_name,
                    entry_id=entry.entry_id,
                )
            )

    async_add_entities(entities, update_before_add=False)


class StopHasDelaySensor(
    CoordinatorEntity[DataUpdateCoordinator[dict]], BinarySensorEntity
):
    """Binary sensor: on when at least one upcoming departure is delayed.

    Uses BinarySensorDeviceClass.PROBLEM so the UI shows it as a warning.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False  # coordinator handles polling

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict],
        stop_id: str,
        stop: Stop,
        instance_name: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._stop = stop

        # Do NOT set self.entity_id – let the registry derive it from name.
        self._attr_unique_id = f"{entry_id}_{stop_id}_has_delay"
        self._attr_name = f"{instance_name} {stop.stop_name} has delay"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_departures(self) -> list[Departure]:
        if self.coordinator.data is None:
            return []
        info = self.coordinator.data.get(self._stop_id)
        if info is None:
            return []
        return info.get("departures", [])

    # ------------------------------------------------------------------
    # Entity properties
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool:
        """Return True if any departure at this stop is currently delayed."""
        return any(d.is_delayed for d in self._get_departures())

    @property
    def icon(self) -> str:
        return "mdi:clock-alert" if self.is_on else "mdi:clock-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        departures = self._get_departures()
        delayed = [d for d in departures if d.is_delayed]
        return {
            "stop_id": self._stop_id,
            "stop_name": self._stop.stop_name,
            "distance_m": self._stop.distance_m,
            "delayed_count": len(delayed),
            "total_departures": len(departures),
            "delayed_lines": [
                {"line": d.line, "delay_label": d.delay_label}
                for d in delayed
            ],
        }

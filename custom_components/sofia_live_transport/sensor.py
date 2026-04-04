"""Sensor platform for Sofia Live Transport."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    COORDINATOR_KEY,
    DEFAULT_NAME,
    DOMAIN,
    VEHICLE_ICONS,
)
from .transit_data import Departure, Stop

_LOGGER = logging.getLogger(__name__)


def _format_next_departure(departures: list[Departure]) -> str:
    """Format the 'next departure' state string in Bulgarian."""
    if not departures:
        return "Няма заминавания"
    dep = departures[0]
    base = f"{dep.line} след {dep.minutes} мин"
    if dep.is_delayed:
        base += f" (зак. {dep.delay_label})"
    return base


def _departure_to_dict(dep: Departure) -> dict[str, Any]:
    """Serialise a Departure dataclass to a plain dict for HA attributes."""
    return {
        "line": dep.line,
        "vehicle_type": dep.vehicle_type,
        "minutes": dep.minutes,
        "arrival_time": dep.arrival_time,
        "destination": dep.destination,
        "delay_seconds": dep.delay_seconds,
        "delay_minutes": dep.delay_minutes,
        "delay_label": dep.delay_label,
        "delay_status": dep.delay_status,
        "is_delayed": dep.is_delayed,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for all nearby stops."""
    coordinator: DataUpdateCoordinator[dict] = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR_KEY
    ]
    instance_name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)

    entities: list[SensorEntity] = []

    if coordinator.data:
        for stop_id, stop_info in coordinator.data.items():
            stop: Stop = stop_info["stop"]
            entities.append(
                StopDeparturesSensor(
                    coordinator=coordinator,
                    stop_id=stop_id,
                    stop=stop,
                    instance_name=instance_name,
                    entry_id=entry.entry_id,
                )
            )
            entities.append(
                StopNextSensor(
                    coordinator=coordinator,
                    stop_id=stop_id,
                    stop=stop,
                    instance_name=instance_name,
                    entry_id=entry.entry_id,
                )
            )

    async_add_entities(entities, update_before_add=False)


class _StopBaseSensor(CoordinatorEntity[DataUpdateCoordinator[dict]], SensorEntity):
    """Base class for per-stop sensors."""

    _attr_should_poll = False  # coordinator handles polling

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict],
        stop_id: str,
        stop: Stop,
        instance_name: str,
        entry_id: str,
        suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._stop = stop
        self._instance_name = instance_name
        self._entry_id = entry_id
        self._suffix = suffix

        # Unique ID is the only thing HA needs; entity_id is derived from name
        # by the entity registry and should NOT be set manually.
        self._attr_unique_id = f"{entry_id}_{stop_id}_{suffix}"
        self._attr_name = f"{instance_name} {stop.stop_name} {suffix}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_stop_info(self) -> dict | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._stop_id)

    def _get_departures(self) -> list[Departure]:
        info = self._get_stop_info()
        if info is None:
            return []
        return info.get("departures", [])

    @property
    def icon(self) -> str:
        departures = self._get_departures()
        if departures:
            vtype = departures[0].vehicle_type
            return VEHICLE_ICONS.get(vtype, VEHICLE_ICONS["default"])
        return VEHICLE_ICONS["default"]


class StopDeparturesSensor(_StopBaseSensor):
    """Sensor showing all upcoming departures for a stop.

    State : "<N> заминавания"
    Attrs : stop_id, stop_name, distance_m, departures[]
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict],
        stop_id: str,
        stop: Stop,
        instance_name: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, stop_id, stop, instance_name, entry_id, "departures")

    @property
    def native_value(self) -> str:
        departures = self._get_departures()
        return f"{len(departures)} заминавания"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._get_stop_info()
        stop: Stop = info["stop"] if info else self._stop
        departures = self._get_departures()
        return {
            "stop_id": stop.stop_id,
            "stop_name": stop.stop_name,
            "distance_m": stop.distance_m,
            "departures": [_departure_to_dict(d) for d in departures],
        }


class StopNextSensor(_StopBaseSensor):
    """Sensor showing the next departure for a stop.

    State : "204 след 5 мин"  or  "204 след 5 мин (зак. +3 мин)"
    Attrs : stop_id, stop_name, distance_m, + full departure fields
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict],
        stop_id: str,
        stop: Stop,
        instance_name: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, stop_id, stop, instance_name, entry_id, "next")

    @property
    def native_value(self) -> str:
        return _format_next_departure(self._get_departures())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._get_stop_info()
        stop: Stop = info["stop"] if info else self._stop
        departures = self._get_departures()

        attrs: dict[str, Any] = {
            "stop_id": stop.stop_id,
            "stop_name": stop.stop_name,
            "distance_m": stop.distance_m,
        }
        if departures:
            attrs.update(_departure_to_dict(departures[0]))
        return attrs

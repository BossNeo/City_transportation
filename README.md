from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_PROVIDER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_LIMIT,
    CONF_TIME_WINDOW,
    CONF_REFRESH,
    CONF_VEHICLE_TYPES,
)
from .transit_data import TransitFeed

_LOGGER = logging.getLogger(__name__)

ICON_MAP = {
    "bus": "mdi:bus",
    "tram": "mdi:tram",
    "trolleybus": "mdi:bus-electric",
    "subway": "mdi:subway",
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = {**entry.data, **entry.options}
    provider = data[CONF_PROVIDER]
    feed = TransitFeed(provider)

    async def _async_update():
        return await hass.async_add_executor_job(_collect_data, feed, data)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=_async_update,
        update_interval=timedelta(seconds=int(data.get(CONF_REFRESH, 60))),
    )
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for stop_item in coordinator.data["stops"]:
        sensors.append(StopDeparturesSensor(coordinator, entry, stop_item, data))
        sensors.append(StopNextDepartureSensor(coordinator, entry, stop_item, data))
    async_add_entities(sensors)

def _collect_data(feed: TransitFeed, data: dict):
    lat = float(data[CONF_LATITUDE])
    lon = float(data[CONF_LONGITUDE])
    radius = int(data[CONF_RADIUS])
    limit = int(data[CONF_LIMIT])
    time_window = int(data[CONF_TIME_WINDOW])
    vehicle_types = set(data.get(CONF_VEHICLE_TYPES, []))
    nearby = feed.find_stops_in_radius(lat, lon, radius)
    stop_ids = [sid for sid, _dist in nearby]
    departures_map = feed.get_departures_by_stop(stop_ids, vehicle_types=vehicle_types, time_window_min=time_window)
    stops = []
    for sid, dist in nearby:
        stop = feed.stops[sid]
        departures = departures_map.get(sid, [])[:limit]
        stops.append({
            "stop_id": sid,
            "stop_name": stop.stop_name,
            "distance_m": round(dist),
            "departures": departures,
        })
    return {"stops": stops}

class BaseStopSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, stop_item, data):
        super().__init__(coordinator)
        self._entry = entry
        self._stop_id = stop_item["stop_id"]
        self._stop_name = stop_item["stop_name"]
        self._distance_m = stop_item["distance_m"]
        self._base_name = data[CONF_NAME]
        self._attr_has_entity_name = True

    def _stop_payload(self):
        for item in self.coordinator.data.get("stops", []):
            if item["stop_id"] == self._stop_id:
                return item
        return None

class StopDeparturesSensor(BaseStopSensor):
    def __init__(self, coordinator, entry, stop_item, data):
        super().__init__(coordinator, entry, stop_item, data)
        slug = self._stop_name.lower().replace(" ", "_").replace("/", "_")
        self._attr_unique_id = f"{entry.entry_id}_{self._stop_id}_departures"
        self._attr_name = f"{self._base_name} {self._stop_name} departures"
        self.entity_id = f"sensor.{DOMAIN}_{slug}_departures"

    @property
    def native_value(self):
        stop = self._stop_payload()
        deps = stop["departures"] if stop else []
        if deps:
            return f"{deps[0]['line']} след {deps[0]['minutes']} мин"
        return "Няма прогноза"

    @property
    def icon(self):
        stop = self._stop_payload()
        deps = stop["departures"] if stop else []
        if deps:
            return ICON_MAP.get(deps[0].get("vehicle_type"), "mdi:bus-clock")
        return "mdi:bus-stop"

    @property
    def extra_state_attributes(self):
        stop = self._stop_payload()
        deps = stop["departures"] if stop else []
        return {
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "distance_m": self._distance_m,
            "departures": deps,
            "departure_count": len(deps),
        }

class StopNextDepartureSensor(BaseStopSensor):
    def __init__(self, coordinator, entry, stop_item, data):
        super().__init__(coordinator, entry, stop_item, data)
        slug = self._stop_name.lower().replace(" ", "_").replace("/", "_")
        self._attr_unique_id = f"{entry.entry_id}_{self._stop_id}_next"
        self._attr_name = f"{self._base_name} {self._stop_name} next"
        self.entity_id = f"sensor.{DOMAIN}_{slug}_next"

    @property
    def native_value(self):
        stop = self._stop_payload()
        deps = stop["departures"] if stop else []
        return deps[0]["minutes"] if deps else None

    @property
    def native_unit_of_measurement(self):
        return "min"

    @property
    def icon(self):
        stop = self._stop_payload()
        deps = stop["departures"] if stop else []
        if deps:
            return ICON_MAP.get(deps[0].get("vehicle_type"), "mdi:bus-clock")
        return "mdi:bus-stop"

    @property
    def extra_state_attributes(self):
        stop = self._stop_payload()
        deps = stop["departures"] if stop else []
        first = deps[0] if deps else {}
        return {
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "distance_m": self._distance_m,
            "next_line": first.get("line"),
            "next_vehicle_type": first.get("vehicle_type"),
            "next_arrival_local": first.get("arrival_local"),
            "next_destination": first.get("destination"),
            "departures": deps,
        }

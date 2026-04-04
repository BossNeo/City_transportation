"""Sofia Live Transport integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_RADIUS,
    CONF_REFRESH_INTERVAL,
    CONF_TIME_WINDOW,
    CONF_VEHICLE_TYPES,
    COORDINATOR_KEY,
    DEFAULT_RADIUS,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_TIME_WINDOW,
    DEFAULT_VEHICLE_TYPES,
    DOMAIN,
    GTFS_REALTIME_URL,
    GTFS_STATIC_URL,
)
from .transit_data import (
    GTFSRealtimeLoader,
    GTFSStaticLoader,
    build_stop_departures,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sofia Live Transport from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)

    static_loader = GTFSStaticLoader(url=GTFS_STATIC_URL, session=session)
    rt_loader = GTFSRealtimeLoader(url=GTFS_REALTIME_URL, session=session)

    refresh_interval: int = entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
    time_window: int = entry.data.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)
    radius: int = entry.data.get(CONF_RADIUS, DEFAULT_RADIUS)
    center_lat: float = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    center_lon: float = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    vehicle_types_raw: str = entry.data.get(CONF_VEHICLE_TYPES, DEFAULT_VEHICLE_TYPES)
    allowed_vehicle_types: list[str] = [
        v.strip() for v in vehicle_types_raw.split(",") if v.strip()
    ]

    async def _async_update_data() -> dict:
        """Fetch static (cached 24h) + RT data, then compute per-stop departures."""
        try:
            static = await static_loader.get()
            delays = await rt_loader.get_delays()
            return await build_stop_departures(
                static=static,
                delays=delays,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_m=radius,
                time_window_min=time_window,
                allowed_vehicle_types=allowed_vehicle_types,
            )
        except Exception as exc:
            raise UpdateFailed(f"Error updating Sofia transport data: {exc}") from exc

    coordinator: DataUpdateCoordinator[dict] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=refresh_interval),
    )

    # Raises ConfigEntryNotReady on first failure so HA will retry.
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR_KEY: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

"""Constants for Sofia Live Transport integration."""

DOMAIN = "sofia_live_transport"

# Data source URLs
GTFS_STATIC_URL = "https://gtfs.sofiatraffic.bg/api/v1/static"
GTFS_REALTIME_URL = "https://gtfs.sofiatraffic.bg/api/v1/trip-updates"

# Cache
STATIC_CACHE_TTL_SECONDS = 86400  # 24 hours

# Integration-specific config keys (lat/lon/name come from homeassistant.const)
CONF_RADIUS = "radius"
CONF_TIME_WINDOW = "time_window"
CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_VEHICLE_TYPES = "vehicle_types"

# Defaults
DEFAULT_NAME = "Sofia Transport"
DEFAULT_RADIUS = 150
DEFAULT_TIME_WINDOW = 30
DEFAULT_REFRESH_INTERVAL = 60
DEFAULT_VEHICLE_TYPES = "bus,tram,trolleybus,subway"

# Vehicle types
VEHICLE_TYPE_BUS = "bus"
VEHICLE_TYPE_TRAM = "tram"
VEHICLE_TYPE_TROLLEYBUS = "trolleybus"
VEHICLE_TYPE_SUBWAY = "subway"

VALID_VEHICLE_TYPES = {
    VEHICLE_TYPE_BUS,
    VEHICLE_TYPE_TRAM,
    VEHICLE_TYPE_TROLLEYBUS,
    VEHICLE_TYPE_SUBWAY,
}

# GTFS route_type -> vehicle_type mapping
# https://developers.google.com/transit/gtfs/reference#routestxt
ROUTE_TYPE_MAP = {
    0: VEHICLE_TYPE_TRAM,       # Tram, Streetcar, Light rail
    1: VEHICLE_TYPE_SUBWAY,     # Subway, Metro
    2: "rail",                  # Rail
    3: VEHICLE_TYPE_BUS,        # Bus
    4: "ferry",
    5: VEHICLE_TYPE_TROLLEYBUS, # Cable tram / trolleybus (Sofia uses 11)
    6: "aerial",
    7: "funicular",
    11: VEHICLE_TYPE_TROLLEYBUS,  # Trolleybus
    12: "monorail",
    800: VEHICLE_TYPE_TROLLEYBUS,
    900: VEHICLE_TYPE_TRAM,
}

# Icons per vehicle type
VEHICLE_ICONS = {
    VEHICLE_TYPE_BUS: "mdi:bus",
    VEHICLE_TYPE_TRAM: "mdi:tram",
    VEHICLE_TYPE_TROLLEYBUS: "mdi:bus-electric",
    VEHICLE_TYPE_SUBWAY: "mdi:subway",
    "default": "mdi:transit-connection-variant",
}

# Delay status labels
DELAY_LATE = "late"
DELAY_EARLY = "early"
DELAY_ON_TIME = "on_time"

# Threshold in seconds to consider "on time"
DELAY_THRESHOLD_SECONDS = 60

# Coordinator update key
COORDINATOR_KEY = "coordinator"

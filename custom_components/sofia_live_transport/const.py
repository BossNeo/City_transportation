DOMAIN = "sofia_live_transport"

CONF_NAME = "name"
CONF_PROVIDER = "provider"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS = "radius_m"
CONF_LIMIT = "limit"
CONF_TIME_WINDOW = "time_window_min"
CONF_REFRESH = "refresh_interval"
CONF_VEHICLE_TYPES = "vehicle_types"

DEFAULT_NAME = "Transit"
DEFAULT_PROVIDER = "sofia"
DEFAULT_RADIUS = 150
DEFAULT_LIMIT = 5
DEFAULT_TIME_WINDOW = 30
DEFAULT_REFRESH = 60

PROVIDER_SOFIA = "sofia"

CENTER_POINTS = {
    "sofia": (42.6977, 23.3219),
}

PROVIDERS = {
    "sofia": {
        "title": "Sofia",
        "static_url": "https://gtfs.sofiatraffic.bg/api/v1/static",
        "trip_updates_url": "https://gtfs.sofiatraffic.bg/api/v1/trip-updates",
    }
}

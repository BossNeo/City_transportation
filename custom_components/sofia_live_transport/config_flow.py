from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

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
    DEFAULT_NAME,
    DEFAULT_PROVIDER,
    DEFAULT_RADIUS,
    DEFAULT_LIMIT,
    DEFAULT_TIME_WINDOW,
    DEFAULT_REFRESH,
    PROVIDERS,
)


class SofiaLiveTransportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            user_input = dict(user_input)
            if isinstance(user_input.get(CONF_VEHICLE_TYPES), str):
                user_input[CONF_VEHICLE_TYPES] = [
                    x.strip() for x in user_input[CONF_VEHICLE_TYPES].split(",") if x.strip()
                ]

            try:
                user_input[CONF_LATITUDE] = float(user_input[CONF_LATITUDE])
                user_input[CONF_LONGITUDE] = float(user_input[CONF_LONGITUDE])
                user_input[CONF_RADIUS] = int(user_input[CONF_RADIUS])
                user_input[CONF_LIMIT] = int(user_input[CONF_LIMIT])
                user_input[CONF_TIME_WINDOW] = int(user_input[CONF_TIME_WINDOW])
                user_input[CONF_REFRESH] = int(user_input[CONF_REFRESH])
            except (TypeError, ValueError):
                errors["base"] = "invalid_input"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_PROVIDER]}_{round(user_input[CONF_LATITUDE], 5)}_{round(user_input[CONF_LONGITUDE], 5)}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        lat = self.hass.config.latitude
        lon = self.hass.config.longitude

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_PROVIDER, default=DEFAULT_PROVIDER): vol.In(list(PROVIDERS.keys())),
                vol.Required(CONF_LATITUDE, default=lat): vol.Coerce(float),
                vol.Required(CONF_LONGITUDE, default=lon): vol.Coerce(float),
                vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS): vol.All(vol.Coerce(int), vol.Range(min=50, max=1500)),
                vol.Required(CONF_LIMIT, default=DEFAULT_LIMIT): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Required(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                vol.Required(CONF_REFRESH, default=DEFAULT_REFRESH): vol.All(vol.Coerce(int), vol.Range(min=15, max=300)),
                vol.Required(CONF_VEHICLE_TYPES, default="bus,tram,trolleybus"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SofiaLiveTransportOptionsFlow(config_entry)


class SofiaLiveTransportOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            user_input = dict(user_input)
            if isinstance(user_input.get(CONF_VEHICLE_TYPES), str):
                user_input[CONF_VEHICLE_TYPES] = [
                    x.strip() for x in user_input[CONF_VEHICLE_TYPES].split(",") if x.strip()
                ]
            return self.async_create_entry(title="", data=user_input)

        data = {**self.config_entry.data, **self.config_entry.options}
        vehicle_types = data.get(CONF_VEHICLE_TYPES, ["bus", "tram", "trolleybus"])
        if isinstance(vehicle_types, list):
            vehicle_types = ",".join(vehicle_types)

        schema = vol.Schema(
            {
                vol.Required(CONF_RADIUS, default=data.get(CONF_RADIUS, DEFAULT_RADIUS)): vol.All(vol.Coerce(int), vol.Range(min=50, max=1500)),
                vol.Required(CONF_LIMIT, default=data.get(CONF_LIMIT, DEFAULT_LIMIT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Required(CONF_TIME_WINDOW, default=data.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                vol.Required(CONF_REFRESH, default=data.get(CONF_REFRESH, DEFAULT_REFRESH)): vol.All(vol.Coerce(int), vol.Range(min=15, max=300)),
                vol.Required(CONF_VEHICLE_TYPES, default=vehicle_types): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

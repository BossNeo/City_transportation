from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

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

VEHICLE_OPTIONS = ["bus", "tram", "trolleybus", "subway"]

class SofiaLiveTransportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_PROVIDER]}_{round(user_input[CONF_LATITUDE], 5)}_{round(user_input[CONF_LONGITUDE], 5)}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        lat = self.hass.config.latitude
        lon = self.hass.config.longitude

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
            vol.Required(CONF_PROVIDER, default=DEFAULT_PROVIDER): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v["title"]} for k, v in PROVIDERS.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_LATITUDE, default=lat): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-90, max=90, step=0.000001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LONGITUDE, default=lon): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-180, max=180, step=0.000001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS): selector.NumberSelector(
                selector.NumberSelectorConfig(min=50, max=1500, step=10, unit_of_measurement="m", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LIMIT, default=DEFAULT_LIMIT): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_REFRESH, default=DEFAULT_REFRESH): selector.NumberSelector(
                selector.NumberSelectorConfig(min=15, max=300, step=5, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_VEHICLE_TYPES, default=["bus", "tram", "trolleybus"]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=VEHICLE_OPTIONS,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
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
            return self.async_create_entry(title="", data=user_input)

        data = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema({
            vol.Required(CONF_RADIUS, default=data.get(CONF_RADIUS, DEFAULT_RADIUS)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=50, max=1500, step=10, unit_of_measurement="m", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LIMIT, default=data.get(CONF_LIMIT, DEFAULT_LIMIT)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_TIME_WINDOW, default=data.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_REFRESH, default=data.get(CONF_REFRESH, DEFAULT_REFRESH)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=15, max=300, step=5, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_VEHICLE_TYPES, default=data.get(CONF_VEHICLE_TYPES, ["bus", "tram", "trolleybus"])): selector.SelectSelector(
                selector.SelectSelectorConfig(options=VEHICLE_OPTIONS, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
        })
        return self.async_show_form(step_id="init", data_schema=schema)

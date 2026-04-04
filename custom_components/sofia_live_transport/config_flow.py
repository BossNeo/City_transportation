"""Config flow for Sofia Live Transport integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_RADIUS,
    CONF_REFRESH_INTERVAL,
    CONF_TIME_WINDOW,
    CONF_VEHICLE_TYPES,
    DEFAULT_NAME,
    DEFAULT_RADIUS,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_TIME_WINDOW,
    DEFAULT_VEHICLE_TYPES,
    DOMAIN,
    VALID_VEHICLE_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def _parse_vehicle_types(raw: str) -> list[str]:
    """Parse and validate a comma-separated vehicle types string.

    Returns a sorted list of unique valid types.
    Raises vol.Invalid if any token is unrecognised or the list is empty.
    """
    types = [t.strip().lower() for t in raw.split(",") if t.strip()]
    invalid = [t for t in types if t not in VALID_VEHICLE_TYPES]
    if invalid:
        raise vol.Invalid(
            f"Невалиден тип превозно средство: {', '.join(invalid)}. "
            f"Допустими стойности: {', '.join(sorted(VALID_VEHICLE_TYPES))}"
        )
    if not types:
        raise vol.Invalid("Трябва да посочите поне един тип превозно средство.")
    return list(dict.fromkeys(types))  # deduplicate while preserving order


def _build_schema(
    hass: HomeAssistant,
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the voluptuous config schema, pre-filled with *defaults*."""
    d = defaults or {}
    home_lat: float = hass.config.latitude
    home_lon: float = hass.config.longitude

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(
                CONF_LATITUDE,
                default=d.get(CONF_LATITUDE, home_lat),
            ): vol.Coerce(float),
            vol.Required(
                CONF_LONGITUDE,
                default=d.get(CONF_LONGITUDE, home_lon),
            ): vol.Coerce(float),
            vol.Required(
                CONF_RADIUS,
                default=d.get(CONF_RADIUS, DEFAULT_RADIUS),
            ): vol.All(vol.Coerce(int), vol.Range(min=50, max=2000)),
            vol.Required(
                CONF_TIME_WINDOW,
                default=d.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
            vol.Required(
                CONF_REFRESH_INTERVAL,
                default=d.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=15, max=600)),
            vol.Required(
                CONF_VEHICLE_TYPES,
                default=d.get(CONF_VEHICLE_TYPES, DEFAULT_VEHICLE_TYPES),
            ): str,
        }
    )


def _validate_user_input(
    user_input: dict[str, Any],
) -> tuple[dict[str, str], list[str]]:
    """Validate user input and return (errors, parsed_vehicle_types)."""
    errors: dict[str, str] = {}
    parsed_types: list[str] = []
    try:
        parsed_types = _parse_vehicle_types(user_input.get(CONF_VEHICLE_TYPES, ""))
    except vol.Invalid as exc:
        errors[CONF_VEHICLE_TYPES] = str(exc)
    return errors, parsed_types


class SofiaLiveTransportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sofia Live Transport."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step shown to the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errs, parsed_types = _validate_user_input(user_input)
            errors.update(errs)

            if not errors:
                data = dict(user_input)
                data[CONF_VEHICLE_TYPES] = ",".join(parsed_types)

                # Unique ID prevents duplicate entries for same location + name
                unique_id = (
                    f"{data[CONF_NAME].lower().replace(' ', '_')}"
                    f"_{data[CONF_LATITUDE]:.5f}"
                    f"_{data[CONF_LONGITUDE]:.5f}"
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=data[CONF_NAME], data=data)

        schema = _build_schema(self.hass, user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "vehicle_types_hint": ", ".join(sorted(VALID_VEHICLE_TYPES))
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SofiaLiveTransportOptionsFlow:
        """Return the options flow handler."""
        return SofiaLiveTransportOptionsFlow()


class SofiaLiveTransportOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Sofia Live Transport.

    In HA 2024+, OptionsFlow receives config_entry via self.config_entry
    (set by the framework); do NOT pass it to __init__.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the integration options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errs, parsed_types = _validate_user_input(user_input)
            errors.update(errs)

            if not errors:
                data = dict(user_input)
                data[CONF_VEHICLE_TYPES] = ",".join(parsed_types)
                # Persist changed values back to the config entry data and
                # trigger a reload via the update listener in __init__.py.
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                return self.async_create_entry(title="", data={})

        # Pre-fill with current values
        current = dict(self.config_entry.data)
        schema = _build_schema(self.hass, current)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "vehicle_types_hint": ", ".join(sorted(VALID_VEHICLE_TYPES))
            },
        )

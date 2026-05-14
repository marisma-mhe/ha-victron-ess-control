from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_CHARGE_EFFICIENCY,
    CONF_CONSUMER_SERIAL,
    CONF_GRID_SERIAL,
    DOMAIN,
)

_SERIAL_RE = re.compile(r"^[0-9a-f]{6,16}$", re.IGNORECASE)

_STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GRID_SERIAL): str,
        vol.Optional(CONF_CONSUMER_SERIAL, default=""): str,
        vol.Required(CONF_BATTERY_CAPACITY, default=10.0): vol.Coerce(float),
        vol.Required(CONF_CHARGE_EFFICIENCY, default=0.95): vol.All(
            vol.Coerce(float), vol.Range(min=0.80, max=1.00)
        ),
    }
)


def _validate_serial(value: str) -> bool:
    return bool(_SERIAL_RE.match(value.strip()))


def _check_packages_enabled(hass: HomeAssistant) -> bool:
    packages_dir = Path(hass.config.config_dir) / "packages"
    return packages_dir.is_dir()


async def _check_victron_mqtt(hass: HomeAssistant) -> str | None:
    """Return error key if victron_mqtt is not ready, else None."""
    if "victron_mqtt" not in hass.config.components:
        return "victron_mqtt_missing"
    if not hass.config_entries.async_entries("victron_mqtt"):
        return "victron_mqtt_not_configured"
    return None


class VictronEssControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            grid_serial = user_input[CONF_GRID_SERIAL].strip().lower()
            consumer_serial = user_input.get(CONF_CONSUMER_SERIAL, "").strip().lower()

            if not _validate_serial(grid_serial):
                errors[CONF_GRID_SERIAL] = "invalid_serial"
            elif consumer_serial and not _validate_serial(consumer_serial):
                errors[CONF_CONSUMER_SERIAL] = "invalid_serial"

            if not errors:
                error = await _check_victron_mqtt(self.hass)
                if error:
                    errors["base"] = error

            if not errors and not await self.hass.async_add_executor_job(
                _check_packages_enabled, self.hass
            ):
                errors["base"] = "packages_not_enabled"

            if not errors:
                if not consumer_serial:
                    consumer_serial = grid_serial

                data = {
                    CONF_GRID_SERIAL: grid_serial,
                    CONF_CONSUMER_SERIAL: consumer_serial,
                    CONF_BATTERY_CAPACITY: user_input[CONF_BATTERY_CAPACITY],
                    CONF_CHARGE_EFFICIENCY: user_input[CONF_CHARGE_EFFICIENCY],
                }
                return self.async_create_entry(title="Victron ESS Control", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_SCHEMA,
            errors=errors,
            description_placeholders={
                "victron_mqtt_name": "ha-victron-mqtt",
                "victron_mqtt_url": "https://github.com/tomer-w/ha-victron-mqtt",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> VictronEssOptionsFlow:
        return VictronEssOptionsFlow(config_entry)


class VictronEssOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            grid_serial = user_input[CONF_GRID_SERIAL].strip().lower()
            consumer_serial = user_input.get(CONF_CONSUMER_SERIAL, "").strip().lower()

            if not _validate_serial(grid_serial):
                errors[CONF_GRID_SERIAL] = "invalid_serial"
            elif consumer_serial and not _validate_serial(consumer_serial):
                errors[CONF_CONSUMER_SERIAL] = "invalid_serial"

            if not errors:
                if not consumer_serial:
                    consumer_serial = grid_serial
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_GRID_SERIAL: grid_serial,
                        CONF_CONSUMER_SERIAL: consumer_serial,
                        CONF_BATTERY_CAPACITY: user_input[CONF_BATTERY_CAPACITY],
                        CONF_CHARGE_EFFICIENCY: user_input[CONF_CHARGE_EFFICIENCY],
                    },
                )

        current = self._entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GRID_SERIAL,
                    default=current.get(CONF_GRID_SERIAL, ""),
                ): str,
                vol.Optional(
                    CONF_CONSUMER_SERIAL,
                    default=current.get(CONF_CONSUMER_SERIAL, ""),
                ): str,
                vol.Required(
                    CONF_BATTERY_CAPACITY,
                    default=current.get(CONF_BATTERY_CAPACITY, 10.0),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_CHARGE_EFFICIENCY,
                    default=current.get(CONF_CHARGE_EFFICIENCY, 0.95),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.80, max=1.00)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

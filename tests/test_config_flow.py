"""Tests for VictronEssControlConfigFlow and VictronEssOptionsFlow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.victron_ess_control.const import (
    CONF_BATTERY_CAPACITY,
    CONF_CHARGE_EFFICIENCY,
    CONF_CONSUMER_SERIAL,
    CONF_GRID_SERIAL,
    DOMAIN,
)

VALID_GRID_SERIAL = "c0619ab4eec9"
VALID_CONSUMER_SERIAL = "c0619ab2288d"

VALID_INPUT = {
    CONF_GRID_SERIAL: VALID_GRID_SERIAL,
    CONF_CONSUMER_SERIAL: VALID_CONSUMER_SERIAL,
    CONF_BATTERY_CAPACITY: 10.0,
    CONF_CHARGE_EFFICIENCY: 0.95,
}


def _mock_victron_mqtt_ok(hass: HomeAssistant) -> None:
    hass.config.components.add("victron_mqtt")
    mock_entry = MagicMock()
    mock_entry.domain = "victron_mqtt"
    hass.config_entries._entries["victron_mqtt_fake"] = mock_entry


@pytest.fixture(autouse=True)
def _packages_dir_exists(tmp_path, hass):
    """Create packages dir so _check_packages_enabled passes."""
    pkg_dir = tmp_path / "packages"
    pkg_dir.mkdir()
    hass.config.config_dir = str(tmp_path)


# ── Config Flow ──────────────────────────────────────────────────────────────


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_invalid_grid_serial(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**VALID_INPUT, CONF_GRID_SERIAL: "not-a-hex-serial!!"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_GRID_SERIAL] == "invalid_serial"


async def test_user_step_invalid_consumer_serial(hass: HomeAssistant) -> None:
    _mock_victron_mqtt_ok(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**VALID_INPUT, CONF_CONSUMER_SERIAL: "BAD!"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_CONSUMER_SERIAL] == "invalid_serial"


async def test_user_step_victron_mqtt_missing(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "victron_mqtt_missing"


async def test_user_step_victron_mqtt_not_configured(hass: HomeAssistant) -> None:
    hass.config.components.add("victron_mqtt")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "victron_mqtt_not_configured"


async def test_user_step_packages_not_enabled(hass: HomeAssistant, tmp_path) -> None:
    _mock_victron_mqtt_ok(hass)
    (tmp_path / "packages").rmdir()  # remove the dir created by autouse fixture

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "packages_not_enabled"


async def test_user_step_success_dual_system(hass: HomeAssistant) -> None:
    _mock_victron_mqtt_ok(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_INPUT
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Victron ESS Control"
    data = result["data"]
    assert data[CONF_GRID_SERIAL] == VALID_GRID_SERIAL
    assert data[CONF_CONSUMER_SERIAL] == VALID_CONSUMER_SERIAL
    assert data[CONF_BATTERY_CAPACITY] == 10.0
    assert data[CONF_CHARGE_EFFICIENCY] == 0.95


async def test_user_step_success_single_system_consumer_defaults_to_grid(
    hass: HomeAssistant,
) -> None:
    _mock_victron_mqtt_ok(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**VALID_INPUT, CONF_CONSUMER_SERIAL: ""},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data[CONF_CONSUMER_SERIAL] == VALID_GRID_SERIAL


async def test_user_step_serial_normalized_to_lowercase(hass: HomeAssistant) -> None:
    _mock_victron_mqtt_ok(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**VALID_INPUT, CONF_GRID_SERIAL: "C0619AB4EEC9"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GRID_SERIAL] == "c0619ab4eec9"


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    _mock_victron_mqtt_ok(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], VALID_INPUT)

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


# ── Options Flow ─────────────────────────────────────────────────────────────


async def test_options_flow_shows_form_with_current_values(
    hass: HomeAssistant,
) -> None:
    _mock_victron_mqtt_ok(hass)
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Victron ESS Control",
        data={
            CONF_GRID_SERIAL: VALID_GRID_SERIAL,
            CONF_CONSUMER_SERIAL: VALID_CONSUMER_SERIAL,
            CONF_BATTERY_CAPACITY: 15.0,
            CONF_CHARGE_EFFICIENCY: 0.92,
        },
        source=config_entries.SOURCE_USER,
        options={},
    )
    entry._hass = hass
    hass.config_entries._entries[entry.entry_id] = entry

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert CONF_GRID_SERIAL in schema_keys
    assert CONF_BATTERY_CAPACITY in schema_keys


async def test_options_flow_invalid_serial(hass: HomeAssistant) -> None:
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Victron ESS Control",
        data={
            CONF_GRID_SERIAL: VALID_GRID_SERIAL,
            CONF_CONSUMER_SERIAL: VALID_CONSUMER_SERIAL,
            CONF_BATTERY_CAPACITY: 10.0,
            CONF_CHARGE_EFFICIENCY: 0.95,
        },
        source=config_entries.SOURCE_USER,
        options={},
    )
    entry._hass = hass
    hass.config_entries._entries[entry.entry_id] = entry

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**VALID_INPUT, CONF_GRID_SERIAL: "!!!"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_GRID_SERIAL] == "invalid_serial"


async def test_options_flow_success(hass: HomeAssistant) -> None:
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Victron ESS Control",
        data={
            CONF_GRID_SERIAL: VALID_GRID_SERIAL,
            CONF_CONSUMER_SERIAL: VALID_CONSUMER_SERIAL,
            CONF_BATTERY_CAPACITY: 10.0,
            CONF_CHARGE_EFFICIENCY: 0.95,
        },
        source=config_entries.SOURCE_USER,
        options={},
    )
    entry._hass = hass
    hass.config_entries._entries[entry.entry_id] = entry

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_GRID_SERIAL: VALID_GRID_SERIAL,
            CONF_CONSUMER_SERIAL: "",  # empty → defaults to grid serial
            CONF_BATTERY_CAPACITY: 20.0,
            CONF_CHARGE_EFFICIENCY: 0.90,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BATTERY_CAPACITY] == 20.0
    assert result["data"][CONF_CONSUMER_SERIAL] == VALID_GRID_SERIAL


# ── _validate_serial unit tests ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "serial,expected",
    [
        ("c0619ab4eec9", True),
        ("C0619AB4EEC9", True),
        ("abcdef", True),
        ("1234567890abcdef", True),
        ("12345", False),  # too short (5 chars)
        ("12345678901234567", False),  # too long (17 chars)
        ("xyz!@#", False),
        ("", False),
        ("  c0619ab4eec9  ", True),  # strip handled by caller
    ],
)
def test_validate_serial(serial: str, expected: bool) -> None:
    from custom_components.victron_ess_control.config_flow import _validate_serial

    assert _validate_serial(serial.strip()) == expected

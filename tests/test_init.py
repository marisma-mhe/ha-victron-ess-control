"""Tests for custom_components.victron_ess_control.__init__."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.victron_ess_control import (
    _deploy_dashboards,
    _deploy_package,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.victron_ess_control.const import (
    CONF_BATTERY_CAPACITY,
    CONF_CHARGE_EFFICIENCY,
    CONF_CONSUMER_SERIAL,
    CONF_GRID_SERIAL,
    DOMAIN,
)

VALID_GRID_SERIAL = "c0619ab4eec9"
VALID_CONSUMER_SERIAL = "c0619ab2288d"

ENTRY_DATA = {
    CONF_GRID_SERIAL: VALID_GRID_SERIAL,
    CONF_CONSUMER_SERIAL: VALID_CONSUMER_SERIAL,
    CONF_BATTERY_CAPACITY: 10.0,
    CONF_CHARGE_EFFICIENCY: 0.95,
}


def _make_entry(hass: HomeAssistant, data=None, options=None):
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Victron ESS Control",
        data=data or ENTRY_DATA,
        source=config_entries.SOURCE_USER,
        options=options or {},
    )
    entry._hass = hass
    hass.config_entries._entries[entry.entry_id] = entry
    return entry


def _mock_victron_mqtt_ok(hass: HomeAssistant) -> None:
    hass.config.components.add("victron_mqtt")
    mock_entry = MagicMock()
    mock_entry.domain = "victron_mqtt"
    hass.config_entries._entries["victron_mqtt_fake"] = mock_entry


# ── async_setup_entry ─────────────────────────────────────────────────────────


async def test_setup_entry_raises_if_victron_mqtt_missing(hass: HomeAssistant) -> None:
    entry = _make_entry(hass)
    with pytest.raises(ConfigEntryNotReady, match="victron_mqtt integration is required"):
        await async_setup_entry(hass, entry)


async def test_setup_entry_raises_if_victron_mqtt_not_configured(
    hass: HomeAssistant,
) -> None:
    hass.config.components.add("victron_mqtt")
    entry = _make_entry(hass)
    with pytest.raises(ConfigEntryNotReady, match="not configured"):
        await async_setup_entry(hass, entry)


async def test_setup_entry_raises_if_deploy_fails(hass: HomeAssistant) -> None:
    _mock_victron_mqtt_ok(hass)
    entry = _make_entry(hass)
    with patch(
        "custom_components.victron_ess_control._deploy_package",
        side_effect=OSError("disk full"),
    ), pytest.raises(ConfigEntryNotReady, match="Package deployment failed"):
        await async_setup_entry(hass, entry)


async def test_setup_entry_success(hass: HomeAssistant, tmp_path: Path) -> None:
    _mock_victron_mqtt_ok(hass)
    hass.config.config_dir = str(tmp_path)
    entry = _make_entry(hass)

    pkg_content = (
        "grid_serial: <YOUR_GRID_SYSTEM_ID>\n"
        "consumer_serial: <YOUR_CONSUMER_SYSTEM_ID>\n"
    )
    with patch(
        "custom_components.victron_ess_control._deploy_package",
    ) as mock_deploy:
        result = await async_setup_entry(hass, entry)

    assert result is True
    mock_deploy.assert_called_once_with(hass, VALID_GRID_SERIAL, VALID_CONSUMER_SERIAL)
    assert entry.entry_id in hass.data[DOMAIN]


async def test_setup_entry_uses_options_over_data(hass: HomeAssistant) -> None:
    _mock_victron_mqtt_ok(hass)
    new_serial = "aabbccddeeff"
    entry = _make_entry(
        hass,
        options={
            CONF_GRID_SERIAL: new_serial,
            CONF_CONSUMER_SERIAL: new_serial,
            CONF_BATTERY_CAPACITY: 20.0,
            CONF_CHARGE_EFFICIENCY: 0.90,
        },
    )
    with patch("custom_components.victron_ess_control._deploy_package") as mock_deploy:
        await async_setup_entry(hass, entry)

    mock_deploy.assert_called_once_with(hass, new_serial, new_serial)


# ── async_unload_entry ────────────────────────────────────────────────────────


async def test_unload_entry_cleans_hass_data(hass: HomeAssistant) -> None:
    _mock_victron_mqtt_ok(hass)
    entry = _make_entry(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ENTRY_DATA

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


# ── _deploy_package ───────────────────────────────────────────────────────────


def test_deploy_package_replaces_placeholders(hass: HomeAssistant, tmp_path: Path) -> None:
    hass.config.config_dir = str(tmp_path)

    pkg_src = tmp_path / "packages"
    pkg_src.mkdir()
    template = pkg_src / "victron_ess.yaml"
    template.write_text(
        "grid: <YOUR_GRID_SYSTEM_ID>\nconsumer: <YOUR_CONSUMER_SYSTEM_ID>\n"
    )

    with patch(
        "custom_components.victron_ess_control._REPO_ROOT", tmp_path
    ):
        _deploy_package(hass, "aabbccddeeff", "112233445566")

    result = (tmp_path / "packages" / "victron_ess.yaml").read_text()
    assert "aabbccddeeff" in result
    assert "112233445566" in result
    assert "<YOUR_GRID_SYSTEM_ID>" not in result
    assert "<YOUR_CONSUMER_SYSTEM_ID>" not in result


def test_deploy_package_creates_packages_dir_if_missing(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.config_dir = str(tmp_path)
    pkg_src_dir = tmp_path / "packages"
    pkg_src_dir.mkdir()
    (pkg_src_dir / "victron_ess.yaml").write_text("grid: <YOUR_GRID_SYSTEM_ID>")

    config_packages = tmp_path / "config" / "packages"
    hass.config.config_dir = str(tmp_path / "config")

    with patch("custom_components.victron_ess_control._REPO_ROOT", tmp_path):
        _deploy_package(hass, "aabbccddeeff", "aabbccddeeff")

    assert config_packages.is_dir()
    assert (config_packages / "victron_ess.yaml").exists()


# ── _deploy_dashboards ────────────────────────────────────────────────────────


def test_deploy_dashboards_copies_yaml_files(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.config_dir = str(tmp_path)

    src_dir = tmp_path / "fake_component" / "dashboards"
    src_dir.mkdir(parents=True)
    (src_dir / "feed_in_control_center.yaml").write_text("title: Feed-In\n")
    (src_dir / "storm_mode_control_center.yaml").write_text("title: Storm\n")

    with patch("custom_components.victron_ess_control._COMPONENT_DIR", tmp_path / "fake_component"):
        _deploy_dashboards(hass)

    dst = tmp_path / "dashboards" / "victron"
    assert (dst / "feed_in_control_center.yaml").exists()
    assert (dst / "storm_mode_control_center.yaml").exists()


def test_deploy_dashboards_skips_existing_files(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.config_dir = str(tmp_path)

    src_dir = tmp_path / "fake_component" / "dashboards"
    src_dir.mkdir(parents=True)
    (src_dir / "feed_in_control_center.yaml").write_text("title: New\n")

    dst = tmp_path / "dashboards" / "victron"
    dst.mkdir(parents=True)
    existing = dst / "feed_in_control_center.yaml"
    existing.write_text("title: Existing\n")

    with patch("custom_components.victron_ess_control._COMPONENT_DIR", tmp_path / "fake_component"):
        _deploy_dashboards(hass)

    assert existing.read_text() == "title: Existing\n"


def test_deploy_dashboards_creates_target_dir(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.config_dir = str(tmp_path)

    src_dir = tmp_path / "fake_component" / "dashboards"
    src_dir.mkdir(parents=True)
    (src_dir / "overnight_charging_control_center.yaml").write_text("title: Overnight\n")

    with patch("custom_components.victron_ess_control._COMPONENT_DIR", tmp_path / "fake_component"):
        _deploy_dashboards(hass)

    assert (tmp_path / "dashboards" / "victron").is_dir()

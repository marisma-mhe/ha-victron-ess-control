from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CONSUMER_SERIAL,
    CONF_GRID_SERIAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_COMPONENT_DIR = Path(__file__).parent


def _deploy_package(hass: HomeAssistant, grid_serial: str, consumer_serial: str) -> None:
    config_dir = Path(hass.config.config_dir)

    pkg_src = _COMPONENT_DIR / "packages" / "victron_ess.yaml"
    pkg_dst_dir = config_dir / "packages"
    pkg_dst_dir.mkdir(exist_ok=True)
    pkg_dst = pkg_dst_dir / "victron_ess.yaml"

    content = pkg_src.read_text()
    content = content.replace("<YOUR_GRID_SYSTEM_ID>", grid_serial)
    content = content.replace("<YOUR_CONSUMER_SYSTEM_ID>", consumer_serial)
    pkg_dst.write_text(content)
    _LOGGER.info("Wrote %s", pkg_dst)


def _deploy_blueprints(hass: HomeAssistant) -> None:
    src = _COMPONENT_DIR / "blueprints" / "automation" / "victron"
    dst = Path(hass.config.config_dir) / "blueprints" / "automation" / "victron"
    dst.mkdir(parents=True, exist_ok=True)
    for bp in src.glob("*.yaml"):
        target = dst / bp.name
        if not target.exists():
            target.write_bytes(bp.read_bytes())
            _LOGGER.info("Installed blueprint %s", bp.name)


def _deploy_dashboards(hass: HomeAssistant) -> None:
    src = _COMPONENT_DIR / "dashboards"
    dst = Path(hass.config.config_dir) / "dashboards" / "victron"
    dst.mkdir(parents=True, exist_ok=True)
    for db in src.glob("*.yaml"):
        target = dst / db.name
        if not target.exists():
            target.write_bytes(db.read_bytes())
            _LOGGER.info("Installed dashboard %s", db.name)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if "victron_mqtt" not in hass.config.components:
        raise ConfigEntryNotReady(
            "victron_mqtt integration is required. "
            "Install via HACS: https://github.com/tomer-w/ha-victron-mqtt"
        )
    if not hass.config_entries.async_entries("victron_mqtt"):
        raise ConfigEntryNotReady(
            "victron_mqtt is installed but not configured. "
            "Add it via Settings → Integrations."
        )

    data = dict(entry.data)
    if entry.options:
        data.update(entry.options)

    grid_serial: str = data[CONF_GRID_SERIAL]
    consumer_serial: str = data[CONF_CONSUMER_SERIAL]

    try:
        await hass.async_add_executor_job(
            _deploy_package, hass, grid_serial, consumer_serial
        )
        await hass.async_add_executor_job(_deploy_blueprints, hass)
        await hass.async_add_executor_job(_deploy_dashboards, hass)
    except Exception as exc:
        _LOGGER.exception("Failed to deploy Victron ESS Control package")
        raise ConfigEntryNotReady(f"Package deployment failed: {exc}") from exc

    hass.components.persistent_notification.async_create(
        message=(
            "**Victron ESS Control** has been set up.\n\n"
            f"- Grid serial: `{grid_serial}`\n"
            f"- Consumer serial: `{consumer_serial}`\n\n"
            "`packages/victron_ess.yaml` has been written, blueprints installed under "
            "`blueprints/automation/victron/`, and dashboard views installed under "
            "`dashboards/victron/`.\n\n"
            "**Restart Home Assistant** to load the helpers and template sensors, "
            "then create automation instances under Settings → Automations → Blueprints.\n\n"
            "To enable the dashboard views, add them to `configuration.yaml`:\n"
            "```yaml\nlovelace:\n  dashboards:\n"
            "    victron-feed-in:\n      mode: yaml\n      filename: dashboards/victron/feed_in_control_center.yaml\n"
            "      title: Feed-In Control\n      icon: mdi:solar-power\n      show_in_sidebar: true\n```"
        ),
        title="Victron ESS Control: Restart Required",
        notification_id=f"{DOMAIN}_setup",
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

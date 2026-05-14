from __future__ import annotations

import logging
import shutil
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_CHARGE_EFFICIENCY,
    CONF_CONSUMER_SERIAL,
    CONF_GRID_SERIAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_COMPONENT_DIR = Path(__file__).parent
_REPO_ROOT = _COMPONENT_DIR.parent.parent


def _deploy_files(hass: HomeAssistant, grid_serial: str, consumer_serial: str) -> None:
    config_dir = Path(hass.config.config_dir)

    # ── Package file ───────────────────────────────────────────────────────────
    pkg_src = _REPO_ROOT / "packages" / "victron_ess.yaml"
    pkg_dst_dir = config_dir / "packages"
    pkg_dst_dir.mkdir(exist_ok=True)
    pkg_dst = pkg_dst_dir / "victron_ess.yaml"

    content = pkg_src.read_text()
    content = content.replace("<YOUR_GRID_SYSTEM_ID>", grid_serial)
    content = content.replace("<YOUR_CONSUMER_SYSTEM_ID>", consumer_serial)
    pkg_dst.write_text(content)
    _LOGGER.info("Wrote %s", pkg_dst)

    # ── Blueprints ─────────────────────────────────────────────────────────────
    bp_src = _REPO_ROOT / "blueprints" / "automation" / "victron"
    bp_dst = config_dir / "blueprints" / "automation" / "victron"
    bp_dst.mkdir(parents=True, exist_ok=True)

    for src_file in bp_src.glob("*.yaml"):
        dst_file = bp_dst / src_file.name
        if not dst_file.exists():
            shutil.copy2(src_file, dst_file)
            _LOGGER.info("Installed blueprint: %s", src_file.name)
        else:
            _LOGGER.debug("Blueprint already exists, skipping: %s", src_file.name)


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
            _deploy_files, hass, grid_serial, consumer_serial
        )
    except Exception as exc:
        _LOGGER.exception("Failed to deploy Victron ESS Control files")
        raise ConfigEntryNotReady(f"File deployment failed: {exc}") from exc

    hass.components.persistent_notification.async_create(
        message=(
            "**Victron ESS Control** has been set up.\n\n"
            f"- Grid serial: `{grid_serial}`\n"
            f"- Consumer serial: `{consumer_serial}`\n\n"
            "`packages/victron_ess.yaml` and blueprints have been installed. "
            "**Restart Home Assistant** to load the helpers and template sensors.\n\n"
            "After restart, create automation instances from the installed blueprints "
            "under Settings → Automations → Blueprints."
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

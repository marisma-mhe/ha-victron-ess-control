Custom integration for Victron Energy ESS systems. Provides a guided setup wizard (config flow), canonical `sensor.victron_ess_*` template sensors, all required helpers, and utility meters — packaged for one-line installation.

## Requirements

- **[ha-victron-mqtt](https://github.com/tomer-w/ha-victron-mqtt)** (HACS) — Victron data source (install first)
- **HA MQTT Integration** — must be connected to the same broker as the Victron GX device
- **Home Assistant 2024.6+**

## What this installs

- Guided config flow — enter your GX device serials, battery capacity; deploys `packages/victron_ess.yaml` automatically
- Canonical sensors: `sensor.victron_ess_battery_soc`, `sensor.victron_ess_grid_power`, `sensor.victron_ess_solar_power`, and more
- All `input_*` helpers and utility meters for feed-in, charging, and storm mode

## Companion repo

Automation blueprints and Lovelace dashboard views are in **[ha-victron-ess-frontend](https://github.com/marisma-mhe/ha-victron-ess-frontend)** — install that after this integration.

"""YAML structure tests for bundled Victron ESS dashboard files."""
from __future__ import annotations

from pathlib import Path

import yaml

DASHBOARDS_DIR = (
    Path(__file__).parent.parent
    / "custom_components"
    / "victron_ess_control"
    / "dashboards"
)
DASHBOARD_FILES = sorted(DASHBOARDS_DIR.glob("*.yaml"))

EXPECTED_DASHBOARDS = {
    "feed_in_control_center.yaml",
    "max_feed_in_control_center.yaml",
    "overnight_charging_control_center.yaml",
    "storm_mode_control_center.yaml",
    "victron_overview_values.yaml",
}


def _load(path: Path):
    with path.open() as f:
        return yaml.safe_load(f)


def test_all_expected_dashboards_present() -> None:
    found = {f.name for f in DASHBOARD_FILES}
    missing = EXPECTED_DASHBOARDS - found
    assert not missing, f"Expected dashboard files missing: {missing}"


class TestDashboards:
    def test_parses_as_valid_yaml(self) -> None:
        for path in DASHBOARD_FILES:
            doc = _load(path)
            assert doc is not None, f"{path.name}: empty file"

    def test_no_marisma_serials(self) -> None:
        for path in DASHBOARD_FILES:
            content = path.read_text()
            for serial in ("c0619ab4eec9", "c0619ab2288d"):
                assert serial not in content, (
                    f"{path.name}: hardcoded Marisma serial '{serial}' found"
                )

    def test_site_specific_markers_not_in_entity_fields(self) -> None:
        """[SITE-SPECIFIC] in entity: or entity_id: values would break the card."""
        import re
        pattern = re.compile(r"^\s*entity(?:_id)?:\s.*\[SITE-SPECIFIC\]")
        for path in DASHBOARD_FILES:
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                assert not pattern.match(line), (
                    f"{path.name}:{lineno}: [SITE-SPECIFIC] marker in entity field"
                )

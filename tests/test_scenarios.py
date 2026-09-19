"""Tests for pre-packaged simulation scenarios.

Verifies that:
- All 4 scenarios execute successfully through the engine.
- Different scenarios produce measurably different peak depths.
- Different scenarios produce different critical-cell counts.
- Scenario registry lookup works (valid and invalid names).
- Mass conservation holds across all scenarios.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from flowshield.risk.classifier import RiskLevel, classify_risk
from flowshield.simulation.scenarios import (
    SCENARIO_REGISTRY,
    channel_blockage,
    cloudburst_surge,
    normal_rainfall,
    pump_drainage_failure,
    run_scenario,
)
from flowshield.validation.conservation import check_mass_conservation


# ═════════════════════════════════════════════════════════════════════════════
# 1.  SCENARIO EXECUTION
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioExecution:
    """Each scenario must run to completion with a valid audit trail."""

    @pytest.mark.parametrize("name", list(SCENARIO_REGISTRY.keys()))
    def test_scenario_completes(self, name: str):
        engine = run_scenario(name)
        assert engine.is_complete
        assert len(engine.audit.rain_added_history) == engine.num_steps

    @pytest.mark.parametrize("name", list(SCENARIO_REGISTRY.keys()))
    def test_scenario_mass_conservation(self, name: str):
        engine = run_scenario(name)
        result = check_mass_conservation(engine)
        assert result.passed, f"{name}: error={result.absolute_error:.2e}"


# ═════════════════════════════════════════════════════════════════════════════
# 2.  MEASURABLE DIFFERENCES BETWEEN SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioDifferences:
    """Different scenarios must produce different flood outcomes."""

    @pytest.fixture(scope="class")
    @classmethod
    def engines(cls):
        """Run all 4 scenarios once and cache results for this test class."""
        return {
            "normal": normal_rainfall(),
            "cloudburst": cloudburst_surge(),
            "drainage": pump_drainage_failure(),
            "blockage": channel_blockage(),
        }

    def test_cloudburst_peak_exceeds_normal(self, engines):
        normal_peak = engines["normal"].grid.water_depth.max()
        cloud_peak = engines["cloudburst"].grid.water_depth.max()
        assert cloud_peak > normal_peak

    def test_drainage_failure_has_more_water_than_normal(self, engines):
        normal_vol = engines["normal"].grid.water_depth.sum()
        drain_vol = engines["drainage"].grid.water_depth.sum()
        assert drain_vol > normal_vol

    def test_blockage_peak_exceeds_normal(self, engines):
        normal_peak = engines["normal"].grid.water_depth.max()
        block_peak = engines["blockage"].grid.water_depth.max()
        assert block_peak > normal_peak

    def test_different_peak_depths(self, engines):
        peaks = {k: e.grid.water_depth.max() for k, e in engines.items()}
        values = list(peaks.values())
        # At least 3 of 4 must be distinct (allow small tolerance)
        unique = len(set(round(v, 4) for v in values))
        assert unique >= 3, f"Too few distinct peak depths: {peaks}"

    def test_different_critical_counts(self, engines):
        counts = {}
        for name, eng in engines.items():
            risk = classify_risk(
                eng.grid.water_depth,
                eng.config.risk.warning_depth_m,
                eng.config.risk.critical_depth_m,
            )
            counts[name] = int((risk == RiskLevel.CRITICAL).sum())
        values = list(counts.values())
        unique = len(set(values))
        assert unique >= 2, f"Too few distinct critical counts: {counts}"


# ═════════════════════════════════════════════════════════════════════════════
# 3.  REGISTRY LOOKUP
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioRegistry:
    """Verify the run_scenario() registry lookup."""

    def test_valid_names(self):
        for name in SCENARIO_REGISTRY:
            engine = run_scenario(name)
            assert engine.is_complete

    def test_invalid_name_raises(self):
        with pytest.raises(KeyError, match="Unknown scenario"):
            run_scenario("Nonexistent Disaster")

    def test_registry_has_four_entries(self):
        assert len(SCENARIO_REGISTRY) == 4

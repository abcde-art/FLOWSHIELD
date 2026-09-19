"""Tests for risk classification, time-to-critical forecasting, and population impact.

Covers:
- Classification boundary edges (exact threshold values).
- Full-grid classification with mixed depths.
- Regression slope and time-to-critical on deterministic linear inputs.
- All forecasting status codes (CRITICAL NOW, NOT EXPECTED, INSUFFICIENT DATA).
- Population impact aggregation correctness.
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
from flowshield.risk.forecasting import (
    CRITICAL_NOW,
    INSUFFICIENT_DATA,
    NOT_EXPECTED,
    predict_time_to_critical,
)
from flowshield.risk.population import PopulationImpact, compute_population_impact


# ═════════════════════════════════════════════════════════════════════════════
# 1.  RISK CLASSIFIER
# ═════════════════════════════════════════════════════════════════════════════

class TestClassifierEdges:
    """Test exact boundary transitions for SAFE/WARNING/CRITICAL."""

    WARNING = 0.10
    CRITICAL = 0.30

    def test_below_warning_is_safe(self):
        wd = np.array([[0.0, 0.05, 0.099]])
        risk = classify_risk(wd, self.WARNING, self.CRITICAL)
        assert (risk == RiskLevel.SAFE).all()

    def test_at_warning_is_warning(self):
        wd = np.array([[0.10]])
        risk = classify_risk(wd, self.WARNING, self.CRITICAL)
        assert risk[0, 0] == RiskLevel.WARNING

    def test_between_warning_and_critical_is_warning(self):
        wd = np.array([[0.15, 0.20, 0.299]])
        risk = classify_risk(wd, self.WARNING, self.CRITICAL)
        assert (risk == RiskLevel.WARNING).all()

    def test_at_critical_is_critical(self):
        wd = np.array([[0.30]])
        risk = classify_risk(wd, self.WARNING, self.CRITICAL)
        assert risk[0, 0] == RiskLevel.CRITICAL

    def test_above_critical_is_critical(self):
        wd = np.array([[0.5, 1.0, 10.0]])
        risk = classify_risk(wd, self.WARNING, self.CRITICAL)
        assert (risk == RiskLevel.CRITICAL).all()

    def test_zero_depth_is_safe(self):
        wd = np.array([[0.0]])
        risk = classify_risk(wd, self.WARNING, self.CRITICAL)
        assert risk[0, 0] == RiskLevel.SAFE


class TestClassifierGrid:
    """Test full-grid classification with mixed depths."""

    def test_mixed_grid(self):
        wd = np.array([
            [0.0,  0.05, 0.10],
            [0.15, 0.30, 0.50],
        ], dtype=np.float64)
        risk = classify_risk(wd, warning_threshold=0.10, critical_threshold=0.30)

        assert risk[0, 0] == RiskLevel.SAFE
        assert risk[0, 1] == RiskLevel.SAFE
        assert risk[0, 2] == RiskLevel.WARNING
        assert risk[1, 0] == RiskLevel.WARNING
        assert risk[1, 1] == RiskLevel.CRITICAL
        assert risk[1, 2] == RiskLevel.CRITICAL

    def test_output_shape_matches_input(self):
        wd = np.zeros((7, 13), dtype=np.float64)
        risk = classify_risk(wd, 0.1, 0.3)
        assert risk.shape == (7, 13)

    def test_output_dtype_is_int32(self):
        wd = np.zeros((3, 3), dtype=np.float64)
        risk = classify_risk(wd, 0.1, 0.3)
        assert risk.dtype == np.int32


# ═════════════════════════════════════════════════════════════════════════════
# 2.  TIME-TO-CRITICAL FORECASTING
# ═════════════════════════════════════════════════════════════════════════════

class TestForecastingLinearInput:
    """Deterministic linear inputs with known slopes."""

    def test_perfect_linear_rise(self):
        """y = 0.01 * t → slope = 0.01 m/step = 0.01 m/min at 1-min steps."""
        history = [0.00, 0.01, 0.02, 0.03, 0.04]
        current = 0.04
        critical = 0.30
        result = predict_time_to_critical(
            history, current, critical, timestep_minutes=1.0, window_size=5
        )
        # (0.30 - 0.04) / 0.01 = 26.0 minutes
        assert isinstance(result, float)
        assert result == pytest.approx(26.0, rel=1e-6)

    def test_steeper_slope(self):
        """y = 0.05 * t → slope = 0.05 m/step."""
        history = [0.0, 0.05, 0.10, 0.15, 0.20]
        current = 0.20
        critical = 0.50
        result = predict_time_to_critical(
            history, current, critical, timestep_minutes=1.0, window_size=5
        )
        # (0.50 - 0.20) / 0.05 = 6.0 minutes
        assert result == pytest.approx(6.0, rel=1e-6)

    def test_timestep_scaling(self):
        """Same slope per step but timestep = 2 min → double the minutes."""
        history = [0.00, 0.01, 0.02, 0.03, 0.04]
        current = 0.04
        critical = 0.30
        result = predict_time_to_critical(
            history, current, critical, timestep_minutes=2.0, window_size=5
        )
        # 26 steps * 2 min/step = 52 minutes
        assert result == pytest.approx(52.0, rel=1e-6)

    def test_window_uses_recent_entries(self):
        """Only the last window_size entries matter."""
        # Old flat data + recent rise
        history = [0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.02, 0.03, 0.04]
        current = 0.04
        critical = 0.30
        result = predict_time_to_critical(
            history, current, critical, timestep_minutes=1.0, window_size=5
        )
        # Window = [0.0, 0.01, 0.02, 0.03, 0.04] → slope = 0.01
        assert result == pytest.approx(26.0, rel=1e-6)


class TestForecastingStatusCodes:
    """Verify all non-numeric return codes."""

    def test_critical_now(self):
        result = predict_time_to_critical(
            [0.1, 0.2, 0.3, 0.4, 0.5], 0.50, critical_threshold=0.30
        )
        assert result == CRITICAL_NOW

    def test_critical_now_at_exact_threshold(self):
        result = predict_time_to_critical(
            [0.1, 0.2, 0.3, 0.3, 0.3], 0.30, critical_threshold=0.30
        )
        assert result == CRITICAL_NOW

    def test_not_expected_falling(self):
        history = [0.10, 0.08, 0.06, 0.04, 0.02]
        result = predict_time_to_critical(
            history, 0.02, critical_threshold=0.30
        )
        assert result == NOT_EXPECTED

    def test_not_expected_flat(self):
        history = [0.05, 0.05, 0.05, 0.05, 0.05]
        result = predict_time_to_critical(
            history, 0.05, critical_threshold=0.30
        )
        assert result == NOT_EXPECTED

    def test_insufficient_data(self):
        result = predict_time_to_critical(
            [0.01, 0.02], 0.02, critical_threshold=0.30, window_size=5
        )
        assert result == INSUFFICIENT_DATA

    def test_insufficient_data_empty(self):
        result = predict_time_to_critical(
            [], 0.0, critical_threshold=0.30, window_size=5
        )
        assert result == INSUFFICIENT_DATA


# ═════════════════════════════════════════════════════════════════════════════
# 3.  POPULATION IMPACT
# ═════════════════════════════════════════════════════════════════════════════

class TestPopulationImpact:
    """Verify population aggregation at each risk level."""

    def test_all_safe(self):
        wd = np.zeros((3, 3), dtype=np.float64)
        pop = np.full((3, 3), 100, dtype=np.int32)
        result = compute_population_impact(wd, pop, 0.10, 0.30)
        assert result.warning_population == 0
        assert result.critical_population == 0
        assert result.total_affected == 0

    def test_all_critical(self):
        wd = np.full((3, 3), 1.0, dtype=np.float64)
        pop = np.full((3, 3), 50, dtype=np.int32)
        result = compute_population_impact(wd, pop, 0.10, 0.30)
        assert result.warning_population == 0   # all are CRITICAL, not WARNING
        assert result.critical_population == 450
        assert result.total_affected == 450

    def test_mixed_levels(self):
        wd = np.array([
            [0.0,  0.15, 0.50],
        ], dtype=np.float64)
        pop = np.array([
            [1000, 2000, 3000],
        ], dtype=np.int32)
        result = compute_population_impact(wd, pop, 0.10, 0.30)
        assert result.warning_population == 2000   # cell (0,1)
        assert result.critical_population == 3000  # cell (0,2)
        assert result.total_affected == 5000

    def test_total_affected_property(self):
        impact = PopulationImpact(warning_population=100, critical_population=200)
        assert impact.total_affected == 300

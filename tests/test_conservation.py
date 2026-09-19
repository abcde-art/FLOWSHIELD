"""Tests for mass conservation, non-negativity, and physical flow invariants.

Covers:
- Full-simulation mass conservation across all 4 scenario configs.
- Per-step mass conservation during partial runs.
- Water non-negativity after every timestep.
- No uphill gravity inflow from dry lower terrain.
- Rainfall unit conversion correctness.
- Drainage capping at water depth.
- Drainage blockage support.
- D4 flow mass neutrality.
- Flow boundary no-wrap verification.
- Performance benchmark (120 steps on 30×30).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from flowshield.data.generator import CityGridGenerator
from flowshield.data.models import CityGrid
from flowshield.simulation.drainage import compute_drainage
from flowshield.simulation.engine import SimulationEngine
from flowshield.simulation.flow import compute_flow
from flowshield.simulation.rainfall import compute_rainfall
from flowshield.utils.config import SimulationConfig, load_config
from flowshield.validation.conservation import (
    ConservationResult,
    check_mass_conservation,
    check_no_uphill_gravity_inflow,
    check_non_negative_water,
)

_CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _default_config(**overrides) -> SimulationConfig:
    return SimulationConfig.model_validate(overrides)


def _make_engine(config: SimulationConfig | None = None, **kw) -> SimulationEngine:
    config = config or _default_config(**kw)
    gen = CityGridGenerator(config)
    grid = gen.generate()
    return SimulationEngine(config, grid)


def _flat_grid(rows: int = 10, cols: int = 10, elev: float = 0.0) -> CityGrid:
    """Create a minimal flat grid with uniform drainage capacity."""
    return CityGrid(
        elevation=np.full((rows, cols), elev, dtype=np.float64),
        population=np.zeros((rows, cols), dtype=np.int32),
        drainage_capacity=np.full((rows, cols), 1e-4, dtype=np.float64),
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1.  MASS CONSERVATION — full simulation
# ═════════════════════════════════════════════════════════════════════════════

class TestMassConservationFull:
    """Run complete simulations and verify mass balance."""

    def test_default_scenario(self):
        engine = _make_engine()
        engine.run()
        result = check_mass_conservation(engine)
        assert result.passed, (
            f"Mass error {result.absolute_error:.2e}  "
            f"(expected {result.expected_volume:.6f}, "
            f"actual {result.actual_volume:.6f})"
        )

    @pytest.mark.parametrize(
        "filename",
        ["default.json", "heavy_rain.json", "drainage_failure.json", "blocked_channel.json"],
    )
    def test_all_scenario_files(self, filename: str):
        config = load_config(_CONFIGS_DIR / filename)
        gen = CityGridGenerator(config)
        grid = gen.generate()
        engine = SimulationEngine(config, grid)
        engine.run()
        result = check_mass_conservation(engine)
        assert result.passed, f"{filename}: error={result.absolute_error:.2e}"

    def test_zero_rain_conserves(self):
        """No rainfall, no drainage → volume stays constant (zero)."""
        cfg = _default_config(
            rainfall={"rate_mm_per_h": 0.0, "duration_h": 0.0},
            drainage={"base_capacity_m3_per_h": 0.0},
            simulation={"timestep_min": 1, "duration_h": 10/60},
        )
        engine = _make_engine(config=cfg)
        engine.run()
        result = check_mass_conservation(engine)
        assert result.passed
        assert result.actual_volume == pytest.approx(0.0, abs=1e-12)

    def test_no_drainage_scenario(self):
        """All rain accumulates when drainage = 0."""
        cfg = _default_config(
            rainfall={"rate_mm_per_h": 20.0, "duration_h": 10.0/60.0},
            drainage={"base_capacity_m3_per_h": 0.0},
            simulation={"timestep_min": 1, "duration_h": 10/60},
            grid={"height": 10, "width": 10},
        )
        engine = _make_engine(config=cfg)
        engine.run()
        result = check_mass_conservation(engine)
        assert result.passed
        # All rain should still be in the grid
        assert engine.audit.cumulative_drainage == pytest.approx(0.0, abs=1e-15)


# ═════════════════════════════════════════════════════════════════════════════
# 2.  PER-STEP CONSERVATION
# ═════════════════════════════════════════════════════════════════════════════

class TestMassConservationPerStep:
    """Check mass balance after every individual step."""

    def test_conservation_every_step(self):
        engine = _make_engine(
            simulation={"timestep_min": 1, "duration_h": 30.0/60.0},
            grid={"height": 15, "width": 15},
        )
        for _ in range(engine.num_steps):
            engine.step()
            result = check_mass_conservation(engine)
            assert result.passed, (
                f"Step {engine.current_step}: error={result.absolute_error:.2e}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 3.  NON-NEGATIVE WATER DEPTH
# ═════════════════════════════════════════════════════════════════════════════

class TestNonNegativeWater:
    """Water depth must remain ≥ 0 at all times."""

    def test_never_negative_default(self):
        engine = _make_engine()
        for _ in range(engine.num_steps):
            engine.step()
            assert check_non_negative_water(engine.grid), (
                f"Negative water at step {engine.current_step}"
            )

    def test_never_negative_heavy_rain(self):
        cfg = load_config(_CONFIGS_DIR / "heavy_rain.json")
        gen = CityGridGenerator(cfg)
        engine = SimulationEngine(cfg, gen.generate())
        engine.run()
        assert check_non_negative_water(engine.grid)


# ═════════════════════════════════════════════════════════════════════════════
# 4.  NO UPHILL GRAVITY INFLOW
# ═════════════════════════════════════════════════════════════════════════════

class TestNoUphillInflow:
    """Higher elevation dry cells must not receive water from lower dry terrain."""

    def test_peak_cell_stays_dry(self):
        """A tall dry peak surrounded by lower dry cells should gain nothing."""
        rows, cols = 5, 5
        elev = np.ones((rows, cols), dtype=np.float64)
        elev[2, 2] = 10.0  # tall peak
        wd = np.zeros((rows, cols), dtype=np.float64)

        wd_before = wd.copy()
        net = compute_flow(elev, wd, flow_coefficient=0.20)
        wd_after = wd + net

        # Peak should still be at zero
        assert wd_after[2, 2] == pytest.approx(0.0, abs=1e-15)
        assert check_no_uphill_gravity_inflow(elev, wd_before, wd_after)

    def test_water_on_peak_flows_downhill(self):
        """Water placed on a peak flows to lower neighbours, not vice-versa."""
        rows, cols = 5, 5
        elev = np.zeros((rows, cols), dtype=np.float64)
        elev[2, 2] = 5.0
        wd = np.zeros((rows, cols), dtype=np.float64)
        wd[2, 2] = 1.0  # water on peak

        wd_before = wd.copy()
        net = compute_flow(elev, wd, flow_coefficient=0.20)
        wd_after = wd + net

        # Peak should lose water
        assert wd_after[2, 2] < wd_before[2, 2]
        # Neighbours should gain
        assert wd_after[1, 2] > 0 or wd_after[3, 2] > 0
        assert check_no_uphill_gravity_inflow(elev, wd_before, wd_after)

    def test_low_water_does_not_climb_hill(self):
        """Water in a valley should not climb to a dry hilltop when head < hill elev."""
        rows, cols = 7, 7
        elev = np.zeros((rows, cols), dtype=np.float64)
        # Create a ridge on the right side
        elev[:, 4:] = 10.0
        wd = np.zeros((rows, cols), dtype=np.float64)
        # Water in valley (left side), but surface head (0 + 2) < hill (10)
        wd[:, 0:4] = 2.0

        wd_before = wd.copy()
        net = compute_flow(elev, wd, flow_coefficient=0.20)
        wd_after = wd + net

        # Ridge cells should remain dry
        np.testing.assert_array_equal(wd_after[:, 5:], 0.0)
        assert check_no_uphill_gravity_inflow(elev, wd_before, wd_after)

    def test_full_simulation_no_uphill(self):
        """Run a full default simulation and check uphill invariant per step."""
        cfg = _default_config(
            simulation={"timestep_min": 1, "duration_h": 20.0/60.0},
            grid={"height": 15, "width": 15},
        )
        gen = CityGridGenerator(cfg)
        grid = gen.generate()
        engine = SimulationEngine(cfg, grid)

        for _ in range(engine.num_steps):
            wd_before = engine.grid.water_depth.copy()
            engine.step()
            wd_after = engine.grid.water_depth.copy()
            assert check_no_uphill_gravity_inflow(
                engine.grid.elevation, wd_before, wd_after
            )


# ═════════════════════════════════════════════════════════════════════════════
# 5.  RAINFALL UNIT CONVERSION
# ═════════════════════════════════════════════════════════════════════════════

class TestRainfallModule:
    """Verify rainfall calculations and unit conversions."""

    def test_mm_to_m_conversion(self):
        cfg = _default_config(
            rainfall={"rate_mm_per_h": 60.0, "duration_h": 10.0/60.0},
            simulation={"timestep_min": 1, "duration_h": 10/60},
        )
        rain = compute_rainfall(cfg, 0, (1, 1))
        # 60 mm/hr × (1/60 hr) = 1 mm = 0.001 m
        assert rain[0, 0] == pytest.approx(0.001, rel=1e-10)

    def test_no_rain_after_event_ends(self):
        cfg = _default_config(
            rainfall={"rate_mm_per_h": 60.0, "duration_h": 5.0/60.0},
            simulation={"timestep_min": 1, "duration_h": 10/60},
        )
        rain = compute_rainfall(cfg, 5, (2, 2))  # minute 5 → event over
        np.testing.assert_array_equal(rain, 0.0)

    def test_surge_multiplier_applied(self):
        cfg = _default_config(
            rainfall={
                "rate_mm_per_h": 20.0,
                "duration_h": 1.0,
                "peak_time_fraction": 10.0/60.0,
                "peak_multiplier": 3.0,
            },
            simulation={"timestep_min": 1, "duration_h": 1.0},
        )
        rain_before = compute_rainfall(cfg, 5, (1, 1))   # minute 5 (no surge)
        rain_during = compute_rainfall(cfg, 15, (1, 1))   # minute 15 (surge)
        assert rain_during[0, 0] == pytest.approx(3.0 * rain_before[0, 0], rel=1e-10)

    def test_rain_uniform_across_grid(self):
        cfg = _default_config()
        rain = compute_rainfall(cfg, 0, (10, 12))
        assert rain.shape == (10, 12)
        assert np.all(rain == rain[0, 0])


# ═════════════════════════════════════════════════════════════════════════════
# 6.  DRAINAGE MODULE
# ═════════════════════════════════════════════════════════════════════════════

class TestDrainageModule:
    """Verify drainage capping and blockage support."""

    def test_drain_capped_at_water_depth(self):
        wd = np.array([[0.001]], dtype=np.float64)
        cap = np.array([[1.0]], dtype=np.float64)  # much larger than wd
        drained = compute_drainage(wd, cap)
        assert drained[0, 0] == pytest.approx(0.001)

    def test_drain_capped_at_capacity(self):
        wd = np.array([[1.0]], dtype=np.float64)
        cap = np.array([[0.005]], dtype=np.float64)
        drained = compute_drainage(wd, cap)
        assert drained[0, 0] == pytest.approx(0.005)

    def test_full_blockage(self):
        wd = np.ones((3, 3), dtype=np.float64)
        cap = np.ones((3, 3), dtype=np.float64) * 0.01
        mask = np.zeros((3, 3), dtype=np.float64)  # fully blocked
        drained = compute_drainage(wd, cap, blockage_mask=mask)
        np.testing.assert_array_equal(drained, 0.0)

    def test_partial_blockage(self):
        wd = np.ones((2, 2), dtype=np.float64)
        cap = np.full((2, 2), 0.1, dtype=np.float64)
        mask = np.full((2, 2), 0.5, dtype=np.float64)  # 50 % capacity
        drained = compute_drainage(wd, cap, blockage_mask=mask)
        np.testing.assert_array_almost_equal(drained, 0.05)


# ═════════════════════════════════════════════════════════════════════════════
# 7.  D4 FLOW — MASS NEUTRALITY & BOUNDARIES
# ═════════════════════════════════════════════════════════════════════════════

class TestFlowModule:
    """Verify flow module physics."""

    def test_net_flow_sums_to_zero(self):
        """Lateral flow must be mass-neutral (pure redistribution)."""
        rng = np.random.default_rng(42)
        elev = rng.uniform(0, 10, (20, 20))
        wd = rng.uniform(0, 0.5, (20, 20))
        net = compute_flow(elev, wd, flow_coefficient=0.20)
        assert net.sum() == pytest.approx(0.0, abs=1e-12)

    def test_flow_on_flat_with_uniform_water_is_zero(self):
        """No head gradient → no flow."""
        elev = np.ones((10, 10), dtype=np.float64) * 5.0
        wd = np.ones((10, 10), dtype=np.float64) * 0.5
        net = compute_flow(elev, wd, flow_coefficient=0.20)
        np.testing.assert_array_almost_equal(net, 0.0, decimal=14)

    def test_no_wrap_around(self):
        """Water at edge must NOT wrap to opposite edge."""
        elev = np.zeros((5, 5), dtype=np.float64)
        wd = np.zeros((5, 5), dtype=np.float64)
        wd[0, 0] = 1.0  # top-left corner

        net = compute_flow(elev, wd, flow_coefficient=0.5)
        wd_after = wd + net

        # Bottom-right and opposite-edge cells must remain at zero.
        assert wd_after[4, 4] == pytest.approx(0.0, abs=1e-15)
        assert wd_after[4, 0] == pytest.approx(0.0, abs=1e-15)
        assert wd_after[0, 4] == pytest.approx(0.0, abs=1e-15)

    def test_outflow_never_exceeds_depth(self):
        """Total outflow from any cell must be ≤ its water depth."""
        rng = np.random.default_rng(7)
        elev = rng.uniform(0, 10, (15, 15))
        wd = rng.uniform(0, 0.3, (15, 15))
        net = compute_flow(elev, wd, flow_coefficient=0.5)
        # net can be negative (outflow > inflow), but wd + net must be ≥ 0
        assert ((wd + net) >= -1e-14).all()

    def test_downhill_flow_direction(self):
        """Water on a slope should move to the lower side."""
        elev = np.zeros((1, 5), dtype=np.float64)
        elev[0, :] = [4, 3, 2, 1, 0]  # slope left→right
        wd = np.zeros((1, 5), dtype=np.float64)
        wd[0, 0] = 1.0  # water at highest point

        net = compute_flow(elev, wd, flow_coefficient=0.2)
        # Cell 0 should lose water (net < 0), cell 1 should gain (net > 0)
        assert net[0, 0] < 0
        assert net[0, 1] > 0


# ═════════════════════════════════════════════════════════════════════════════
# 8.  ENGINE AUDIT HISTORY
# ═════════════════════════════════════════════════════════════════════════════

class TestEngineAudit:
    """Verify audit trail completeness."""

    def test_history_length_matches_steps(self):
        engine = _make_engine(
            simulation={"timestep_min": 1, "duration_h": 10/60},
            grid={"height": 5, "width": 5},
        )
        engine.run()
        assert len(engine.audit.rain_added_history) == 10
        assert len(engine.audit.water_drained_history) == 10
        assert len(engine.audit.total_water_volume_history) == 10

    def test_cumulative_properties(self):
        engine = _make_engine(
            simulation={"timestep_min": 1, "duration_h": 5/60},
            grid={"height": 5, "width": 5},
        )
        engine.run()
        assert engine.audit.cumulative_rain == pytest.approx(
            sum(engine.audit.rain_added_history)
        )
        assert engine.audit.cumulative_drainage == pytest.approx(
            sum(engine.audit.water_drained_history)
        )


# ═════════════════════════════════════════════════════════════════════════════
# 9.  PERFORMANCE BENCHMARK
# ═════════════════════════════════════════════════════════════════════════════

class TestBenchmark:
    """Benchmark: 120 timesteps on a 30×30 grid."""

    def test_benchmark_30x30_120steps(self):
        cfg = _default_config(
            grid={"height": 30, "width": 30},
            simulation={"timestep_min": 1, "duration_h": 2},
        )
        gen = CityGridGenerator(cfg)
        grid = gen.generate()
        engine = SimulationEngine(cfg, grid)

        t0 = time.perf_counter()
        engine.run()
        elapsed = time.perf_counter() - t0

        print(f"\n  -> Benchmark: 120 steps x 30x30 grid completed in {elapsed:.4f}s")

        # Sanity: should complete in a reasonable time (< 10 s on any machine)
        assert elapsed < 10.0, f"Benchmark too slow: {elapsed:.2f}s"

        # Also verify conservation after the benchmark run
        result = check_mass_conservation(engine)
        assert result.passed, f"Mass error: {result.absolute_error:.2e}"

"""Tests for CityGridGenerator and CityGrid — terrain, population, drainage."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Ensure the src/ tree is importable without an editable install.
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from flowshield.data.generator import CityGridGenerator
from flowshield.data.models import CityGrid
from flowshield.utils.config import SimulationConfig


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_config(seed: int = 42, rows: int = 30, cols: int = 30) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {"terrain": {"seed": seed}, "population": {"seed": seed}, "drainage": {"seed": seed}, "grid": {"height": rows, "width": cols}}
    )


def _generate(seed: int = 42, rows: int = 30, cols: int = 30) -> CityGrid:
    cfg = _make_config(seed=seed, rows=rows, cols=cols)
    gen = CityGridGenerator(cfg)
    return gen.generate()


# ── Seed determinism ─────────────────────────────────────────────────────────

class TestSeedDeterminism:
    """Two identical seeds MUST produce bitwise-identical arrays."""

    def test_same_seed_elevation(self):
        g1 = _generate(seed=42)
        g2 = _generate(seed=42)
        np.testing.assert_array_equal(g1.elevation, g2.elevation)

    def test_same_seed_population(self):
        g1 = _generate(seed=42)
        g2 = _generate(seed=42)
        np.testing.assert_array_equal(g1.population, g2.population)

    def test_same_seed_drainage(self):
        g1 = _generate(seed=42)
        g2 = _generate(seed=42)
        np.testing.assert_array_equal(g1.drainage_capacity, g2.drainage_capacity)

    def test_same_seed_water_depth(self):
        g1 = _generate(seed=42)
        g2 = _generate(seed=42)
        np.testing.assert_array_equal(g1.water_depth, g2.water_depth)


# ── Distinct seeds → different topologies ─────────────────────────────────────

class TestDistinctSeeds:
    """Different seeds must produce different grids."""

    def test_different_seed_elevation(self):
        g1 = _generate(seed=42)
        g2 = _generate(seed=99)
        assert not np.array_equal(g1.elevation, g2.elevation)

    def test_different_seed_population(self):
        g1 = _generate(seed=42)
        g2 = _generate(seed=99)
        assert not np.array_equal(g1.population, g2.population)

    def test_different_seed_drainage(self):
        g1 = _generate(seed=42)
        g2 = _generate(seed=99)
        assert not np.array_equal(g1.drainage_capacity, g2.drainage_capacity)


# ── Valley / downhill gradient ───────────────────────────────────────────────

class TestValleyGradient:
    """The central valley corridor must have lower mean elevation than the
    outer boundary cells, proving a realistic downhill drainage path exists.
    """

    def test_valley_lower_than_boundaries(self):
        grid = _generate(seed=42, rows=50, cols=50)
        elev = grid.elevation

        # Central vertical strip (columns 40-60 % of width)
        c_lo = int(0.40 * grid.cols)
        c_hi = int(0.60 * grid.cols)
        valley_mean = elev[:, c_lo:c_hi].mean()

        # Outer boundary: first & last 10 % of columns
        edge = max(1, int(0.10 * grid.cols))
        left_mean = elev[:, :edge].mean()
        right_mean = elev[:, -edge:].mean()
        boundary_mean = (left_mean + right_mean) / 2.0

        assert valley_mean < boundary_mean, (
            f"Valley mean ({valley_mean:.4f}) should be lower than "
            f"boundary mean ({boundary_mean:.4f})"
        )

    def test_valley_lower_on_multiple_seeds(self):
        """Ensure the valley-is-lower property is robust, not seed-lucky."""
        for seed in [1, 7, 42, 100, 999]:
            grid = _generate(seed=seed, rows=40, cols=40)
            elev = grid.elevation
            c_lo = int(0.40 * grid.cols)
            c_hi = int(0.60 * grid.cols)
            valley_mean = elev[:, c_lo:c_hi].mean()

            edge = max(1, int(0.10 * grid.cols))
            boundary_mean = (elev[:, :edge].mean() + elev[:, -edge:].mean()) / 2.0
            assert valley_mean < boundary_mean, f"Failed for seed={seed}"


# ── Elevation boundary checks ────────────────────────────────────────────────

class TestElevationBounds:
    """Elevation must be non-negative and finite."""

    def test_no_negative_elevation(self):
        grid = _generate(seed=42)
        assert (grid.elevation >= 0).all()

    def test_elevation_finite(self):
        grid = _generate(seed=42)
        assert np.isfinite(grid.elevation).all()

    def test_elevation_dtype(self):
        grid = _generate(seed=42)
        assert grid.elevation.dtype == np.float64

    def test_min_elevation_is_zero(self):
        """Generator shifts so minimum is exactly zero."""
        grid = _generate(seed=42)
        assert grid.elevation.min() == pytest.approx(0.0, abs=1e-12)


# ── Population boundary checks ──────────────────────────────────────────────

class TestPopulationBounds:
    """Population cells must be non-negative and sum to total."""

    def test_no_negative_population(self):
        grid = _generate(seed=42)
        assert (grid.population >= 0).all()

    def test_population_sums_to_total(self):
        total = 100_000
        cfg = _make_config(seed=42)
        cfg.population.mean = total / (cfg.grid.width * cfg.grid.height)
        gen = CityGridGenerator(cfg)
        grid = gen.generate()
        assert abs(grid.population.sum() - total) < total * 0.05

    def test_custom_total_population(self):
        total = 50_000
        cfg = _make_config(seed=42)
        cfg.population.mean = total / (cfg.grid.width * cfg.grid.height)
        gen = CityGridGenerator(cfg)
        grid = gen.generate()
        assert abs(grid.population.sum() - total) < total * 0.05

    def test_population_dtype(self):
        grid = _generate(seed=42)
        assert grid.population.dtype == np.int32

    def test_population_clusters_in_valleys(self):
        """Mean population density should be higher in the central valley
        than on the elevated boundary columns.
        """
        grid = _generate(seed=42, rows=50, cols=50)
        c_lo = int(0.40 * grid.cols)
        c_hi = int(0.60 * grid.cols)
        valley_pop_density = grid.population[:, c_lo:c_hi].mean()

        edge = max(1, int(0.10 * grid.cols))
        boundary_pop_density = (
            grid.population[:, :edge].mean() + grid.population[:, -edge:].mean()
        ) / 2.0

        assert valley_pop_density > boundary_pop_density, (
            f"Valley pop density ({valley_pop_density:.2f}) should exceed "
            f"boundary density ({boundary_pop_density:.2f})"
        )


# ── Drainage boundary checks ────────────────────────────────────────────────

class TestDrainageBounds:
    """Drainage capacity must be non-negative and spatially realistic."""

    def test_no_negative_drainage(self):
        grid = _generate(seed=42)
        assert (grid.drainage_capacity >= 0).all()

    def test_drainage_finite(self):
        grid = _generate(seed=42)
        assert np.isfinite(grid.drainage_capacity).all()

    def test_drainage_dtype(self):
        grid = _generate(seed=42)
        assert grid.drainage_capacity.dtype == np.float64

    def test_drainage_higher_near_valley(self):
        """Central drainage corridor should have higher capacity."""
        grid = _generate(seed=42, rows=50, cols=50)
        c_lo = int(0.40 * grid.cols)
        c_hi = int(0.60 * grid.cols)
        valley_drain = grid.drainage_capacity[:, c_lo:c_hi].mean()

        edge = max(1, int(0.10 * grid.cols))
        boundary_drain = (
            grid.drainage_capacity[:, :edge].mean()
            + grid.drainage_capacity[:, -edge:].mean()
        ) / 2.0

        assert valley_drain > boundary_drain, (
            f"Valley drainage ({valley_drain:.6f}) should exceed "
            f"boundary drainage ({boundary_drain:.6f})"
        )


# ── Water depth initialisation ──────────────────────────────────────────────

class TestWaterDepthInit:
    """Water depth must be initialised to zero."""

    def test_water_depth_all_zero(self):
        grid = _generate(seed=42)
        np.testing.assert_array_equal(grid.water_depth, 0.0)

    def test_water_depth_dtype(self):
        grid = _generate(seed=42)
        assert grid.water_depth.dtype == np.float64


# ── Shape / grid size ────────────────────────────────────────────────────────

class TestGridShapes:
    """All arrays must match the configured grid dimensions."""

    @pytest.mark.parametrize("rows,cols", [(10, 10), (30, 30), (50, 80), (100, 100)])
    def test_shape_matches_config(self, rows: int, cols: int):
        grid = _generate(rows=rows, cols=cols)
        expected = (rows, cols)
        assert grid.elevation.shape == expected
        assert grid.population.shape == expected
        assert grid.drainage_capacity.shape == expected
        assert grid.water_depth.shape == expected

    def test_rows_cols_properties(self):
        grid = _generate(rows=25, cols=40)
        assert grid.rows == 25
        assert grid.cols == 40


# ── Validator helper ─────────────────────────────────────────────────────────

class TestValidateHelper:
    """CityGridGenerator.validate() should pass on valid grids and raise on bad ones."""

    def test_valid_grid_passes(self):
        grid = _generate(seed=42)
        CityGridGenerator.validate(grid)  # should not raise

    def test_negative_elevation_fails(self):
        grid = _generate(seed=42)
        grid.elevation[0, 0] = -1.0
        with pytest.raises(ValueError, match="negative"):
            CityGridGenerator.validate(grid)

    def test_negative_population_fails(self):
        grid = _generate(seed=42)
        grid.population[0, 0] = -1
        with pytest.raises(ValueError, match="negative"):
            CityGridGenerator.validate(grid)

    def test_negative_drainage_fails(self):
        grid = _generate(seed=42)
        grid.drainage_capacity[0, 0] = -0.001
        with pytest.raises(ValueError, match="negative"):
            CityGridGenerator.validate(grid)


# ── CityGrid dataclass edge cases ───────────────────────────────────────────

class TestCityGridDataclass:
    """Direct construction edge-cases for CityGrid."""

    def test_mismatched_shapes_raise(self):
        with pytest.raises(ValueError, match="does not match"):
            CityGrid(
                elevation=np.zeros((10, 10)),
                population=np.zeros((10, 12), dtype=np.int32),
                drainage_capacity=np.zeros((10, 10)),
            )

    def test_custom_water_depth_accepted(self):
        wd = np.ones((5, 5), dtype=np.float64) * 0.05
        grid = CityGrid(
            elevation=np.zeros((5, 5)),
            population=np.zeros((5, 5), dtype=np.int32),
            drainage_capacity=np.zeros((5, 5)),
            water_depth=wd,
        )
        np.testing.assert_array_equal(grid.water_depth, 0.05)

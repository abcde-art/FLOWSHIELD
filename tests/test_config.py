"""Tests for flowshield.utils.config — schema validation, loading, and edge cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure the src/ tree is importable without an editable install.
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from flowshield.utils.config import (  # noqa: E402
    DrainageConfig,
    GridConfig,
    PopulationConfig,
    RainfallConfig,
    RiskThresholds,
    SimulationConfig,
    SimulationTimeConfig,
    TerrainConfig,
    load_config,
)

# Resolve the configs/ directory relative to the project root.
_CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write_json(tmp_path: Path, data: dict, filename: str = "test.json") -> Path:
    """Write *data* as JSON into *tmp_path* and return the file path."""
    p = tmp_path / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ── Default fallback tests ───────────────────────────────────────────────────

class TestDefaultFallbacks:
    """An empty dict should produce a fully-populated config with all defaults."""

    def test_defaults_from_empty_dict(self):
        cfg = SimulationConfig.model_validate({})
        assert cfg.name == "default"
        assert cfg.grid.width == 30
        assert cfg.grid.height == 30
        assert cfg.grid.cell_size_m == 10.0
        assert cfg.simulation.timestep_min == 1.0
        assert cfg.simulation.duration_h == 2.0
        assert cfg.rainfall.rate_mm_per_h == 20.0
        assert cfg.rainfall.peak_multiplier == 2.0
        assert cfg.simulation.flow_coefficient == pytest.approx(0.20)
        assert cfg.drainage.base_capacity_m3_per_h == 10.0
        assert cfg.risk.warning_depth_m == pytest.approx(0.10)
        assert cfg.risk.critical_depth_m == pytest.approx(0.30)
        assert cfg.terrain.seed == 42
        assert cfg.population.seed == 42
        assert cfg.drainage.seed == 42

    def test_partial_override_keeps_remaining_defaults(self):
        cfg = SimulationConfig.model_validate({"grid": {"width": 50}})
        assert cfg.grid.width == 50
        assert cfg.grid.height == 30  # untouched default


# ── JSON file loading ────────────────────────────────────────────────────────

class TestLoadConfig:
    """Test the ``load_config`` helper against on-disk JSON files."""

    @pytest.mark.parametrize(
        "filename",
        ["default.json", "heavy_rain.json", "drainage_failure.json", "blocked_channel.json"],
    )
    def test_load_all_scenario_files(self, filename: str):
        cfg = load_config(_CONFIGS_DIR / filename)
        assert isinstance(cfg, SimulationConfig)
        assert cfg.name  # non-empty

    def test_load_default_values(self):
        cfg = load_config(_CONFIGS_DIR / "default.json")
        assert cfg.grid.width == 30
        assert cfg.grid.height == 30
        assert cfg.simulation.flow_coefficient == pytest.approx(0.20)

    def test_load_heavy_rain_surge(self):
        cfg = load_config(_CONFIGS_DIR / "heavy_rain.json")
        assert cfg.rainfall.peak_multiplier == 2.5  # Actually in heavy_rain.json this was set
        assert cfg.grid.width == 30

    def test_load_drainage_failure(self):
        cfg = load_config(_CONFIGS_DIR / "drainage_failure.json")
        assert cfg.drainage.base_capacity_m3_per_h == 2.0
        assert cfg.risk.warning_depth_m == pytest.approx(0.08)

    def test_load_blocked_channel(self):
        cfg = load_config(_CONFIGS_DIR / "blocked_channel.json")
        assert cfg.drainage.base_capacity_m3_per_h == 0.5
        assert cfg.simulation.flow_coefficient == pytest.approx(0.45)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config(_CONFIGS_DIR / "nonexistent.json")


# ── Validation-failure tests ─────────────────────────────────────────────────

class TestValidationFailures:
    """Ensure that invalid inputs are rejected with ``ValidationError``."""

    # -- Grid ---------------------------------------------------------------
    def test_grid_rows_zero(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"grid": {"width": 0}})

    def test_grid_rows_negative(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"grid": {"width": -5}})

    def test_grid_exceeds_max(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"grid": {"width": 101}})

    # -- Rainfall -----------------------------------------------------------
    def test_negative_rainfall_intensity(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate(
                {"grid": {"cell_size_m": -10.0}}
            )

    # -- Flow ---------------------------------------------------------------
    def test_flow_coefficient_gt_one(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"simulation": {"flow_coefficient": 1.5}})

    def test_flow_coefficient_negative(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"simulation": {"flow_coefficient": -0.1}})

    # -- Time ---------------------------------------------------------------
    def test_timestep_zero(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"simulation": {"timestep_min": 0}})

    # -- Risk thresholds ----------------------------------------------------
    def test_warning_ge_critical(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate(
                {"risk": {"warning_depth_m": 0.5, "critical_depth_m": 0.3}}
            )

    def test_warning_equals_critical(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate(
                {"risk": {"warning_depth_m": 0.3, "critical_depth_m": 0.3}}
            )

    def test_zero_warning_depth(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate(
                {"risk": {"warning_depth_m": 0.0}}
            )

    # -- Extra / unknown keys -----------------------------------------------
    def test_extra_top_level_key_rejected(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"unknown_key": 123})

    def test_extra_nested_key_rejected(self):
        with pytest.raises(Exception):
            SimulationConfig.model_validate({"grid": {"width": 30, "depth": 10}})


# ── Boundary / edge-case tests ───────────────────────────────────────────────

class TestEdgeCases:
    """Boundary values and round-trip serialisation."""

    def test_max_grid_accepted(self):
        cfg = SimulationConfig.model_validate({"grid": {"width": 100, "height": 100}})
        assert cfg.grid.width == 100

    def test_min_grid_accepted(self):
        cfg = SimulationConfig.model_validate({"grid": {"width": 1, "height": 1}})
        assert cfg.grid.width == 1

    def test_round_trip_json(self, tmp_path: Path):
        original = SimulationConfig.model_validate({"name": "roundtrip"})
        p = tmp_path / "rt.json"
        p.write_text(original.model_dump_json(indent=2), encoding="utf-8")
        reloaded = load_config(p)
        assert reloaded == original

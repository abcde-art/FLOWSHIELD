"""Pre-packaged FLOWSHIELD simulation scenarios.

Each scenario function constructs a :class:`SimulationConfig`, generates a
:class:`CityGrid`, wires up the :class:`SimulationEngine` (with an optional
drainage blockage mask), and returns the **completed** engine.  All scenarios
run through the identical engine code path — only configuration parameters
and blockage masks differ.

Available scenarios
-------------------
* ``normal_rainfall``         — baseline moderate rainfall event.
* ``cloudburst_surge``        — extreme rainfall with a mid-event surge.
* ``pump_drainage_failure``   — drainage infrastructure degraded system-wide.
* ``channel_blockage``        — heavy rain with drainage blocked in the
  central valley corridor.


Source References:
- [REF-001] Python standard library
- [REF-002] NumPy documentation
- [REF-003] Pydantic documentation

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

from flowshield.data.generator import CityGridGenerator
from flowshield.data.models import CityGrid
from flowshield.simulation.engine import SimulationEngine
from flowshield.utils.config import SimulationConfig


# ── Scenario builders ────────────────────────────────────────────────────────

def _build(
    overrides: dict,
    blockage_mask_fn=None,
) -> Tuple[SimulationConfig, CityGrid, Optional[np.ndarray]]:
    """Internal helper: build config → grid → optional blockage mask."""
    if "terrain" not in overrides: overrides["terrain"] = {}
    overrides["terrain"]["seed"] = overrides.get("terrain", {}).get("seed", 42)
    if "population" not in overrides: overrides["population"] = {}
    overrides["population"]["seed"] = overrides.get("population", {}).get("seed", 42)
    if "drainage" not in overrides: overrides["drainage"] = {}
    overrides["drainage"]["seed"] = overrides.get("drainage", {}).get("seed", 42)
    cfg = SimulationConfig.model_validate(overrides)
    gen = CityGridGenerator(cfg)
    grid = gen.generate()
    mask = blockage_mask_fn(grid) if blockage_mask_fn else None
    return cfg, grid, mask


def _run(overrides: dict, blockage_mask_fn=None) -> SimulationEngine:
    """Build and fully execute a scenario."""
    cfg, grid, mask = _build(overrides, blockage_mask_fn)
    engine = SimulationEngine(cfg, grid, blockage_mask=mask)
    engine.run()
    return engine


# ── Public scenario runners ──────────────────────────────────────────────────

def normal_rainfall() -> SimulationEngine:
    """Baseline scenario: moderate 20 mm/hr rainfall for 60 min on a 30x30 grid."""
    return _run({
        "name": "Normal Rainfall",
        "grid": {"height": 30, "width": 30},
                "rainfall": {
            "rate_mm_per_h": 20,
            "duration_h": 1,
            
        },
        "simulation": {"timestep_min": 1, "duration_h": 2, "flow_coefficient": 0.20},
        "drainage": {"base_capacity_m3_per_h": 10},
        "risk": {"warning_depth_m": 0.10, "critical_depth_m": 0.30},
        
    })


def cloudburst_surge() -> SimulationEngine:
    """Extreme cloudburst: 60 mm/hr base with a 2.5x surge at minute 30."""
    return _run({
        "name": "Cloudburst Surge",
        "grid": {"height": 30, "width": 30},
                "rainfall": {
            "rate_mm_per_h": 60,
            "duration_h": 1.5,
            
            "peak_time_fraction": 0.5,
            "peak_multiplier": 2.5,
        },
        "simulation": {"timestep_min": 1, "duration_h": 2, "flow_coefficient": 0.35},
        "drainage": {"base_capacity_m3_per_h": 10},
        "risk": {"warning_depth_m": 0.10, "critical_depth_m": 0.30},
        
    })


def pump_drainage_failure() -> SimulationEngine:
    """Drainage infrastructure largely non-functional (2 mm/hr capacity)."""
    return _run({
        "name": "Pump/Drainage Failure",
        "grid": {"height": 30, "width": 30},
                "rainfall": {
            "rate_mm_per_h": 25,
            "duration_h": 1,
            
        },
        "simulation": {"timestep_min": 1, "duration_h": 2, "flow_coefficient": 0.20},
        "drainage": {"base_capacity_m3_per_h": 2},
        "risk": {"warning_depth_m": 0.08, "critical_depth_m": 0.20},
        
    })


def _valley_blockage_mask(grid: CityGrid) -> np.ndarray:
    """Block drainage in the central 20 % of columns (valley corridor)."""
    rows, cols = grid.shape
    mask = np.ones((rows, cols), dtype=np.float64)
    c_lo = int(0.40 * cols)
    c_hi = int(0.60 * cols)
    mask[:, c_lo:c_hi] = 0.0  # fully blocked
    return mask


def channel_blockage() -> SimulationEngine:
    """Heavy rain with the central drainage channel completely blocked."""
    return _run(
        {
            "name": "Central Valley Channel Blockage",
            "grid": {"height": 30, "width": 30},
                        "rainfall": {
                "rate_mm_per_h": 40,
                "duration_h": 1.25,
                
                "peak_time_fraction": 0.26666,
                "peak_multiplier": 3.0,
            },
            "simulation": {"timestep_min": 1, "duration_h": 2, "flow_coefficient": 0.45},
            "drainage": {"base_capacity_m3_per_h": 10},
            "risk": {"warning_depth_m": 0.05, "critical_depth_m": 0.15},
            
        },
        blockage_mask_fn=_valley_blockage_mask,
    )


# ── Registry for programmatic access ─────────────────────────────────────────

SCENARIO_REGISTRY: Dict[str, callable] = {
    "Normal Rainfall": normal_rainfall,
    "Cloudburst Surge": cloudburst_surge,
    "Pump/Drainage Failure": pump_drainage_failure,
    "Central Valley Channel Blockage": channel_blockage,
}


def run_scenario(name: str) -> SimulationEngine:
    """Look up and execute a named scenario.

    Parameters
    ----------
    name:
        One of the keys in :data:`SCENARIO_REGISTRY`.

    Returns
    -------
    SimulationEngine
        The completed engine with full audit trail.

    Raises
    ------
    KeyError
        If *name* is not a registered scenario.
    """
    try:
        builder = SCENARIO_REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(SCENARIO_REGISTRY))
        raise KeyError(f"Unknown scenario '{name}'. Available: {available}") from None
    return builder()

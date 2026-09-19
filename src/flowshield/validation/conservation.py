"""Mass-conservation and physical sanity checks for FLOWSHIELD simulations.

Three invariants are enforced:

1. **Mass conservation** — the total water in the system must equal
   ``initial_water + cumulative_rain − cumulative_drainage`` to within a
   configurable tolerance.
2. **Non-negativity** — water depth must never drop below zero in any cell.
3. **No uphill gravity inflow** — a dry, lower-elevation cell must not
   spontaneously push water into a higher-elevation neighbour.


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

from dataclasses import dataclass

import numpy as np

from flowshield.data.models import CityGrid
from flowshield.simulation.engine import SimulationEngine


@dataclass
class ConservationResult:
    """Result of a mass-conservation check."""

    passed: bool
    expected_volume: float
    actual_volume: float
    absolute_error: float


def check_mass_conservation(
    engine: SimulationEngine,
    tolerance: float = 1e-5,
) -> ConservationResult:
    """Verify that total water volume is consistent with rain/drain ledger.

    Parameters
    ----------
    engine:
        A :class:`SimulationEngine` that has been (partially or fully) run.
    tolerance:
        Maximum acceptable absolute error (metres of cumulative depth).

    Returns
    -------
    ConservationResult
    """
    expected = (
        engine.initial_water_volume
        + engine.audit.cumulative_rain
        - engine.audit.cumulative_drainage
    )
    actual = float(engine.grid.water_depth.sum())
    error = abs(expected - actual)
    return ConservationResult(
        passed=error < tolerance,
        expected_volume=expected,
        actual_volume=actual,
        absolute_error=error,
    )


def check_non_negative_water(grid: CityGrid) -> bool:
    """Return ``True`` if no cell has negative water depth."""
    return bool((grid.water_depth >= 0.0).all())


def check_no_uphill_gravity_inflow(
    elevation: np.ndarray,
    water_depth_before: np.ndarray,
    water_depth_after: np.ndarray,
) -> bool:
    """Verify that dry lower-terrain cells did not push water uphill.

    For every cell that was **dry** (``water_depth == 0``) *before* the flow
    step, check that no neighbour with **higher** elevation gained water
    solely from that dry cell.  In practice we verify the contrapositive:
    a cell whose elevation exceeds *all* of its neighbours' hydraulic heads
    (``elevation + water_depth``) should not have gained water.

    Parameters
    ----------
    elevation:
        Terrain elevation (m).
    water_depth_before:
        Water depth grid *before* the lateral flow step.
    water_depth_after:
        Water depth grid *after* the lateral flow step.

    Returns
    -------
    bool
        ``True`` if no uphill violation was detected.
    """
    H_before = elevation + water_depth_before  # neighbours' heads

    rows, cols = elevation.shape

    # For each cell, compute the maximum neighbour head (D4).
    max_neighbour_head = np.full_like(elevation, -np.inf)

    if rows > 1:
        max_neighbour_head[:-1, :] = np.maximum(
            max_neighbour_head[:-1, :], H_before[1:, :]
        )
        max_neighbour_head[1:, :] = np.maximum(
            max_neighbour_head[1:, :], H_before[:-1, :]
        )
    if cols > 1:
        max_neighbour_head[:, :-1] = np.maximum(
            max_neighbour_head[:, :-1], H_before[:, 1:]
        )
        max_neighbour_head[:, 1:] = np.maximum(
            max_neighbour_head[:, 1:], H_before[:, :-1]
        )

    # Cells whose bare elevation already exceeds every neighbour's head
    # should never *gain* water from the flow step.
    unreachable = elevation > max_neighbour_head
    gained_water = water_depth_after > water_depth_before + 1e-15

    violations = unreachable & gained_water
    return bool(not violations.any())


def water_balance(result_or_engine):
    if hasattr(result_or_engine, 'cumulative_rain'):
        err = (result_or_engine.cumulative_rain - result_or_engine.cumulative_drainage)
        if len(result_or_engine.total_water_volume_history) > 0:
             err -= result_or_engine.total_water_volume_history[-1]
        return {"balance_error_m3": err}
    else:
        res = check_mass_conservation(result_or_engine)
        return {"balance_error_m3": res.absolute_error}

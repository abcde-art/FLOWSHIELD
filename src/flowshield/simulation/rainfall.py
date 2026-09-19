"""Rainfall input module.

Computes per-cell rainfall depth (in **metres**) at each simulation timestep,
supporting constant base intensity, a timed surge interval, and correct
mm → m unit conversion.


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

import numpy as np

from flowshield.utils.config import SimulationConfig


def compute_rainfall(
    config: SimulationConfig,
    timestep_index: int,
    grid_shape: tuple[int, int],
) -> np.ndarray:
    """Return the rainfall depth (m) added to every cell at *timestep_index*.

    Parameters
    ----------
    config:
        Validated simulation configuration.
    timestep_index:
        Zero-based timestep counter (``t = 0, 1, 2, …``).
    grid_shape:
        ``(rows, cols)`` shape of the simulation grid.

    Returns
    -------
    np.ndarray[float64]
        Uniform rainfall depth array in **metres** for this timestep.
        Returns all-zeros if the rainfall event has ended.
    """
    dt_min = config.simulation.timestep_min
    current_minute = timestep_index * dt_min

    # No rain once past the rainfall duration window.
    if current_minute >= (config.rainfall.duration_h * 60):
        return np.zeros(grid_shape, dtype=np.float64)

    intensity_mm_hr = config.rainfall.rate_mm_per_h

    # Apply surge multiplier if enabled and within the surge window.
    if (
        (config.rainfall.peak_multiplier > 1.0)
        and (config.rainfall.peak_time_fraction * config.simulation.duration_h * 60) is not None
        and current_minute >= (config.rainfall.peak_time_fraction * config.simulation.duration_h * 60)
    ):
        intensity_mm_hr *= config.rainfall.peak_multiplier  # type: ignore[operator]

    # Convert mm/hr → metres/timestep:
    #   mm/hr × (1 m / 1000 mm) × (dt_min / 60 min/hr)
    rainfall_m = (intensity_mm_hr / 1000.0) * (dt_min / 60.0)

    return np.full(grid_shape, rainfall_m, dtype=np.float64)

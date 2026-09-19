"""Linear-regression time-to-critical forecaster.

Estimates how many minutes remain before a cell reaches the critical flood
depth by fitting a least-squares line through the most recent *N* depth
readings and extrapolating.

Status semantics
----------------
* ``"CRITICAL NOW"``     — the cell is already at or above the critical
  threshold.
* ``"NOT EXPECTED"``     — the depth trend is flat or falling (slope <= 0).
* ``"INSUFFICIENT DATA"``— fewer than *window_size* history entries are
  available for regression.
* ``float``              — estimated minutes until the critical threshold is
  reached (positive, finite).


Source References:
- [REF-002] NumPy documentation
- [REF-005] Linear least squares regression (np.polyfit)

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.
"""

from __future__ import annotations

from typing import Sequence, Union

import numpy as np


# Sentinel strings returned when a numeric forecast is not meaningful.
CRITICAL_NOW = "CRITICAL NOW"
NOT_EXPECTED = "NOT EXPECTED"
INSUFFICIENT_DATA = "INSUFFICIENT DATA"


def predict_time_to_critical(
    water_history: Sequence[float],
    current_depth: float,
    critical_threshold: float,
    timestep_minutes: float = 1.0,
    window_size: int = 5,
) -> Union[str, float]:
    """Forecast minutes until *current_depth* reaches *critical_threshold*.

    Parameters
    ----------
    water_history:
        Sequence of past depth values (one per elapsed timestep), ordered
        from oldest to newest.  The most recent entry should correspond to
        *current_depth* or the step immediately before it.
    current_depth:
        Latest water depth reading (m).
    critical_threshold:
        Depth (m) defining the CRITICAL boundary.
    timestep_minutes:
        Duration of each simulation timestep in minutes.
    window_size:
        Number of most-recent entries used for regression (default 5).

    Returns
    -------
    str | float
        One of the three status strings or a positive float giving the
        estimated minutes to critical.
    """
    # ── Already critical ──────────────────────────────────────────────────
    if current_depth >= critical_threshold:
        return CRITICAL_NOW

    # ── Insufficient history ──────────────────────────────────────────────
    if len(water_history) < window_size:
        return INSUFFICIENT_DATA

    # ── Linear regression over the last *window_size* entries ─────────────
    recent = np.asarray(water_history[-window_size:], dtype=np.float64)
    t = np.arange(window_size, dtype=np.float64)  # timestep indices

    # Slope *a* in depth-per-timestep via np.polyfit (degree 1).
    coeffs = np.polyfit(t, recent, deg=1)
    a_per_step = coeffs[0]  # slope (depth / timestep)

    # ── Flat or falling → critical not expected ───────────────────────────
    if a_per_step <= 1e-12:
        return NOT_EXPECTED

    # ── Extrapolate ───────────────────────────────────────────────────────
    steps_remaining = (critical_threshold - current_depth) / a_per_step
    return float(steps_remaining * timestep_minutes)


forecast_time_to_critical = predict_time_to_critical

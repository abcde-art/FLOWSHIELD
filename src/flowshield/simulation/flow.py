"""Vectorised D4 lateral gravity-flow module.

Implements a single-pass, array-sliced D4 (von Neumann) flow algorithm:

1. Compute **hydraulic head**  ``H = elevation + water_depth``.
2. For each of the 4 cardinal directions, calculate head differences via
   array slicing (no Python for-loops over cells).
3. Potential outflow per direction = ``flow_coefficient × max(ΔH, 0)``.
4. Scale all outflows so that total outflow from any cell never exceeds its
   current ``water_depth`` (mass-safe constraint).
5. Accumulate inflows from neighbours and return the **net flow** array.

Boundary handling: cells at grid edges have zero outflow in the direction
of the boundary (no-flow / reflective).  ``np.roll`` is never used, so
wrap-around artefacts cannot occur.


Source References:
- [REF-002] NumPy documentation
- [REF-004] D4 / von Neumann cellular automaton flow routing approximation
- [REF-007] Hydrological mass conservation principles

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.
"""

from __future__ import annotations

import numpy as np


def compute_flow(
    elevation: np.ndarray,
    water_depth: np.ndarray,
    flow_coefficient: float,
) -> np.ndarray:
    """Compute the net lateral water redistribution for one timestep.

    Parameters
    ----------
    elevation:
        Terrain elevation grid (m), shape ``(R, C)``.
    water_depth:
        Current standing water depth (m), shape ``(R, C)``.
    flow_coefficient:
        Fraction of head difference that is transferred per timestep (0–1).

    Returns
    -------
    np.ndarray[float64]
        ``net_flow`` array (m) with the same shape.  Positive values mean a
        cell *gains* water; negative values mean it *loses* water.
        ``net_flow.sum() ≈ 0`` (exact to floating-point precision).
    """
    H = elevation + water_depth  # hydraulic head

    # ── Potential outflow in each cardinal direction ──────────────────────
    #
    # out_X[i, j] = water that cell (i, j) *wants* to send in direction X.
    # Boundary rows / columns are left at zero (initialised below).

    out_n = np.zeros_like(H)
    out_s = np.zeros_like(H)
    out_e = np.zeros_like(H)
    out_w = np.zeros_like(H)

    # North: cell (i, j) → (i−1, j)   for i ∈ [1, R)
    out_n[1:, :] = np.maximum(H[1:, :] - H[:-1, :], 0.0)

    # South: cell (i, j) → (i+1, j)   for i ∈ [0, R−1)
    out_s[:-1, :] = np.maximum(H[:-1, :] - H[1:, :], 0.0)

    # East:  cell (i, j) → (i, j+1)   for j ∈ [0, C−1)
    out_e[:, :-1] = np.maximum(H[:, :-1] - H[:, 1:], 0.0)

    # West:  cell (i, j) → (i, j−1)   for j ∈ [1, C)
    out_w[:, 1:] = np.maximum(H[:, 1:] - H[:, :-1], 0.0)

    # Apply flow coefficient
    out_n *= flow_coefficient
    out_s *= flow_coefficient
    out_e *= flow_coefficient
    out_w *= flow_coefficient

    # ── Outflow cap: total outflow ≤ water_depth ─────────────────────────
    total_out = out_n + out_s + out_e + out_w

    scale = np.ones_like(H)
    active = total_out > 1e-15  # avoid division by zero
    scale[active] = np.minimum(1.0, water_depth[active] / total_out[active])

    out_n *= scale
    out_s *= scale
    out_e *= scale
    out_w *= scale

    # ── Recompute total outflow after scaling ────────────────────────────
    outflow = out_n + out_s + out_e + out_w

    # ── Accumulate inflows from neighbours ───────────────────────────────
    #
    # Cell (i, j) receives inflow from:
    #   south neighbour (i+1, j) sending north  → out_n[i+1, j]
    #   north neighbour (i−1, j) sending south  → out_s[i−1, j]
    #   west  neighbour (i, j−1) sending east   → out_e[i, j−1]
    #   east  neighbour (i, j+1) sending west   → out_w[i, j+1]

    inflow = np.zeros_like(H)
    inflow[:-1, :] += out_n[1:, :]    # from south neighbour
    inflow[1:, :]  += out_s[:-1, :]   # from north neighbour
    inflow[:, 1:]  += out_e[:, :-1]   # from west neighbour
    inflow[:, :-1] += out_w[:, 1:]    # from east neighbour

    return inflow - outflow

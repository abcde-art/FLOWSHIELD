"""Drainage outflow module.

Removes standing water from the grid according to each cell's drainage
capacity.  Supports per-cell blockage multipliers so that individual cells
or entire sub-regions can be set to zero throughput.


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

from typing import Optional

import numpy as np


def compute_drainage(
    water_depth: np.ndarray,
    drainage_capacity: np.ndarray,
    blockage_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Compute the water volume (m) removed by drainage this timestep.

    Parameters
    ----------
    water_depth:
        Current standing-water depth per cell in metres (≥ 0).
    drainage_capacity:
        Maximum drainage throughput per cell in **metres/timestep** (≥ 0).
    blockage_mask:
        Optional per-cell multiplier array in ``[0, 1]``.
        * ``1.0`` — fully operational (default when *None*).
        * ``0.0`` — fully blocked (zero drainage).
        * Intermediate values model partial blockage.

    Returns
    -------
    np.ndarray[float64]
        Actual water removed (m).  Always ``≤ water_depth`` and
        ``≤ effective_capacity``.
    """
    effective = drainage_capacity if blockage_mask is None else drainage_capacity * blockage_mask
    return np.minimum(water_depth, effective)

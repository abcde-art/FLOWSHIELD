"""Per-cell flood-risk classifier.

Maps water depth to one of three discrete risk levels based on the
configurable thresholds in :class:`~flowshield.utils.config.RiskThresholds`.

Risk levels (integer codes)
---------------------------
* ``SAFE     = 0`` — depth < warning threshold
* ``WARNING  = 1`` — warning threshold <= depth < critical threshold
* ``CRITICAL = 2`` — depth >= critical threshold


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

from enum import IntEnum

import numpy as np


class RiskLevel(IntEnum):
    """Enumerated risk codes matching the integer grid values."""

    SAFE = 0
    WARNING = 1
    CRITICAL = 2


def classify_risk(
    water_depth: np.ndarray,
    warning_threshold: float,
    critical_threshold: float,
) -> np.ndarray:
    """Classify every grid cell into a risk level.

    Parameters
    ----------
    water_depth:
        Current standing water depth (m), shape ``(R, C)``.
    warning_threshold:
        Depth (m) at or above which a cell is classified as WARNING.
    critical_threshold:
        Depth (m) at or above which a cell is classified as CRITICAL.

    Returns
    -------
    np.ndarray[int32]
        Integer risk-level grid with the same shape as *water_depth*.
    """
    risk = np.full(water_depth.shape, RiskLevel.SAFE, dtype=np.int32)
    risk[water_depth >= warning_threshold] = RiskLevel.WARNING
    risk[water_depth >= critical_threshold] = RiskLevel.CRITICAL
    return risk


classify_grid = classify_risk

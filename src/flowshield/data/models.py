"""Domain data-models for FLOWSHIELD simulation state.

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

from dataclasses import dataclass, field
from typing import Tuple

import numpy as np


@dataclass
class CityGrid:
    """Immutable snapshot of a city's spatial data layers.

    All arrays must share the same ``(rows, cols)`` shape.

    Attributes
    ----------
    elevation : np.ndarray[float64]
        Terrain elevation in metres above datum.
    population : np.ndarray[int32]
        Estimated resident count per cell.
    drainage_capacity : np.ndarray[float64]
        Effective drainage capacity in **metres per timestep**.
    water_depth : np.ndarray[float64]
        Current standing water depth in metres (initialised to 0.0).
    """

    elevation: np.ndarray
    population: np.ndarray
    drainage_capacity: np.ndarray
    water_depth: np.ndarray = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # ── dtype enforcement ─────────────────────────────────────────────
        self.elevation = np.asarray(self.elevation, dtype=np.float64)
        self.population = np.asarray(self.population, dtype=np.int32)
        self.drainage_capacity = np.asarray(self.drainage_capacity, dtype=np.float64)

        # ── shape consistency ─────────────────────────────────────────────
        shape = self.elevation.shape
        if self.population.shape != shape:
            raise ValueError(
                f"population shape {self.population.shape} does not match "
                f"elevation shape {shape}"
            )
        if self.drainage_capacity.shape != shape:
            raise ValueError(
                f"drainage_capacity shape {self.drainage_capacity.shape} does not "
                f"match elevation shape {shape}"
            )

        # ── water_depth defaults to zeros ─────────────────────────────────
        if self.water_depth is None:
            self.water_depth = np.zeros(shape, dtype=np.float64)
        else:
            self.water_depth = np.asarray(self.water_depth, dtype=np.float64)
            if self.water_depth.shape != shape:
                raise ValueError(
                    f"water_depth shape {self.water_depth.shape} does not match "
                    f"elevation shape {shape}"
                )

    # ── convenience properties ────────────────────────────────────────────

    @property
    def shape(self) -> Tuple[int, int]:
        """Grid dimensions ``(rows, cols)``."""
        return self.elevation.shape  # type: ignore[return-value]

    @property
    def rows(self) -> int:
        return self.shape[0]

    @property
    def cols(self) -> int:
        return self.shape[1]

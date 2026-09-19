"""Simulation engine — timestep orchestration and audit bookkeeping.

Each timestep follows the update rule:

    ``water(t+1) = water(t) + rain_in − drainage_out + net_lateral_flow``

The engine records per-step and cumulative audit metrics so that
:mod:`flowshield.validation.conservation` can verify mass balance at any
point during or after the run.


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
from typing import List, Optional

import numpy as np

from flowshield.data.models import CityGrid
from flowshield.simulation.drainage import compute_drainage
from flowshield.simulation.flow import compute_flow
from flowshield.simulation.rainfall import compute_rainfall
from flowshield.utils.config import SimulationConfig


@dataclass
class SimulationAudit:
    """Comprehensive per-timestep audit history."""

    rain_added_history: List[float] = field(default_factory=list)
    water_drained_history: List[float] = field(default_factory=list)
    total_water_volume_history: List[float] = field(default_factory=list)

    @property
    def cumulative_rain(self) -> float:
        """Total rainfall volume added across all elapsed timesteps (m³-equiv)."""
        return float(np.sum(self.rain_added_history))

    @property
    def cumulative_drainage(self) -> float:
        """Total drainage volume removed across all elapsed timesteps."""
        return float(np.sum(self.water_drained_history))


class SimulationEngine:
    """Orchestrates the FLOWSHIELD hydrological simulation.

    Parameters
    ----------
    config:
        Validated simulation configuration.
    grid:
        Initial city grid (elevation, population, drainage_capacity,
        water_depth).  ``water_depth`` is mutated **in-place** each step.
    blockage_mask:
        Optional per-cell drainage multiplier ``[0, 1]``.  ``None`` means
        all drains are fully operational.
    """

    def __init__(
        self,
        config: SimulationConfig,
        grid: CityGrid,
        blockage_mask: Optional[np.ndarray] = None,
    ) -> None:
        self.config = config
        self.grid = grid
        self.blockage_mask = blockage_mask

        self.audit = SimulationAudit()
        self.initial_water_volume: float = float(grid.water_depth.sum())

        self._timestep_index: int = 0
        self._num_steps: int = int(
            (config.simulation.duration_h * 60) / config.simulation.timestep_min
        )

    # ── public API ────────────────────────────────────────────────────────

    @property
    def num_steps(self) -> int:
        """Total number of timesteps in the simulation."""
        return self._num_steps

    @property
    def current_step(self) -> int:
        """Zero-based index of the *next* timestep to execute."""
        return self._timestep_index

    @property
    def is_complete(self) -> bool:
        return self._timestep_index >= self._num_steps

    def step(self) -> None:
        """Advance the simulation by one timestep.

        Update order:
        1. Add rainfall.
        2. Remove drainage outflow.
        3. Compute and apply lateral gravity flow.
        4. Clamp water_depth ≥ 0 (numerical safety net).
        5. Record audit metrics.
        """
        wd = self.grid.water_depth

        # 1 ── Rainfall ───────────────────────────────────────────────────
        rain = compute_rainfall(
            self.config, self._timestep_index, self.grid.shape
        )
        wd += rain
        total_rain = float(rain.sum())

        # 2 ── Drainage ───────────────────────────────────────────────────
        drained = compute_drainage(wd, self.grid.drainage_capacity, self.blockage_mask)
        wd -= drained
        total_drained = float(drained.sum())

        # 3 ── Lateral flow ───────────────────────────────────────────────
        net_flow = compute_flow(
            self.grid.elevation, wd, self.config.simulation.flow_coefficient
        )
        wd += net_flow

        # 4 ── Numerical safety clamp ─────────────────────────────────────
        np.clip(wd, 0.0, None, out=wd)

        # 5 ── Audit bookkeeping ──────────────────────────────────────────
        self.audit.rain_added_history.append(total_rain)
        self.audit.water_drained_history.append(total_drained)
        self.audit.total_water_volume_history.append(float(wd.sum()))

        self._timestep_index += 1

    def run(self) -> SimulationAudit:
        """Execute the full simulation and return the audit trail."""
        while not self.is_complete:
            self.step()
        return self.audit

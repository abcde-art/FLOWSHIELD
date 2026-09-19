"""Population impact calculator.

Quantifies how many residents are exposed at each risk level by combining
the risk-classification grid with the population-density grid.


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

from flowshield.risk.classifier import RiskLevel, classify_risk


@dataclass
class PopulationImpact:
    """Aggregated population exposure counts."""

    warning_population: int
    critical_population: int

    @property
    def total_affected(self) -> int:
        """Sum of warning + critical populations."""
        return self.warning_population + self.critical_population


def compute_population_impact(
    water_depth: np.ndarray,
    population: np.ndarray,
    warning_threshold: float,
    critical_threshold: float,
) -> PopulationImpact:
    """Calculate total population at WARNING and CRITICAL risk levels.

    Parameters
    ----------
    water_depth:
        Current standing water depth (m), shape ``(R, C)``.
    population:
        Resident count per cell, shape ``(R, C)``.
    warning_threshold:
        Depth (m) defining the WARNING boundary.
    critical_threshold:
        Depth (m) defining the CRITICAL boundary.

    Returns
    -------
    PopulationImpact
        Counts of exposed (WARNING) and critical populations.
    """
    risk = classify_risk(water_depth, warning_threshold, critical_threshold)

    warning_pop = int(population[risk == RiskLevel.WARNING].sum())
    critical_pop = int(population[risk == RiskLevel.CRITICAL].sum())

    return PopulationImpact(
        warning_population=warning_pop,
        critical_population=critical_pop,
    )

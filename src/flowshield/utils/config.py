"""Configuration schema and loading helpers for FLOWSHIELD simulations.

All simulation parameters are expressed as a Pydantic v2 model so that every
JSON config file is validated on load.  Unknown keys are forbidden to prevent
silent mis-configuration.


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

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# =============================================================================
# Sub-models
# =============================================================================

class GridConfig(BaseModel, extra="forbid"):
    """Spatial grid dimensions."""
    width: int = Field(default=30, ge=1, le=100)
    height: int = Field(default=30, ge=1, le=100)
    cell_size_m: float = Field(default=10.0, gt=0)


class TerrainConfig(BaseModel, extra="forbid"):
    seed: int = Field(default=42)
    base_elevation_m: float = Field(default=10.0)
    amplitude_m: float = Field(default=5.0)
    roughness: float = Field(default=0.5)
    valley_depth_m: float = Field(default=5.0)


class PopulationConfig(BaseModel, extra="forbid"):
    seed: int = Field(default=42)
    mean: float = Field(default=100.0)
    std: float = Field(default=20.0)
    max: float = Field(default=1000.0)


class DrainageConfig(BaseModel, extra="forbid"):
    seed: int = Field(default=42)
    base_capacity_m3_per_h: float = Field(default=10.0)
    variability: float = Field(default=0.1)


class RainfallConfig(BaseModel, extra="forbid"):
    duration_h: float = Field(default=1.0)
    rate_mm_per_h: float = Field(default=20.0)
    peak_multiplier: float = Field(default=2.0)
    peak_time_fraction: float = Field(default=0.5)


class SimulationTimeConfig(BaseModel, extra="forbid"):
    timestep_min: float = Field(default=1.0, gt=0)
    duration_h: float = Field(default=2.0, gt=0)
    flow_coefficient: float = Field(default=0.20, ge=0, le=1.0)


class RiskThresholds(BaseModel, extra="forbid"):
    warning_depth_m: float = Field(default=0.10, gt=0)
    critical_depth_m: float = Field(default=0.30, gt=0)

    @model_validator(mode="after")
    def _warning_lt_critical(self) -> "RiskThresholds":
        if self.warning_depth_m >= self.critical_depth_m:
            raise ValueError(
                f"warning_depth_m ({self.warning_depth_m}) must be less than "
                f"critical_depth_m ({self.critical_depth_m})"
            )
        return self


# =============================================================================
# Root configuration
# =============================================================================

class SimulationConfig(BaseModel, extra="forbid"):
    """Top-level simulation configuration validated against the FLOWSHIELD schema."""
    name: str = Field(default="default", min_length=1)
    grid: GridConfig = Field(default_factory=GridConfig)
    terrain: TerrainConfig = Field(default_factory=TerrainConfig)
    population: PopulationConfig = Field(default_factory=PopulationConfig)
    drainage: DrainageConfig = Field(default_factory=DrainageConfig)
    rainfall: RainfallConfig = Field(default_factory=RainfallConfig)
    simulation: SimulationTimeConfig = Field(default_factory=SimulationTimeConfig)
    risk: RiskThresholds = Field(default_factory=RiskThresholds)


# =============================================================================
# Loading helpers
# =============================================================================

def load_config(path: str | Path) -> SimulationConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return SimulationConfig.model_validate(raw)

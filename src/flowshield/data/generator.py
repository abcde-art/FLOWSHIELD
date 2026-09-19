"""Deterministic synthetic terrain, drainage, and population generator.

Builds a realistic :class:`~flowshield.data.models.CityGrid` that combines:

* **Elevation** ?" planar base slope + Gaussian hill peaks + a central valley
  corridor + smooth sinusoidal noise.  No pure white noise.
* **Population** ?" density inversely correlated with elevation so that
  settlements cluster in valleys (typical of urban flood-plain development).
* **Drainage capacity** ?" baseline capacity from config, spatially modulated
  so that cells near the valley corridor have higher drainage throughput.

Everything is seeded from a single ``np.random.Generator`` for full
deterministic reproducibility.


Source References:
- [REF-002] NumPy documentation
- [REF-006] Synthetic terrain generation mathematics

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.

Dataset:
Synthetic FLOWSHIELD-generated data. No external dataset used.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from flowshield.data.models import CityGrid
from flowshield.utils.config import SimulationConfig

# =============================================================================
# Generator
# =============================================================================

class CityGridGenerator:
    """Generates a synthetic city grid from a :class:`SimulationConfig`."""

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.rows = config.grid.height
        self.cols = config.grid.width

    def generate(self) -> CityGrid:
        """Build and return a fully-initialised :class:`CityGrid`."""
        elevation = self._generate_elevation()
        population = self._generate_population(elevation)
        drainage = self._generate_drainage(elevation)
        return CityGrid(
            elevation=elevation,
            population=population,
            drainage_capacity=drainage,
        )

    def _generate_elevation(self) -> np.ndarray:
        rng = np.random.default_rng(self.config.terrain.seed)
        rows, cols = self.rows, self.cols

        y = np.linspace(0, 1, rows)
        x = np.linspace(0, 1, cols)
        xx, yy = np.meshgrid(x, y)

        base_slope = self.config.terrain.base_elevation_m * (1.0 - 0.4 * xx - 0.6 * yy)

        n_hills = rng.integers(2, 4)
        hills = np.zeros((rows, cols), dtype=np.float64)
        for _ in range(n_hills):
            cx = rng.uniform(0.15, 0.85)
            cy = rng.uniform(0.15, 0.85)
            sigma = rng.uniform(0.08, 0.20)
            amplitude = rng.uniform(self.config.terrain.amplitude_m / 2, self.config.terrain.amplitude_m * 1.5)
            hills += amplitude * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2))

        valley_sigma = 0.12
        valley_depth = self.config.terrain.valley_depth_m
        valley = -valley_depth * np.exp(-((xx - 0.5) ** 2) / (2 * valley_sigma**2))

        freq1 = rng.uniform(2.0, 5.0)
        freq2 = rng.uniform(5.0, 10.0)
        amp1 = rng.uniform(self.config.terrain.roughness * 0.5, self.config.terrain.roughness * 1.5)
        amp2 = rng.uniform(self.config.terrain.roughness * 0.2, self.config.terrain.roughness * 0.6)
        noise = (
            amp1 * np.sin(2 * np.pi * freq1 * xx) * np.cos(2 * np.pi * freq1 * yy)
            + amp2 * np.sin(2 * np.pi * freq2 * yy)
        )

        elevation = base_slope + hills + valley + noise
        elevation -= elevation.min()

        return elevation.astype(np.float64)

    def _generate_population(self, elevation: np.ndarray) -> np.ndarray:
        rng = np.random.default_rng(self.config.population.seed)
        rows, cols = self.rows, self.cols
        
        # We need total_population. We approximate based on mean * cells.
        total_population = int(self.config.population.mean * rows * cols)

        max_elev = elevation.max()
        inv_elev = max_elev - elevation + 1e-3

        density_weight = gaussian_filter(inv_elev, sigma=max(1.0, min(rows, cols) / 15.0))
        prob = density_weight / density_weight.sum()

        flat_pop = rng.multinomial(total_population, prob.ravel())
        population = flat_pop.reshape(rows, cols)

        # Apply standard deviation noise
        noise = rng.normal(0, self.config.population.std, (rows, cols))
        population = population + noise
        population = np.clip(population, 0, self.config.population.max)

        return population.astype(np.int32)

    def _generate_drainage(self, elevation: np.ndarray) -> np.ndarray:
        rng = np.random.default_rng(self.config.drainage.seed)
        rows, cols = self.rows, self.cols

        # baseline capacity is in m3/hr, but the original used mm/hr and converted it.
        # "drainage{seed,base_capacity_m3_per_h,variability}"
        # Convert m3/hr to m/timestep.
        # Assuming base_capacity_m3_per_h is per cell, volume = capacity. Area = cell_size_m^2.
        # So rate in m/hr = capacity / Area
        cell_area = self.config.grid.cell_size_m ** 2
        base_m_hr = self.config.drainage.base_capacity_m3_per_h / cell_area
        timestep_hr = self.config.simulation.timestep_min / 60.0
        base_m_per_step = base_m_hr * timestep_hr

        x = np.linspace(0, 1, cols)
        centre_proximity = np.exp(-((x - 0.5) ** 2) / (2 * 0.12**2))
        spatial_factor = 1.0 + centre_proximity[np.newaxis, :]

        variance = 1.0 + self.config.drainage.variability * (rng.standard_normal((rows, cols)))
        variance = gaussian_filter(variance, sigma=max(1.0, min(rows, cols) / 20.0))

        drainage = base_m_per_step * spatial_factor * variance
        np.clip(drainage, 0.0, None, out=drainage)

        return drainage.astype(np.float64)

    @staticmethod
    def validate(grid: CityGrid) -> None:
        if grid.elevation.ndim != 2:
            raise ValueError("elevation must be a 2-D array")
        if (grid.elevation < 0).any():
            raise ValueError("elevation contains negative values")
        if grid.population.ndim != 2:
            raise ValueError("population must be a 2-D array")
        if (grid.population < 0).any():
            raise ValueError("population contains negative values")
        if grid.drainage_capacity.ndim != 2:
            raise ValueError("drainage_capacity must be a 2-D array")
        if (grid.drainage_capacity < 0).any():
            raise ValueError("drainage_capacity contains negative values")

        expected = grid.elevation.shape
        for name, arr in [
            ("population", grid.population),
            ("drainage_capacity", grid.drainage_capacity),
            ("water_depth", grid.water_depth),
        ]:
            if arr.shape != expected:
                raise ValueError(
                    f"{name} shape {arr.shape} does not match "
                    f"elevation shape {expected}"
                )

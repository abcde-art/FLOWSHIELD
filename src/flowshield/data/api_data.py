"""Real-world data fetchers for FLOWSHIELD.

Fetches terrain elevation, weather/rainfall, and population density from
free, no-API-key web services to replace synthetic data generation.

APIs used:
    - Open-Elevation (https://api.open-elevation.com) — terrain elevation
    - Open-Meteo     (https://api.open-meteo.com)     — hourly precipitation
    - WorldPop       (https://wopr.worldpop.org)       — population density

Source References:
- Open-Elevation API documentation
- Open-Meteo API documentation
- WorldPop Open Population Repository

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

import numpy as np
import requests


# ── Timeouts & defaults ──────────────────────────────────────────────────────
_TIMEOUT = 15  # seconds


# =============================================================================
# Elevation — Open-Meteo Elevation API
# =============================================================================

def fetch_elevation(
    lat: float,
    lon: float,
    grid_size: int = 30,
    cell_size_m: float = 10.0,
) -> np.ndarray:
    """Fetch real-world elevation data for a grid centred on (lat, lon).

    Samples a sparse grid of points from the Open-Meteo Elevation API
    (single request, max ~100 points) and bilinearly interpolates to the
    requested grid_size × grid_size resolution.

    Parameters
    ----------
    lat : float
        Centre latitude (decimal degrees).
    lon : float
        Centre longitude (decimal degrees).
    grid_size : int
        Number of rows and columns in the output grid.
    cell_size_m : float
        Spacing between grid points in metres.

    Returns
    -------
    np.ndarray[float64]
        Elevation matrix of shape ``(grid_size, grid_size)``.
    """
    from scipy.interpolate import RegularGridInterpolator

    # Approximate degree offsets for the requested metre spacing.
    d_lat = cell_size_m / 111_320.0
    d_lon = cell_size_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))

    half = grid_size // 2

    # Sample a sparse grid (max 10×10 = 100 points) to stay within a single
    # API call and avoid rate-limiting.
    sample_n = min(grid_size, 10)
    sample_rows = np.linspace(0, grid_size - 1, sample_n, dtype=int)
    sample_cols = np.linspace(0, grid_size - 1, sample_n, dtype=int)

    lats_sparse = []
    lons_sparse = []
    for r in sample_rows:
        for c in sample_cols:
            pt_lat = lat + (r - half) * d_lat
            pt_lon = lon + (c - half) * d_lon
            lats_sparse.append(round(pt_lat, 6))
            lons_sparse.append(round(pt_lon, 6))

    # Single API call with ≤100 points.
    import time
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                "https://api.open-meteo.com/v1/elevation",
                params={
                    "latitude": ",".join(str(x) for x in lats_sparse),
                    "longitude": ",".join(str(x) for x in lons_sparse),
                },
                timeout=_TIMEOUT,
            )
            if resp.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            raw_elevs = data.get("elevation", [])
            break
        except (requests.RequestException, KeyError, ValueError) as exc:
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"Open-Meteo Elevation API request failed: {exc}\n"
                    "Check your internet connection or try again later."
                ) from exc
            time.sleep(1.0)

    sparse_grid = np.array(raw_elevs, dtype=np.float64).reshape(sample_n, sample_n)

    # Bilinearly interpolate from the sparse grid to the full grid.
    if sample_n == grid_size:
        elevation = sparse_grid
    else:
        interp = RegularGridInterpolator(
            (sample_rows.astype(float), sample_cols.astype(float)),
            sparse_grid,
            method="linear",
            bounds_error=False,
            fill_value=None,
        )
        full_rows = np.arange(grid_size, dtype=float)
        full_cols = np.arange(grid_size, dtype=float)
        rr, cc = np.meshgrid(full_rows, full_cols, indexing="ij")
        elevation = interp((rr, cc))

    # Normalise so the minimum is 0 (consistent with synthetic generator).
    elevation -= elevation.min()

    return elevation.astype(np.float64)



# =============================================================================
# Rainfall — Open-Meteo API
# =============================================================================

def fetch_rainfall(
    lat: float,
    lon: float,
    duration_h: float = 2.0,
) -> Dict[str, Any]:
    """Fetch current/forecast precipitation data for a location.

    Queries the Open-Meteo forecast API for hourly precipitation and
    returns a dict of rainfall parameters compatible with FLOWSHIELD's
    config schema.

    Parameters
    ----------
    lat : float
        Latitude (decimal degrees).
    lon : float
        Longitude (decimal degrees).
    duration_h : float
        Desired rainfall duration in hours (used to extract the relevant
        forecast window).

    Returns
    -------
    dict
        Keys: ``rate_mm_per_h``, ``duration_h``, ``peak_multiplier``,
        ``peak_time_fraction``.
    """
    try:
        hours_needed = max(int(math.ceil(duration_h)), 1)
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation",
                "forecast_days": 1,
                "timezone": "auto",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        precip = data["hourly"]["precipitation"]  # list of mm values per hour
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise RuntimeError(
            f"Open-Meteo API request failed: {exc}\n"
            "Check your internet connection or try again later."
        ) from exc

    # Take the first `hours_needed` entries (or all available).
    window = precip[: hours_needed] if len(precip) >= hours_needed else precip

    if not window or all(v is None for v in window):
        # No precipitation forecast — return light default rain.
        return {
            "rate_mm_per_h": 5.0,
            "duration_h": duration_h,
            "peak_multiplier": 1.0,
            "peak_time_fraction": 0.5,
        }

    # Replace None values with 0.
    window = [v if v is not None else 0.0 for v in window]

    avg_rate = sum(window) / len(window) if window else 5.0
    max_rate = max(window) if window else avg_rate

    # Ensure a minimum rate so the simulation is interesting.
    avg_rate = max(avg_rate, 2.0)

    peak_multiplier = max_rate / avg_rate if avg_rate > 0 else 1.0
    peak_multiplier = max(peak_multiplier, 1.0)

    # Find when the peak occurs as a fraction of the window.
    peak_idx = window.index(max_rate)
    peak_fraction = (peak_idx + 0.5) / len(window) if len(window) > 1 else 0.5

    return {
        "rate_mm_per_h": round(avg_rate, 2),
        "duration_h": duration_h,
        "peak_multiplier": round(peak_multiplier, 2),
        "peak_time_fraction": round(peak_fraction, 3),
    }


# =============================================================================
# Population — WorldPop API (fallback: statistical estimate)
# =============================================================================

def fetch_population(
    lat: float,
    lon: float,
    grid_size: int = 30,
    cell_size_m: float = 10.0,
) -> np.ndarray:
    """Fetch population density for a grid centred on (lat, lon).

    Attempts to query the WorldPop point API. Because the WorldPop API
    returns a single-point estimate, we sample the grid corners and
    interpolate to build a spatial population map.

    If the API is unavailable, falls back to a statistical estimate based
    on known global urban density patterns.

    Parameters
    ----------
    lat : float
        Centre latitude.
    lon : float
        Centre longitude.
    grid_size : int
        Grid rows/columns.
    cell_size_m : float
        Cell spacing in metres.

    Returns
    -------
    np.ndarray[int32]
        Population count per cell, shape ``(grid_size, grid_size)``.
    """
    d_lat = cell_size_m / 111_320.0
    d_lon = cell_size_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    half = grid_size // 2

    # Sample a sparse set of points (corners + centre + edges) to reduce API calls.
    sample_offsets = [
        (0, 0), (0, half), (0, grid_size - 1),
        (half, 0), (half, half), (half, grid_size - 1),
        (grid_size - 1, 0), (grid_size - 1, half), (grid_size - 1, grid_size - 1),
    ]

    pop_samples: Dict[Tuple[int, int], float] = {}

    for r, c in sample_offsets:
        pt_lat = lat + (r - half) * d_lat
        pt_lon = lon + (c - half) * d_lon
        try:
            resp = requests.get(
                "https://hub.worldpop.org/rest/data/pop/wpgp",
                params={
                    "lat": round(pt_lat, 4),
                    "lon": round(pt_lon, 4),
                },
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                # WorldPop returns population density per km².
                # Convert to per-cell: density × (cell_area_m² / 1e6)
                density = 0.0
                if isinstance(data, dict) and "data" in data:
                    items = data["data"]
                    if items and isinstance(items, list) and len(items) > 0:
                        density = float(items[0].get("ppp", 0.0))
                elif isinstance(data, (int, float)):
                    density = float(data)

                cell_area_km2 = (cell_size_m ** 2) / 1e6
                pop_samples[(r, c)] = max(0.0, density * cell_area_km2)
            else:
                pop_samples[(r, c)] = -1  # mark as failed
        except (requests.RequestException, ValueError, KeyError):
            pop_samples[(r, c)] = -1  # mark as failed

    # Check how many samples succeeded.
    valid = {k: v for k, v in pop_samples.items() if v >= 0}

    if len(valid) >= 3:
        # Interpolate using inverse-distance weighting.
        population = np.zeros((grid_size, grid_size), dtype=np.float64)
        for r in range(grid_size):
            for c in range(grid_size):
                if (r, c) in valid:
                    population[r, c] = valid[(r, c)]
                else:
                    weights = []
                    values = []
                    for (sr, sc), val in valid.items():
                        dist = max(math.sqrt((r - sr) ** 2 + (c - sc) ** 2), 0.1)
                        weights.append(1.0 / dist)
                        values.append(val)
                    total_w = sum(weights)
                    population[r, c] = sum(w * v for w, v in zip(weights, values)) / total_w

        # Add small random variation for realism.
        rng = np.random.default_rng(42)
        noise = rng.normal(1.0, 0.15, (grid_size, grid_size))
        population = population * np.abs(noise)
        population = np.clip(population, 0, 5000)
        return population.astype(np.int32)
    else:
        # Fallback: use statistical estimate (urban ~5000–15000 people/km²).
        rng = np.random.default_rng(42)
        density_per_km2 = rng.uniform(3000, 10000)
        cell_area_km2 = (cell_size_m ** 2) / 1e6
        base_pop = density_per_km2 * cell_area_km2

        population = rng.normal(base_pop, base_pop * 0.3, (grid_size, grid_size))
        population = np.clip(population, 0, 5000)
        return population.astype(np.int32)


# =============================================================================
# Combined fetcher
# =============================================================================

def fetch_all_real_data(
    lat: float,
    lon: float,
    grid_size: int = 30,
    cell_size_m: float = 10.0,
    duration_h: float = 2.0,
) -> Dict[str, Any]:
    """Fetch elevation, rainfall, and population from real-world APIs.

    Returns a dict with keys:
        ``elevation``  — np.ndarray (grid_size, grid_size)
        ``rainfall``   — dict of rainfall parameters
        ``population`` — np.ndarray (grid_size, grid_size)

    Raises
    ------
    RuntimeError
        If a critical API (elevation) fails.
    """
    elevation = fetch_elevation(lat, lon, grid_size, cell_size_m)
    rainfall = fetch_rainfall(lat, lon, duration_h)
    population = fetch_population(lat, lon, grid_size, cell_size_m)

    return {
        "elevation": elevation,
        "rainfall": rainfall,
        "population": population,
    }

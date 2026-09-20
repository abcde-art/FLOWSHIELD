"""Data loading and city initialization routines."""

from __future__ import annotations

from typing import Dict, Any

import numpy as np

from flowshield.utils.config import SimulationConfig
from flowshield.data.generator import CityGridGenerator
from flowshield.data.models import CityGrid

def build_city(config: Dict[str, Any] | SimulationConfig) -> CityGrid:
    """Build a city grid from a configuration."""
    if isinstance(config, dict):
        config = SimulationConfig.model_validate(config)
        
    generator = CityGridGenerator(config)
    city = generator.generate()
    
    # ensure shape validation occurs
    CityGridGenerator.validate(city)
    
    return city


def build_city_from_api(
    lat: float,
    lon: float,
    config: Dict[str, Any] | SimulationConfig,
) -> CityGrid:
    """Build a city grid using real-world data from APIs.

    Fetches elevation, population, and rainfall data from Open-Elevation,
    WorldPop, and Open-Meteo, then constructs a CityGrid with real terrain
    and population while computing drainage from the config parameters.

    Parameters
    ----------
    lat : float
        Centre latitude (decimal degrees).
    lon : float
        Centre longitude (decimal degrees).
    config : dict | SimulationConfig
        Simulation configuration (used for grid size, drainage params, etc.).

    Returns
    -------
    CityGrid
        A fully initialised city grid with real-world data.
    """
    from flowshield.data.api_data import fetch_elevation, fetch_population

    if isinstance(config, dict):
        config = SimulationConfig.model_validate(config)

    grid_size = config.grid.width  # assume square grid
    cell_size_m = config.grid.cell_size_m

    generator = CityGridGenerator(config)

    # 1. Elevation
    try:
        elevation = fetch_elevation(lat, lon, grid_size, cell_size_m)
    except Exception as e:
        import streamlit as st
        st.sidebar.warning(f"Elevation API failed ({e}). Using synthetic terrain.")
        elevation = generator._generate_elevation()

    # 2. Population
    try:
        population = fetch_population(lat, lon, grid_size, cell_size_m)
    except Exception as e:
        import streamlit as st
        st.sidebar.warning(f"Population API failed ({e}). Using synthetic population.")
        population = generator._generate_population(elevation)

    # 3. Drainage (always synthetic)
    drainage = generator._generate_drainage(elevation)

    city = CityGrid(
        elevation=elevation,
        population=population,
        drainage_capacity=drainage,
    )

    CityGridGenerator.validate(city)

    return city

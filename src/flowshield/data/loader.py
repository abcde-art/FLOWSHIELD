"""Data loading and city initialization routines."""

from __future__ import annotations

from typing import Dict, Any

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

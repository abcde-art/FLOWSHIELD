# FLOWSHIELD References

This document serves as the central source-of-truth for project references, identifying external code, algorithms, published methodologies, third-party libraries, and synthetic dataset origins.

## 1. Numerical Simulation

[REF-004]
Title: Cellular Automata in Hydrology: The D4 (von Neumann) routing approximation
Type: Methodological Reference
URL: https://en.wikipedia.org/wiki/Von_Neumann_neighborhood
Usage: Grid-based flow transfer. FLOWSHIELD implements a vectorized, mass-conserving derivation of this neighborhood.
License: Public Domain (Mathematical Concept)
Used In: `src/flowshield/simulation/flow.py`

[REF-007]
Title: Hydrological Mass Conservation Principle
Type: Standard Physics Principle
URL: https://en.wikipedia.org/wiki/Water_balance
Usage: Strict mass balance equation ($V_{surface} = V_{init} + V_{rain} - V_{drain}$) used for validation auditing.
License: Public Domain (Mathematical Concept)
Used In: `src/flowshield/validation/conservation.py`

## 2. Terrain Generation & Datasets

[REF-006]
Title: Synthetic Topography Generation via Gaussian Superposition
Type: Algorithm Reference
Usage: Generates a deterministic grid of hills and valleys utilizing overlapping 2D Gaussian functions and planar slopes.
License: Original FLOWSHIELD Method
Used In: `src/flowshield/data/generator.py`
Dataset: **Synthetic FLOWSHIELD-generated data.** No external DEM/LIDAR dataset is used.

## 3. Forecasting / Regression

[REF-005]
Title: Simple Linear Regression for Time-Series Extrapolation
Type: Methodological Reference
URL: https://numpy.org/doc/stable/reference/generated/numpy.polyfit.html
Usage: `numpy.polyfit(deg=1)` is used to estimate the instantaneous linear trend of water accumulation. Time-to-critical is a simple linear extrapolation.
License: NumPy License (BSD)
Used In: `src/flowshield/risk/forecasting.py`

## 4. Python / NumPy References

[REF-001]
Library: Python Standard Library
Purpose: Standard system execution, path handling, and typing.
Official Source: https://docs.python.org/3/
Usage: Foundation of all modules.
License: Python Software Foundation License

[REF-002]
Library: NumPy
Version: >= 1.24.0
Purpose: Vectorized numerical array operations and slicing.
Official Source: https://numpy.org/
Usage: Simulation engine physics and grid representations.
License: BSD 3-Clause

[REF-003]
Library: Pydantic
Version: >= 2.0.0
Purpose: Configuration parsing and data model validation.
Official Source: https://docs.pydantic.dev/
Usage: `src/flowshield/utils/config.py` and scenario definitions.
License: MIT License

## 5. UI & Dashboard References

[REF-008]
Library: Streamlit
Version: >= 1.30.0
Purpose: Web-based interactive emergency dashboard.
Official Source: https://streamlit.io/
Usage: `app.py`
License: Apache 2.0

[REF-009]
Library: Plotly
Version: >= 5.18.0
Purpose: 2D heatmap and 3D surface visualizations.
Official Source: https://plotly.com/python/
Usage: `app.py`
License: MIT License

## 6. Testing References

[REF-010]
Library: pytest
Version: >= 7.4.0
Purpose: Automated validation suite and parametrized testing.
Official Source: https://docs.pytest.org/
Usage: `tests/` directory
License: MIT License

## 7. AI-Assisted Development Disclosure

FLOWSHIELD contains code developed with assistance from AI coding tools.

AI assistance included:
- Code generation
- Physics-engine optimizations (vectorization)
- Documentation assistance
- Test generation

All AI-generated code was thoroughly reviewed, mathematically validated, and integrated into the project by the development team. No external copyrighted code was reproduced by the AI tool.

"""FLOWSHIELD Emergency Flood Forecasting Dashboard.

Launch:
    cd flowshield
    streamlit run app.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ── Path setup ───────────────────────────────────────────────────────────────
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from flowshield.data.generator import CityGridGenerator
from flowshield.data.models import CityGrid
from flowshield.risk.classifier import RiskLevel, classify_risk
from flowshield.risk.forecasting import (
    CRITICAL_NOW,
    INSUFFICIENT_DATA,
    NOT_EXPECTED,
    predict_time_to_critical,
)
from flowshield.risk.population import compute_population_impact
from flowshield.simulation.engine import SimulationEngine
from flowshield.simulation.scenarios import SCENARIO_REGISTRY
from flowshield.utils.config import SimulationConfig
from flowshield.validation.conservation import check_mass_conservation

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FLOWSHIELD | Emergency Flood Ops",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Global typography */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
section[data-testid="stSidebar"] { background: #0b0e14; }

/* KPI card container */
.kpi-card {
    background: linear-gradient(135deg, #12152a 0%, #16213e 100%);
    border: 1px solid rgba(77, 166, 255, 0.15);
    border-radius: 14px;
    padding: 18px 14px;
    text-align: center;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35);
    transition: transform .2s ease, box-shadow .2s ease;
}
.kpi-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.5);
}
.kpi-value { font-size: 2rem; font-weight: 800; margin: 6px 0 2px; line-height:1; }
.kpi-label {
    font-size: .7rem; color: #6b7d95;
    text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;
}
.kpi-safe  .kpi-value { color: #00e676; }
.kpi-warn  .kpi-value { color: #ffc107; }
.kpi-crit  .kpi-value { color: #ff5252; }
.kpi-info  .kpi-value { color: #4da6ff; }
.kpi-pop   .kpi-value { color: #ff9100; }

.badge {
    display:inline-block; padding: 5px 14px; border-radius: 20px;
    font-size: .75rem; font-weight: 700; letter-spacing: 1px;
}
.badge-pass { background: rgba(0,230,118,.12); color:#00e676; border:1px solid #00e676; }
.badge-fail { background: rgba(255,82,82,.12); color:#ff5252; border:1px solid #ff5252; }

/* Header banner */
.hero-banner {
    background: linear-gradient(100deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    padding: 22px 32px; border-radius: 14px; margin-bottom: 18px;
    border: 1px solid rgba(120,120,220,.18);
}
.hero-banner h1 {
    margin:0; font-size: 1.7rem; font-weight: 800;
    background: linear-gradient(135deg,#4da6ff,#ff6b6b);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.hero-banner p { margin:4px 0 0; color:#7889a0; font-size:.88rem; }

/* Section header */
.sec-hdr {
    font-size:.85rem; font-weight:700; text-transform:uppercase;
    letter-spacing:2px; color:#5a7a9a; margin:22px 0 8px;
    padding-bottom:5px; border-bottom:2px solid rgba(90,122,154,.25);
}
</style>
""",
    unsafe_allow_html=True,
)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CONSTANTS & PRESETS                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

SCENARIO_LABELS = [
    "Normal Rainfall",
    "Cloudburst Surge",
    "Drainage Failure",
    "Blocked Culvert",
]


_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"
SCENARIO_FILES = {
    "Normal Rainfall": _CONFIGS_DIR / "default.json",
    "Cloudburst Surge": _CONFIGS_DIR / "heavy_rain.json",
    "Drainage Failure": _CONFIGS_DIR / "drainage_failure.json",
    "Blocked Culvert": _CONFIGS_DIR / "blocked_channel.json",
}

GRID_OPTIONS = {"20 x 20": 20, "30 x 30": 30, "50 x 50": 50, "80 x 80": 80}

_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"
SCENARIO_FILES = {
    "Normal Rainfall": _CONFIGS_DIR / "default.json",
    "Cloudburst Surge": _CONFIGS_DIR / "heavy_rain.json",
    "Drainage Failure": _CONFIGS_DIR / "drainage_failure.json",
    "Blocked Culvert": _CONFIGS_DIR / "blocked_channel.json",
}

SECTOR_NAMES = ["NW", "N", "NE", "W", "Central", "E", "SW", "S", "SE"]

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  HELPER FUNCTIONS                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def _sector_slices(rows: int, cols: int) -> Dict[str, Tuple[slice, slice]]:
    r3, c3 = rows // 3, cols // 3
    return {
        "NW": (slice(0, r3), slice(0, c3)),
        "N":  (slice(0, r3), slice(c3, 2 * c3)),
        "NE": (slice(0, r3), slice(2 * c3, cols)),
        "W":  (slice(r3, 2 * r3), slice(0, c3)),
        "Central": (slice(r3, 2 * r3), slice(c3, 2 * c3)),
        "E":  (slice(r3, 2 * r3), slice(2 * c3, cols)),
        "SW": (slice(2 * r3, rows), slice(0, c3)),
        "S":  (slice(2 * r3, rows), slice(c3, 2 * c3)),
        "SE": (slice(2 * r3, rows), slice(2 * c3, cols)),
    }


def _make_blockage_mask(
    rows: int, cols: int, blocked: Tuple[str, ...],
) -> np.ndarray | None:
    if not blocked:
        return None
    mask = np.ones((rows, cols), dtype=np.float64)
    sectors = _sector_slices(rows, cols)
    for name in blocked:
        if name in sectors:
            rs, cs = sectors[name]
            mask[rs, cs] = 0.0
    return mask


def _kpi_html(label: str, value, css: str = "kpi-info") -> str:
    return (
        f'<div class="kpi-card {css}">'
        f'  <div class="kpi-label">{label}</div>'
        f'  <div class="kpi-value">{value}</div>'
        f"</div>"
    )


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CACHED COMPUTATIONS                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

@st.cache_data(show_spinner="Running flood simulation ...")
def run_simulation(config_json: str, blocked: tuple) -> dict:
    """Run the full simulation and capture per-step snapshots."""
    cfg = SimulationConfig.model_validate(json.loads(config_json))
    from flowshield.data.loader import build_city
    grid = build_city(cfg)

    mask = _make_blockage_mask(cfg.grid.height, cfg.grid.width, blocked)
    engine = SimulationEngine(cfg, grid, blockage_mask=mask)

    snapshots: List[np.ndarray] = [grid.water_depth.copy()]
    for _ in range(engine.num_steps):
        engine.step()
        snapshots.append(grid.water_depth.copy())

    cons = check_mass_conservation(engine)

    return dict(
        elevation=grid.elevation,
        population=grid.population,
        drainage_capacity=grid.drainage_capacity,
        snapshots=snapshots,
        rain_hist=list(engine.audit.rain_added_history),
        drain_hist=list(engine.audit.water_drained_history),
        vol_hist=list(engine.audit.total_water_volume_history),
        init_vol=engine.initial_water_volume,
        num_steps=engine.num_steps,
        dt=cfg.simulation.timestep_min,
        warn_th=cfg.risk.warning_depth_m,
        crit_th=cfg.risk.critical_depth_m,
        cons_pass=cons.passed,
        cons_err=cons.absolute_error,
        name=cfg.name,
    )


@st.cache_data(show_spinner="Fetching real-world data & running simulation ...")
def run_simulation_api(config_json: str, blocked: tuple, lat: float, lon: float) -> dict:
    """Run simulation using real-world data from APIs."""
    cfg = SimulationConfig.model_validate(json.loads(config_json))
    from flowshield.data.loader import build_city_from_api
    from flowshield.data.api_data import fetch_rainfall

    try:
        real_rain = fetch_rainfall(lat, lon, cfg.simulation.duration_h)
        # Override config with real rain data
        cfg.rainfall.rate_mm_per_h = real_rain["rate_mm_per_h"]
        cfg.rainfall.duration_h = real_rain["duration_h"]
        cfg.rainfall.peak_multiplier = real_rain["peak_multiplier"]
        cfg.rainfall.peak_time_fraction = real_rain["peak_time_fraction"]
    except Exception as e:
        import streamlit as st
        st.sidebar.warning(f"Rainfall API failed ({e}). Using synthetic rainfall.")
        real_rain = {
            "rate_mm_per_h": cfg.rainfall.rate_mm_per_h,
            "duration_h": cfg.rainfall.duration_h,
            "peak_multiplier": cfg.rainfall.peak_multiplier,
            "peak_time_fraction": cfg.rainfall.peak_time_fraction,
        }

    grid = build_city_from_api(lat, lon, cfg)

    mask = _make_blockage_mask(cfg.grid.height, cfg.grid.width, blocked)
    engine = SimulationEngine(cfg, grid, blockage_mask=mask)

    snapshots: List[np.ndarray] = [grid.water_depth.copy()]
    for _ in range(engine.num_steps):
        engine.step()
        snapshots.append(grid.water_depth.copy())

    cons = check_mass_conservation(engine)

    return dict(
        elevation=grid.elevation,
        population=grid.population,
        drainage_capacity=grid.drainage_capacity,
        snapshots=snapshots,
        rain_hist=list(engine.audit.rain_added_history),
        drain_hist=list(engine.audit.water_drained_history),
        vol_hist=list(engine.audit.total_water_volume_history),
        init_vol=engine.initial_water_volume,
        num_steps=engine.num_steps,
        dt=cfg.simulation.timestep_min,
        warn_th=cfg.risk.warning_depth_m,
        crit_th=cfg.risk.critical_depth_m,
        cons_pass=cons.passed,
        cons_err=cons.absolute_error,
        name=cfg.name,
        api_rainfall=real_rain,
        data_source="api",
        lat=lat,
        lon=lon,
    )


@st.cache_data(show_spinner="Comparing scenarios ...")
def compare_scenarios() -> Dict[str, Dict[str, Any]]:
    """Run all four preset scenarios and return summary metrics."""
    results: Dict[str, Dict[str, Any]] = {}
    for label, builder in SCENARIO_REGISTRY.items():
        eng = builder()
        c = eng.config
        risk = classify_risk(
            eng.grid.water_depth,
            c.risk.warning_depth_m,
            c.risk.critical_depth_m,
        )
        pop = compute_population_impact(
            eng.grid.water_depth, eng.grid.population,
            c.risk.warning_depth_m, c.risk.critical_depth_m,
        )
        results[label] = dict(
            peak=float(eng.grid.water_depth.max()),
            crit_cells=int((risk == RiskLevel.CRITICAL).sum()),
            warn_cells=int((risk == RiskLevel.WARNING).sum()),
            crit_pop=pop.critical_population,
            warn_pop=pop.warning_population,
            total_pop=pop.total_affected,
        )
    return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  SESSION STATE INIT                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝

if "auto_play" not in st.session_state:
    st.session_state.auto_play = False
if "current_step" not in st.session_state:
    st.session_state.current_step = 0
if "_prev_scenario" not in st.session_state:
    st.session_state._prev_scenario = None

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  SIDEBAR                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════╝

with st.sidebar:
    st.markdown("## :shield: Scenario Configuration")

    # ── Data Source Toggle ────────────────────────────────────────────────
    data_source = st.radio(
        "📡 Data Source",
        ["Synthetic", "Real-World API"],
        index=0,
        key="data_source",
        horizontal=True,
        help="Synthetic uses procedural generation. Real-World API fetches live terrain, weather, and population data.",
    )
    use_api = data_source == "Real-World API"

    if use_api:
        st.markdown("##### 🌍 Location (Lat / Lon)")
        api_col1, api_col2 = st.columns(2)
        with api_col1:
            api_lat = st.number_input("Latitude", value=28.6139, format="%.4f", key="api_lat")
        with api_col2:
            api_lon = st.number_input("Longitude", value=77.2090, format="%.4f", key="api_lon")
        st.caption("Default: New Delhi. Try Mumbai (19.0760, 72.8777) or Chennai (13.0827, 80.2707).")

    st.divider()

    scenario = st.selectbox("Scenario Preset", SCENARIO_LABELS, key="scenario_sel")

    # Sync slider defaults when scenario changes
    if scenario != st.session_state._prev_scenario:
        st.session_state._prev_scenario = scenario
        from flowshield.utils.config import load_config
        cfg = load_config(SCENARIO_FILES[scenario])
        st.session_state.s_rain_mm = cfg.rainfall.rate_mm_per_h
        st.session_state.s_rain_dur = int(cfg.rainfall.duration_h * 60)
        st.session_state.s_surge = cfg.rainfall.peak_multiplier > 1.0
        st.session_state.s_surge_start = int(cfg.rainfall.peak_time_fraction * cfg.rainfall.duration_h * 60)
        st.session_state.s_surge_mult = cfg.rainfall.peak_multiplier
        st.session_state.s_flow_c = cfg.simulation.flow_coefficient
        st.session_state.s_drain_mm = cfg.drainage.base_capacity_m3_per_h
        st.session_state.s_warn = cfg.risk.warning_depth_m
        st.session_state.s_crit = cfg.risk.critical_depth_m
        st.session_state.s_blocked = []
        st.rerun()

    st.divider()

    grid_label = st.selectbox("Grid Size", list(GRID_OPTIONS.keys()), index=1)
    grid_n = GRID_OPTIONS[grid_label]

    rain_mm = st.slider(
        "Rainfall Intensity (mm/hr)", 5.0, 120.0, key="s_rain_mm", step=1.0,
    )
    rain_dur = st.slider(
        "Rainfall Duration (min)", 10, 180, key="s_rain_dur", step=5,
    )
    sim_dur = st.slider(
        "Simulation Duration (min)", 30, 360, value=120, step=10,
    )

    st.divider()
    surge = st.checkbox("Surge Enabled", key="s_surge")
    if surge:
        surge_start = st.slider("Surge Start (min)", 5, 120, key="s_surge_start")
        surge_mult = st.slider(
            "Surge Multiplier", 1.5, 5.0, key="s_surge_mult", step=0.1,
        )
    else:
        surge_start = int(st.session_state.get("s_surge_start", 30))
        surge_mult = float(st.session_state.get("s_surge_mult", 2.0))

    st.divider()
    flow_c = st.slider(
        "Flow Coefficient", 0.05, 1.0, key="s_flow_c", step=0.05,
    )
    drain_mm = st.slider(
        "Drainage Rate (mm/hr)", 0.0, 30.0, key="s_drain_mm", step=0.5,
    )

    st.divider()
    st.markdown("### :construction: Channel Blockage")
    blocked = st.multiselect(
        "Block Sectors", SECTOR_NAMES, key="s_blocked",
    )

    st.divider()
    run_btn = st.button(
        "🚀  RUN SIMULATION", type="primary", use_container_width=True,
    )

    if run_btn:
        st.session_state.current_step = 0
        st.session_state.auto_play = True

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  BUILD CONFIG & RUN                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝

from flowshield.utils.config import load_config
cfg = load_config(SCENARIO_FILES[scenario])
cfg_dict = cfg.model_dump()
cfg_dict["grid"]["width"] = grid_n
cfg_dict["grid"]["height"] = grid_n
cfg_dict["rainfall"]["rate_mm_per_h"] = rain_mm
cfg_dict["rainfall"]["duration_h"] = rain_dur / 60.0
cfg_dict["rainfall"]["peak_multiplier"] = surge_mult if surge else 1.0
cfg_dict["rainfall"]["peak_time_fraction"] = surge_start / rain_dur if surge and rain_dur > 0 else 0.5
cfg_dict["simulation"]["duration_h"] = sim_dur / 60.0
cfg_dict["simulation"]["flow_coefficient"] = flow_c
cfg_dict["drainage"]["base_capacity_m3_per_h"] = drain_mm
cfg_dict["risk"]["warning_depth_m"] = float(st.session_state.get("s_warn", 0.10))
cfg_dict["risk"]["critical_depth_m"] = float(st.session_state.get("s_crit", 0.30))
cfg_json = json.dumps(cfg_dict, sort_keys=True)

if use_api:
    try:
        sim = run_simulation_api(cfg_json, tuple(sorted(blocked)), api_lat, api_lon)
        st.sidebar.success(f"📡 API Data loaded for ({api_lat:.4f}, {api_lon:.4f}) (with synthetic fallbacks if needed).")
    except RuntimeError as e:
        st.sidebar.error(f"API Error: {e}\n\nFalling back to synthetic data.")
        sim = run_simulation(cfg_json, tuple(sorted(blocked)))
else:
    sim = run_simulation(cfg_json, tuple(sorted(blocked)))

# ── Convenience aliases ───────────────────────────────────────────────────
elevation = sim["elevation"]
population = sim["population"]
drainage = sim["drainage_capacity"]
snapshots = sim["snapshots"]
num_steps = sim["num_steps"]
dt_min = sim["dt"]
warn_th = sim["warn_th"]
crit_th = sim["crit_th"]
rows, cols = elevation.shape

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  AUTO-PLAY LOGIC (increment step BEFORE slider renders)                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝

if st.session_state.auto_play:
    cs = st.session_state.current_step
    if cs < num_steps:
        # Advance slightly (reduce reruns)
        step_increment = max(1, num_steps // 30)
        st.session_state.current_step = min(num_steps, cs + step_increment)
        import time
        time.sleep(0.05)
        st.rerun()
    else:
        st.session_state.auto_play = False

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  HEADER                                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝

st.markdown(
    '<div class="hero-banner">'
    "  <h1>FLOWSHIELD — Emergency Flood Operations Center</h1>"
    f'  <p>Scenario: <strong>{sim["name"]}</strong> &nbsp;|&nbsp; '
    f'Grid: {rows} x {cols} &nbsp;|&nbsp; Duration: {num_steps} min</p>'
    "</div>",
    unsafe_allow_html=True,
)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  TIME CONTROLS                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

ctrl_cols = st.columns([1, 1, 1, 9])
with ctrl_cols[0]:
    if st.button("⏮ Reset", use_container_width=True):
        st.session_state.current_step = 0
        st.session_state.auto_play = False
        st.rerun()
with ctrl_cols[1]:
    play_label = "⏸ Pause" if st.session_state.auto_play else "▶ Play"
    if st.button(play_label, use_container_width=True):
        st.session_state.auto_play = not st.session_state.auto_play
        st.rerun()
with ctrl_cols[2]:
    if st.button("⏭ End", use_container_width=True):
        st.session_state.current_step = num_steps
        st.session_state.auto_play = False
        st.rerun()

step = st.slider(
    "Simulation Time (minutes)",
    min_value=0,
    max_value=num_steps,
    key="current_step",
    label_visibility="collapsed",
)

st.caption(
    f"**T = {step * dt_min:.0f} min** of {num_steps * dt_min:.0f} min total"
)

# ── Current snapshot ──────────────────────────────────────────────────────
wd = snapshots[step]
risk = classify_risk(wd, warn_th, crit_th)
pop_impact = compute_population_impact(wd, population, warn_th, crit_th)

safe_count = int((risk == RiskLevel.SAFE).sum())
warn_count = int((risk == RiskLevel.WARNING).sum())
crit_count = int((risk == RiskLevel.CRITICAL).sum())

# ── Conservation at current step ──────────────────────────────────────────
cum_rain = float(np.sum(sim["rain_hist"][:step])) if step > 0 else 0.0
cum_drain = float(np.sum(sim["drain_hist"][:step])) if step > 0 else 0.0
surface_vol = float(wd.sum())
expected_vol = sim["init_vol"] + cum_rain - cum_drain
cons_err = abs(surface_vol - expected_vol)
cons_ok = cons_err < 1e-6

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  KPI CARDS                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════╝

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    st.markdown(_kpi_html("Safe Regions", f"{safe_count}", "kpi-safe"), unsafe_allow_html=True)
with k2:
    st.markdown(_kpi_html("Warning Regions", f"{warn_count}", "kpi-warn"), unsafe_allow_html=True)
with k3:
    st.markdown(_kpi_html("Critical Regions", f"{crit_count}", "kpi-crit"), unsafe_allow_html=True)
with k4:
    st.markdown(
        _kpi_html("Population at Risk", f"{pop_impact.total_affected:,}", "kpi-pop"),
        unsafe_allow_html=True,
    )
with k5:
    st.markdown(
        _kpi_html("Severely Impacted", f"{pop_impact.critical_population:,}", "kpi-crit"),
        unsafe_allow_html=True,
    )
with k6:
    badge = "badge-pass" if cons_ok else "badge-fail"
    tag = "PASS" if cons_ok else "FAIL"
    st.markdown(
        _kpi_html("Water Balance", f'<span class="badge {badge}">{tag}</span>', "kpi-info"),
        unsafe_allow_html=True,
    )

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  SPATIAL VISUALIZER (2D / 3D)                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝

st.markdown('<div class="sec-hdr">Spatial &amp; Temporal Flood Map</div>', unsafe_allow_html=True)

# ── Precompute per-cell hover data ────────────────────────────────────────
risk_labels = np.where(
    risk == RiskLevel.SAFE, "SAFE",
    np.where(risk == RiskLevel.WARNING, "WARNING", "CRITICAL"),
)
region_ids = np.array(
    [[f"R{r:02d}C{c:02d}" for c in range(cols)] for r in range(rows)]
)

# Time-to-critical text
window = 5
ttc_start = max(0, step - window + 1)
recent_stack = np.stack(snapshots[ttc_start : step + 1], axis=0)  # (T, R, C)
ttc_text = np.full((rows, cols), "--", dtype=object)
ttc_text[risk == RiskLevel.CRITICAL] = "CRITICAL NOW"

warning_cells = np.argwhere(risk == RiskLevel.WARNING)
for r, c in warning_cells:
    hist = [float(recent_stack[t, r, c]) for t in range(recent_stack.shape[0])]
    res = predict_time_to_critical(
        hist, float(wd[r, c]), crit_th, dt_min,
        window_size=min(window, len(hist)),
    )
    ttc_text[r, c] = f"{res:.1f} min" if isinstance(res, float) else res

# Build customdata: [elevation, drainage, risk_label, ttc]
elev_fmt = np.vectorize(lambda x: f"{x:.2f}")(elevation)
drain_fmt = np.vectorize(lambda x: f"{x:.6f}")(drainage)
customdata = np.stack([elev_fmt, drain_fmt, risk_labels, ttc_text], axis=-1)

tab2d, tab3d = st.tabs(["2D Heatmap", "3D Surface"])

# ── 2D Heatmap ────────────────────────────────────────────────────────────
with tab2d:
    fig2d = go.Figure()

    # Water depth heatmap
    max_depth = max(float(np.max([s.max() for s in snapshots])), 0.001)
    fig2d.add_trace(
        go.Heatmap(
            z=wd,
            zmin=0,
            zmax=max_depth,
            colorscale=[
                [0.0, "rgba(10,10,30,0.95)"],
                [0.15, "#0d47a1"],
                [0.4, "#1565c0"],
                [0.6, "#42a5f5"],
                [0.8, "#ffb300"],
                [1.0, "#ff1744"],
            ],
            colorbar=dict(title="Water Depth (m)", thickness=14),
            text=region_ids,
            customdata=customdata,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Elevation: %{customdata[0]} m<br>"
                "Water Depth: %{z:.4f} m<br>"
                "Drainage: %{customdata[1]} m/step<br>"
                "Risk: %{customdata[2]}<br>"
                "Time-to-Critical: %{customdata[3]}"
                "<extra></extra>"
            ),
        )
    )

    # Terrain contour lines
    fig2d.add_trace(
        go.Contour(
            z=elevation,
            showscale=False,
            contours=dict(
                coloring="none",
                showlabels=True,
                labelfont=dict(size=9, color="rgba(255,255,255,0.45)"),
            ),
            line=dict(width=1, color="rgba(255,255,255,0.18)"),
            hoverinfo="skip",
        )
    )

    fig2d.update_layout(
        uirevision="constant",
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0e1117",
        xaxis=dict(title="Column", showgrid=False, color="#6b7d95"),
        yaxis=dict(title="Row", showgrid=False, autorange="reversed", color="#6b7d95"),
        title=dict(
            text=f"Flood Map — T = {step} min",
            font=dict(size=14, color="#8899aa"),
        ),
    )
    st.plotly_chart(fig2d, use_container_width=True, key="plot_2d")

# ── 3D Surface ────────────────────────────────────────────────────────────
with tab3d:
    fig3d = go.Figure()

    # Terrain surface
    fig3d.add_trace(
        go.Surface(
            z=elevation,
            colorscale="Earth",
            opacity=0.85,
            showscale=False,
            name="Terrain",
            hovertemplate="Terrain<br>Elevation: %{z:.2f} m<extra></extra>",
        )
    )

    # Water surface (only where depth > 0.001 m)
    water_level = elevation + wd
    water_masked = np.where(wd > 0.001, water_level, np.nan)
    fig3d.add_trace(
        go.Surface(
            z=water_masked,
            colorscale=[
                [0, "rgba(13,71,161,0.7)"],
                [0.5, "rgba(66,165,245,0.65)"],
                [1, "rgba(255,23,68,0.8)"],
            ],
            opacity=0.7,
            showscale=True,
            colorbar=dict(title="Water Level (m)", thickness=12, x=1.05),
            name="Water",
            hovertemplate="Water<br>Level: %{z:.3f} m<extra></extra>",
        )
    )

    fig3d.update_layout(
        uirevision="constant",
        height=560,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            xaxis=dict(title="Col", backgroundcolor="#0e1117", gridcolor="#1a2030"),
            yaxis=dict(title="Row", backgroundcolor="#0e1117", gridcolor="#1a2030"),
            zaxis=dict(title="Elev (m)", backgroundcolor="#0e1117", gridcolor="#1a2030"),
            bgcolor="#0e1117",
        ),
        title=dict(
            text=f"3D Terrain + Flood — T = {step} min",
            font=dict(size=14, color="#8899aa"),
        ),
    )
    st.plotly_chart(fig3d, use_container_width=True, key="plot_3d")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  BOTTOM ROW — INTELLIGENCE PANELS                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝

bot1, bot2, bot3 = st.columns([4, 4, 4])

# ── Panel 1: Early Warning Table ──────────────────────────────────────────
with bot1:
    st.markdown('<div class="sec-hdr">Early Warning Table</div>', unsafe_allow_html=True)

    warning_idx = np.argwhere((risk == RiskLevel.WARNING) | (risk == RiskLevel.CRITICAL))
    if len(warning_idx) == 0:
        st.info("No regions at WARNING or CRITICAL level at this timestep.")
    else:
        records = []
        for r, c in warning_idx:
            depth = float(wd[r, c])
            # Rising rate (m/min) from last 2 snapshots
            if step > 0:
                prev = float(snapshots[step - 1][r, c])
                rate = (depth - prev) / dt_min
            else:
                rate = 0.0
            records.append(dict(
                Region=f"R{r:02d}C{c:02d}",
                Depth_m=round(depth, 4),
                Rate_m_per_min=round(rate, 6),
                Risk=risk_labels[r, c],
                Time_to_Critical=ttc_text[r, c],
            ))
        df_warn = pd.DataFrame(records)
        df_warn = df_warn.sort_values("Depth_m", ascending=False).head(25)
        df_warn.columns = ["Region", "Depth (m)", "Rate (m/min)", "Risk", "ETA Critical"]
        st.dataframe(df_warn, use_container_width=True, height=340, hide_index=True)


# ── Panel 2: Scenario Comparison ──────────────────────────────────────────
with bot2:
    st.markdown('<div class="sec-hdr">Scenario Comparison</div>', unsafe_allow_html=True)

    cmp = compare_scenarios()
    labels = list(cmp.keys())
    peaks = [cmp[k]["peak"] for k in labels]
    crits = [cmp[k]["crit_cells"] for k in labels]
    pops  = [cmp[k]["total_pop"] for k in labels]

    fig_cmp = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        subplot_titles=("Peak Depth (m)", "Critical Cells", "Population Affected"),
    )

    bar_colors = ["#42a5f5", "#ff7043", "#ab47bc", "#66bb6a"]

    fig_cmp.add_trace(
        go.Bar(x=labels, y=peaks, marker_color=bar_colors, showlegend=False), row=1, col=1,
    )
    fig_cmp.add_trace(
        go.Bar(x=labels, y=crits, marker_color=bar_colors, showlegend=False), row=2, col=1,
    )
    fig_cmp.add_trace(
        go.Bar(x=labels, y=pops, marker_color=bar_colors, showlegend=False), row=3, col=1,
    )

    fig_cmp.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0e1117",
        font=dict(color="#8899aa", size=10),
    )
    fig_cmp.update_xaxes(showgrid=False, color="#6b7d95")
    fig_cmp.update_yaxes(showgrid=True, gridcolor="#1a2030", color="#6b7d95")
    st.plotly_chart(fig_cmp, use_container_width=True)


# ── Panel 3: Water Conservation Audit ─────────────────────────────────────
with bot3:
    st.markdown('<div class="sec-hdr">Water Conservation Audit</div>', unsafe_allow_html=True)

    if step == 0:
        st.info("Advance time to see conservation audit data.")
    else:
        t_axis = list(range(1, step + 1))
        cum_rain_arr = np.cumsum(sim["rain_hist"][:step]).tolist()
        cum_drain_arr = np.cumsum(sim["drain_hist"][:step]).tolist()
        surface_arr = [float(snapshots[t].sum()) for t in range(1, step + 1)]
        error_arr = [
            abs(
                sim["init_vol"] + cum_rain_arr[i] - cum_drain_arr[i] - surface_arr[i]
            )
            for i in range(len(t_axis))
        ]

        fig_aud = make_subplots(specs=[[{"secondary_y": True}]])

        fig_aud.add_trace(
            go.Scatter(
                x=t_axis, y=cum_rain_arr, name="Rain Added",
                line=dict(color="#42a5f5", width=2),
            ),
            secondary_y=False,
        )
        fig_aud.add_trace(
            go.Scatter(
                x=t_axis, y=cum_drain_arr, name="Drained",
                line=dict(color="#66bb6a", width=2),
            ),
            secondary_y=False,
        )
        fig_aud.add_trace(
            go.Scatter(
                x=t_axis, y=surface_arr, name="Surface Water",
                line=dict(color="#ffb300", width=2),
            ),
            secondary_y=False,
        )
        fig_aud.add_trace(
            go.Scatter(
                x=t_axis, y=error_arr, name="Error",
                line=dict(color="#ff5252", width=1.5, dash="dot"),
            ),
            secondary_y=True,
        )

        fig_aud.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0e1117",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, font=dict(size=10),
            ),
            font=dict(color="#8899aa", size=10),
        )
        fig_aud.update_xaxes(title="Time (min)", showgrid=False, color="#6b7d95")
        fig_aud.update_yaxes(
            title_text="Volume", showgrid=True,
            gridcolor="#1a2030", color="#6b7d95", secondary_y=False,
        )
        fig_aud.update_yaxes(
            title_text="Error", showgrid=False,
            color="#ff5252", secondary_y=True,
        )
        st.plotly_chart(fig_aud, use_container_width=True)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  AUTO-PLAY RERUN (must be last)                                         ║
# ╚══════════════════════════════════════════════════════════════════════════╝

if st.session_state.auto_play and st.session_state.current_step < num_steps:
    time.sleep(0.12)
    st.rerun()

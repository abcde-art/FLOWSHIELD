import numpy as np
from src.flowshield.simulation.scenarios import run_scenario
from src.flowshield.risk.classifier import RiskLevel, classify_risk
from src.flowshield.risk.population import compute_population_impact
from src.flowshield.validation.conservation import check_mass_conservation

# 1. Run Scenario
print('Running Cloudburst Surge simulation...')
engine = run_scenario('Cloudburst Surge')
grid = engine.grid
config = engine.config

# 2. Analyze Results
final_depth = grid.water_depth
risk_map = classify_risk(final_depth, 
                         warning_threshold=config.risk_thresholds.warning_depth_m, 
                         critical_threshold=config.risk_thresholds.critical_depth_m)

safe = np.sum(risk_map == RiskLevel.SAFE)
warn = np.sum(risk_map == RiskLevel.WARNING)
crit = np.sum(risk_map == RiskLevel.CRITICAL)

impact = compute_population_impact(final_depth, grid.population, 
                                   config.risk_thresholds.warning_depth_m, 
                                   config.risk_thresholds.critical_depth_m)

# 3. Conservation Check
conservation_result = check_mass_conservation(engine)
bal_str = "PASS" if conservation_result.passed else "FAIL"

print(f'\n--- SIMULATION RESULTS (Cloudburst Surge, {grid.rows}x{grid.cols} grid) ---')
print(f'Safe Regions: {safe}')
print(f'Warning Regions: {warn}')
print(f'Critical Regions: {crit}')
print(f'Population at Risk (Warning): {impact.warning_population:,.0f}')
print(f'Severely Impacted Pop (Critical): {impact.critical_population:,.0f}')
print(f'Total Affected Population: {impact.total_affected:,.0f}')
print(f'Water Balance: {bal_str} (Error: {conservation_result.absolute_error:.2e})')

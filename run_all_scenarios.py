import numpy as np
from src.flowshield.simulation.scenarios import SCENARIO_REGISTRY, run_scenario
from src.flowshield.risk.classifier import RiskLevel, classify_risk
from src.flowshield.risk.population import compute_population_impact

print("| Scenario | Safe | Warning | Critical | Pop at Risk | Severely Impacted |")
print("|---|---|---|---|---|---|")

for name in SCENARIO_REGISTRY.keys():
    engine = run_scenario(name)
    grid = engine.grid
    config = engine.config
    

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

    print(f"| {name} | {safe} | {warn} | {crit} | {impact.warning_population:,} | {impact.critical_population:,} |")


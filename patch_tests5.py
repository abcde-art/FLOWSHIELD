import glob
import re

def fix_scenarios():
    with open('src/flowshield/simulation/scenarios.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove the duplicate seed injection that overwrote drainage
    content = content.replace('"terrain": {"seed": 42},\n        "population": {"seed": 42},\n        "drainage": {"seed": 42},', '')
    
    # And manually inject seeds into the config building at the top so we don't have to write messy dicts
    content = content.replace('cfg = SimulationConfig.model_validate(overrides)', '''if "terrain" not in overrides: overrides["terrain"] = {}
    overrides["terrain"]["seed"] = overrides.get("terrain", {}).get("seed", 42)
    if "population" not in overrides: overrides["population"] = {}
    overrides["population"]["seed"] = overrides.get("population", {}).get("seed", 42)
    if "drainage" not in overrides: overrides["drainage"] = {}
    overrides["drainage"]["seed"] = overrides.get("drainage", {}).get("seed", 42)
    cfg = SimulationConfig.model_validate(overrides)''')

    # Remove duplicate simulation keys
    content = content.replace('"simulation": {"timestep_min": 1, "duration_h": 2},\n', '')

    with open('src/flowshield/simulation/scenarios.py', 'w', encoding='utf-8') as f:
        f.write(content)

def fix_test_conservation():
    with open('tests/test_conservation.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('drainage.base_drainage_rate_mm_hr', 'drainage.base_capacity_m3_per_h')
    content = content.replace('cfg.drainage.base_capacity_m3_per_h = 0', 'cfg.drainage.base_capacity_m3_per_h = 0.0')
    content = content.replace('rainfall={"rate_mm_per_h": 20, "duration_minutes": 10}', 'rainfall={"rate_mm_per_h": 20.0, "duration_h": 10.0/60.0}')
    content = content.replace('rainfall={"rate_mm_per_h": 0, "duration_minutes": 0}', 'rainfall={"rate_mm_per_h": 0.0, "duration_h": 0.0}')
    content = content.replace('rainfall={"rate_mm_per_h": 60, "duration_minutes": 10}', 'rainfall={"rate_mm_per_h": 60.0, "duration_h": 10.0/60.0}')
    content = content.replace('rainfall={"rate_mm_per_h": 60, "duration_minutes": 5}', 'rainfall={"rate_mm_per_h": 60.0, "duration_h": 5.0/60.0}')
    
    # test_surge_multiplier_applied
    content = content.replace('''rainfall={
                "rate_mm_per_h": 20,
                "duration_minutes": 60,
                "surge_enabled": True,
                "surge_start_minute": 10,
                "surge_multiplier": 3.0,
            }''', '''rainfall={
                "rate_mm_per_h": 20.0,
                "duration_h": 1.0,
                "peak_time_fraction": 10.0/60.0,
                "peak_multiplier": 3.0,
            }''')

    with open('tests/test_conservation.py', 'w', encoding='utf-8') as f:
        f.write(content)

fix_scenarios()
fix_test_conservation()

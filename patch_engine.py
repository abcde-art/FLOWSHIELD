import glob

def patch_file(file):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # fix specific config property access
    content = content.replace('cfg.time.timestep_minutes', 'cfg.simulation.timestep_min')
    content = content.replace('cfg.time.duration_minutes', 'cfg.simulation.duration_h * 60')
    content = content.replace('cfg.time.', 'cfg.simulation.')
    content = content.replace('config.time.timestep_minutes', 'config.simulation.timestep_min')
    content = content.replace('config.time.duration_minutes', '(config.simulation.duration_h * 60)')

    content = content.replace('cfg.rainfall.base_intensity_mm_hr', 'cfg.rainfall.rate_mm_per_h')
    content = content.replace('cfg.rainfall.duration_minutes', 'cfg.rainfall.duration_h * 60')
    content = content.replace('config.rainfall.base_intensity_mm_hr', 'config.rainfall.rate_mm_per_h')
    content = content.replace('config.rainfall.duration_minutes', '(config.rainfall.duration_h * 60)')
    content = content.replace('config.rainfall.surge_enabled', '(config.rainfall.peak_multiplier > 1.0)')
    content = content.replace('config.rainfall.surge_start_minute', '(config.rainfall.peak_time_fraction * config.simulation.duration_h * 60)')
    content = content.replace('config.rainfall.surge_multiplier', 'config.rainfall.peak_multiplier')
    
    content = content.replace('cfg.drainage.base_drainage_rate_mm_hr', 'cfg.drainage.base_capacity_m3_per_h')
    content = content.replace('config.drainage.base_drainage_rate_mm_hr', 'config.drainage.base_capacity_m3_per_h')
    
    content = content.replace('cfg.flow.flow_coefficient', 'cfg.simulation.flow_coefficient')
    content = content.replace('config.flow.flow_coefficient', 'config.simulation.flow_coefficient')
    
    content = content.replace('cfg.risk_thresholds.', 'cfg.risk.')
    content = content.replace('config.risk_thresholds.', 'config.risk.')

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

patch_file('src/flowshield/simulation/engine.py')
patch_file('src/flowshield/simulation/rainfall.py')
patch_file('src/flowshield/simulation/drainage.py')
patch_file('src/flowshield/simulation/flow.py')
patch_file('src/flowshield/risk/classifier.py')
patch_file('src/flowshield/risk/forecasting.py')
patch_file('src/flowshield/risk/population.py')

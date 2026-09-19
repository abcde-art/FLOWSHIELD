import glob
for file in glob.glob('tests/*.py'):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # fix _make_config
    content = content.replace('"grid": {"rows": rows, "cols": cols}', '"grid": {"height": rows, "width": cols}')
    
    # fix specific config property access
    content = content.replace('cfg.grid.rows', 'cfg.grid.height')
    content = content.replace('cfg.grid.cols', 'cfg.grid.width')
    content = content.replace('c.grid.rows', 'c.grid.height')
    content = content.replace('c.grid.cols', 'c.grid.width')
    content = content.replace('config.grid.rows', 'config.grid.height')
    content = content.replace('config.grid.cols', 'config.grid.width')
    
    content = content.replace('cfg.time.timestep_minutes', 'cfg.simulation.timestep_min')
    content = content.replace('cfg.time.duration_minutes', 'cfg.simulation.duration_h * 60')
    content = content.replace('cfg.time.', 'cfg.simulation.')
    content = content.replace('config.time.timestep_minutes', 'config.simulation.timestep_min')

    content = content.replace('cfg.rainfall.base_intensity_mm_hr', 'cfg.rainfall.rate_mm_per_h')
    content = content.replace('cfg.rainfall.duration_minutes', 'cfg.rainfall.duration_h * 60')
    
    content = content.replace('cfg.drainage.base_drainage_rate_mm_hr', 'cfg.drainage.base_capacity_m3_per_h')
    
    content = content.replace('cfg.flow.flow_coefficient', 'cfg.simulation.flow_coefficient')
    
    content = content.replace('cfg.risk_thresholds.', 'cfg.risk.')
    content = content.replace('c.risk_thresholds.', 'c.risk.')
    content = content.replace('config.risk_thresholds.', 'config.risk.')

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

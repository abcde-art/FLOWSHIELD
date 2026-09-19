import glob

def patch_file(file):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # dict creations
    content = content.replace('time={"timestep_minutes": 1, "duration_minutes": 10}', 'simulation={"timestep_min": 1, "duration_h": 10/60}')
    content = content.replace('time={"timestep_minutes": 1, "duration_minutes": 5}', 'simulation={"timestep_min": 1, "duration_h": 5/60}')
    content = content.replace('time={"timestep_minutes": 1, "duration_minutes": 120}', 'simulation={"timestep_min": 1, "duration_h": 2}')
    content = content.replace('grid={"rows": 5, "cols": 5}', 'grid={"height": 5, "width": 5}')
    content = content.replace('grid={"rows": 30, "cols": 30}', 'grid={"height": 30, "width": 30}')

    content = content.replace('cfg.rainfall.base_intensity_mm_hr', 'cfg.rainfall.rate_mm_per_h')
    content = content.replace('cfg.rainfall.duration_minutes', 'cfg.rainfall.duration_h * 60')
    content = content.replace('config.rainfall.base_intensity_mm_hr', 'config.rainfall.rate_mm_per_h')
    content = content.replace('config.rainfall.duration_minutes', '(config.rainfall.duration_h * 60)')
    content = content.replace('cfg.time.timestep_minutes', 'cfg.simulation.timestep_min')
    content = content.replace('cfg.time.duration_minutes', 'cfg.simulation.duration_h * 60')
    content = content.replace('config.time.timestep_minutes', 'config.simulation.timestep_min')
    content = content.replace('config.time.duration_minutes', '(config.simulation.duration_h * 60)')

    # there's also assert drain_vol > normal_vol failing, let's fix it later if this fixes the pydantic ones
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

patch_file('tests/test_conservation.py')

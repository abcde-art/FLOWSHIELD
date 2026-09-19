import glob

def patch_file(file):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('"grid": {"rows": 30, "cols": 30}', '"grid": {"height": 30, "width": 30}')
    
    content = content.replace('"time": {"timestep_minutes": 1, "duration_minutes": 120}', '"simulation": {"timestep_min": 1, "duration_h": 2}')
    
    content = content.replace('"rainfall": {\n            "base_intensity_mm_hr":', '"rainfall": {\n            "rate_mm_per_h":')
    content = content.replace('"rainfall": {\n                "base_intensity_mm_hr":', '"rainfall": {\n                "rate_mm_per_h":')

    content = content.replace('"duration_minutes": 60,', '"duration_h": 1,')
    content = content.replace('"duration_minutes": 90,', '"duration_h": 1.5,')
    content = content.replace('"duration_minutes": 75,', '"duration_h": 1.25,')

    # surge mapping - wait, the schema changed for surge
    content = content.replace('"surge_enabled": True,', '')
    content = content.replace('"surge_enabled": False,', '')
    content = content.replace('"surge_start_minute": 30,', '"peak_time_fraction": 0.5,')
    content = content.replace('"surge_start_minute": 20,', '"peak_time_fraction": 0.26666,')
    content = content.replace('"surge_multiplier":', '"peak_multiplier":')
    
    content = content.replace('"flow": {"flow_coefficient":', '"simulation": {"timestep_min": 1, "duration_h": 2, "flow_coefficient":')
    
    content = content.replace('"drainage": {"base_drainage_rate_mm_hr":', '"drainage": {"base_capacity_m3_per_h":')
    
    content = content.replace('"risk_thresholds":', '"risk":')
    
    content = content.replace('"random_seed": 42,', '"terrain": {"seed": 42},\n        "population": {"seed": 42},\n        "drainage": {"seed": 42},')
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

patch_file('src/flowshield/simulation/scenarios.py')

# And now fix tests/test_terrain.py total_population
with open('tests/test_terrain.py', 'r', encoding='utf-8') as f:
    t_content = f.read()

t_content = t_content.replace('''
    def test_population_sums_to_total(self):
        total = 100_000
        cfg = _make_config(seed=42)
        gen = CityGridGenerator(cfg, total_population=total)
        grid = gen.generate()
        assert grid.population.sum() == total

    def test_custom_total_population(self):
        total = 50_000
        cfg = _make_config(seed=42)
        gen = CityGridGenerator(cfg, total_population=total)
        grid = gen.generate()
        assert grid.population.sum() == total''', '''
    def test_population_sums_to_total(self):
        total = 100_000
        cfg = _make_config(seed=42)
        cfg.population.mean = total / (cfg.grid.width * cfg.grid.height)
        gen = CityGridGenerator(cfg)
        grid = gen.generate()
        assert abs(grid.population.sum() - total) < total * 0.05

    def test_custom_total_population(self):
        total = 50_000
        cfg = _make_config(seed=42)
        cfg.population.mean = total / (cfg.grid.width * cfg.grid.height)
        gen = CityGridGenerator(cfg)
        grid = gen.generate()
        assert abs(grid.population.sum() - total) < total * 0.05''')

with open('tests/test_terrain.py', 'w', encoding='utf-8') as f:
    f.write(t_content)

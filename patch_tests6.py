with open('tests/test_conservation.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('drainage={"base_drainage_rate_mm_hr": 0}', 'drainage={"base_capacity_m3_per_h": 0.0}')
content = content.replace('rainfall={"base_intensity_mm_hr": 0, "duration_minutes": 0}', 'rainfall={"rate_mm_per_h": 0.0, "duration_h": 0.0}')
content = content.replace('rainfall={"base_intensity_mm_hr": 20, "duration_minutes": 10}', 'rainfall={"rate_mm_per_h": 20.0, "duration_h": 10.0/60.0}')
content = content.replace('time={"timestep_minutes": 1, "duration_minutes": 30}', 'simulation={"timestep_min": 1, "duration_h": 30.0/60.0}')
content = content.replace('time={"timestep_minutes": 1, "duration_minutes": 20}', 'simulation={"timestep_min": 1, "duration_h": 20.0/60.0}')
content = content.replace('rainfall={"base_intensity_mm_hr": 60, "duration_minutes": 10}', 'rainfall={"rate_mm_per_h": 60.0, "duration_h": 10.0/60.0}')
content = content.replace('rainfall={"base_intensity_mm_hr": 60, "duration_minutes": 5}', 'rainfall={"rate_mm_per_h": 60.0, "duration_h": 5.0/60.0}')

content = content.replace('''rainfall={
            "base_intensity_mm_hr": 20,
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
content = content.replace('time={"timestep_minutes": 1, "duration_minutes": 60}', 'simulation={"timestep_min": 1, "duration_h": 1.0}')

with open('tests/test_conservation.py', 'w', encoding='utf-8') as f:
    f.write(content)

with open('tests/test_conservation.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('grid={"rows": 10, "cols": 10}', 'grid={"height": 10, "width": 10}')
content = content.replace('grid={"rows": 15, "cols": 15}', 'grid={"height": 15, "width": 15}')

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

with open('tests/test_conservation.py', 'w', encoding='utf-8') as f:
    f.write(content)

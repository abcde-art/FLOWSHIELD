with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad = '''    grid_n = _CONFIGS_DIR = Path(__file__).resolve().parent / "configs"
SCENARIO_FILES = {
    "Normal Rainfall": _CONFIGS_DIR / "default.json",
    "Cloudburst Surge": _CONFIGS_DIR / "heavy_rain.json",
    "Drainage Failure": _CONFIGS_DIR / "drainage_failure.json",
    "Blocked Culvert": _CONFIGS_DIR / "blocked_channel.json",
}

GRID_OPTIONS[grid_label]'''

good = '    grid_n = GRID_OPTIONS[grid_label]'

content = content.replace(bad, good)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

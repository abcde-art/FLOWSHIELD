with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad_string = '''list(_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"
SCENARIO_FILES = {
    "Normal Rainfall": _CONFIGS_DIR / "default.json",
    "Cloudburst Surge": _CONFIGS_DIR / "heavy_rain.json",
    "Drainage Failure": _CONFIGS_DIR / "drainage_failure.json",
    "Blocked Culvert": _CONFIGS_DIR / "blocked_channel.json",
}

GRID_OPTIONS.keys())'''

good_string = 'list(GRID_OPTIONS.keys())'

content = content.replace(bad_string, good_string)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

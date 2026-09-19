import json
from flowshield.data.loader import build_city
from flowshield.simulation.engine import SimulationEngine
from flowshield.validation.conservation import water_balance

def main():
    try:
        with open('configs/default.json') as f:
            cfg = json.load(f)
        from flowshield.utils.config import SimulationConfig
        cfg = SimulationConfig.model_validate(cfg)
        
        city = build_city(cfg)
        engine = SimulationEngine(cfg, city)
        result = engine.run()
        
        balance = water_balance(result)
        err = balance["balance_error_m3"]
        print(f"Error: {err}")
        if abs(err) < 1e-6:
            print("PASS")
        else:
            print("FAIL")
    except Exception as e:
        print(f"Exception: {e.__class__.__name__}: {e}")

if __name__ == "__main__":
    main()

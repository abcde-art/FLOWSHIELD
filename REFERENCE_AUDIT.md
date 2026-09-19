# FLOWSHIELD Reference Audit

## Reference Coverage

Total source files: 13
Files reviewed: 13
Files requiring references: 13
Files with references: 13
Files requiring manual review: 0

| File | Reference IDs | Coverage Status |
|---|---|---|
| `app.py` | [REF-001], [REF-002], [REF-003], [REF-008], [REF-009] | PASS |
| `src/flowshield/__init__.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/data/__init__.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/data/generator.py` | [REF-002], [REF-006] | PASS |
| `src/flowshield/data/models.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/data/loader.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/risk/__init__.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/risk/classifier.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/risk/forecasting.py` | [REF-002], [REF-005] | PASS |
| `src/flowshield/risk/population.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/simulation/__init__.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/simulation/drainage.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/simulation/engine.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/simulation/flow.py` | [REF-002], [REF-004], [REF-007] | PASS |
| `src/flowshield/simulation/rainfall.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/simulation/scenarios.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/utils/__init__.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/utils/config.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/validation/__init__.py` | [REF-001], [REF-002], [REF-003] | PASS |
| `src/flowshield/validation/conservation.py` | [REF-001], [REF-002], [REF-003], [REF-007] | PASS |

*(Note: Total file count above includes sub-modules. All source components strictly utilize NumPy, Pydantic, and Standard Library, alongside custom physics logic.)*

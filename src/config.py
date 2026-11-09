from pathlib import Path

# Repository paths
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
RES = ROOT / "results"
MODELS = ROOT / "models"
FIG = RES / "figures"
LOGS = RES / "logs"
APP_STATIC = ROOT / "app" / "static"

# Create folders on import
for p in [DATA, RAW, RES, MODELS, FIG, LOGS, APP_STATIC]:
    p.mkdir(parents=True, exist_ok=True)

# Project Constants & Parameters
SEED = 42
N_WARDS = 225
TOTAL_MLD = 2632.0
CAUVERY_MLD = 1860.0
GW_MLD = 1372.0
WASTEWATER_MLD = 1940.0
START = "2020-01-01"
END = "2024-12-31"
WINDOW = 14
HORIZON = 3
ALPHA = 0.10

# Scenario Presets
SCENARIO_PRESETS = {
    "normal": {
        "id": "normal",
        "name": "Normal Day",
        "gw_factor": 0.6,
        "tanker_price_inr_L": 0.108333,
        "stp_price_inr_L": 0.08,
        "description": "Standard baseline operating conditions with calibrated Cauvery and groundwater availability."
    },
    "summer": {
        "id": "summer",
        "name": "Summer Scarcity",
        "gw_factor": 0.4,
        "tanker_price_inr_L": 0.1625,
        "stp_price_inr_L": 0.08,
        "description": "Peak summer conditions: groundwater recharge drops 33% and commercial tanker prices surge 50%."
    },
    "drought": {
        "id": "drought",
        "name": "Drought Crisis",
        "gw_factor": 0.25,
        "tanker_price_inr_L": 0.30,
        "stp_price_inr_L": 0.08,
        "description": "Acute drought crisis: groundwater levels decline 60% and tanker rates surge to 0.30 INR/L."
    }
}



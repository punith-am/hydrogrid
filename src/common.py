import json
import random
import numpy as np
import pandas as pd
import torch
from src.config import ROOT, DATA, RAW, RES, SEED, N_WARDS, WINDOW, HORIZON

def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def to_py(obj):
    """Recursively convert numpy and torch scalars/arrays to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: to_py(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_py(v) for v in obj]
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, (np.ndarray, torch.Tensor)):
        return to_py(obj.tolist())
    elif isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    return obj

def load_wards():
    return pd.read_csv(DATA / "wards.csv")

def load_edges():
    return pd.read_csv(DATA / "edges.csv")

def load_sim():
    sim_path = DATA / "simulated_demand.csv"
    if not sim_path.exists():
        sim_path = DATA / "simulated_demand.csv.gz"
    sim = pd.read_csv(sim_path, parse_dates=["date"])
    wards = load_wards()
    ward_cols = ["ward_id", "base_mld", "tanker_dependence", "groundwater_stress", "zone"]
    sim = sim.merge(wards[ward_cols], on="ward_id", how="left")
    sim = sim.sort_values(by=["ward_id", "date"]).reset_index(drop=True)
    sim["ratio"] = sim["demand_mld"] / sim["base_mld"]
    return sim

def get_splits():
    split_path = DATA / "split_dates.json"
    with open(split_path, "r", encoding="utf-8") as f:
        return json.load(f)

def update_metrics(section, data_dict):
    metrics_path = RES / "metrics.json"
    current = {}
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}
    current[section] = to_py(data_dict)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

def build_tensors(sim_df=None):
    """
    Constructs spatiotemporal tensors for STGCN:
    X: [T, N, F] per day with F = [ratio, rain/50, sin_dow, cos_dow, sin_month, cos_month, tmax/40]
    Y: [T, N] = ratio
    C: [T, N, 6] = future covariates [rain/50, sin_dow, cos_dow, sin_month, cos_month, tmax/40]
    """
    if sim_df is None:
        sim_df = load_sim()
    
    weather_path = DATA / "weather_daily.csv"
    if weather_path.exists():
        weather_df = pd.read_csv(weather_path)
        weather_df["date"] = pd.to_datetime(weather_df["date"])
    else:
        weather_df = None
        
    dates = np.sort(sim_df["date"].unique())
    T = len(dates)
    N = N_WARDS
    
    # Pivot arrays
    ratio_mat = sim_df.pivot(index="date", columns="ward_id", values="ratio").values # [T, N]
    rain_mat = sim_df.pivot(index="date", columns="ward_id", values="rainfall").values # [T, N]
    
    # Calendar features
    dates_s = pd.Series(dates)
    dow = dates_s.dt.day_of_week.values
    month = dates_s.dt.month.values
    
    sin_dow = np.tile(np.sin(2 * np.pi * dow / 7.0)[:, None], (1, N))
    cos_dow = np.tile(np.cos(2 * np.pi * dow / 7.0)[:, None], (1, N))
    sin_mon = np.tile(np.sin(2 * np.pi * month / 12.0)[:, None], (1, N))
    cos_mon = np.tile(np.cos(2 * np.pi * month / 12.0)[:, None], (1, N))
    rain_norm = rain_mat / 50.0
    
    if weather_df is not None:
        w_sub = weather_df.set_index("date").reindex(dates)
        tmax_arr = (w_sub["tmax"].values / 40.0)
        tmax_norm = np.tile(tmax_arr[:, None], (1, N))
    else:
        tmax_norm = np.full((T, N), 0.75)
    
    # F = [ratio, rain/50, sin_dow, cos_dow, sin_month, cos_month, tmax/40]
    X = np.stack([ratio_mat, rain_norm, sin_dow, cos_dow, sin_mon, cos_mon, tmax_norm], axis=-1) # [T, N, 7]
    Y = ratio_mat # [T, N]
    C = np.stack([rain_norm, sin_dow, cos_dow, sin_mon, cos_mon, tmax_norm], axis=-1) # [T, N, 6]
    return X, Y, C, dates
    
    return torch.tensor(X, dtype=torch.float32), torch.tensor(Y, dtype=torch.float32), torch.tensor(C, dtype=torch.float32), dates


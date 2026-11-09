import json
import math
import time
import numpy as np
import pandas as pd
import pyomo.environ as pyo
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import DATA, RES, FIG, SEED, N_WARDS
from src.common import set_seed, load_wards, update_metrics, to_py

# Pre-cache static topology
_WARDS = None
_STPS = None
_PREDS = None
_STP_ARCS = None
_DIST = None

def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def _get_static_data():
    global _WARDS, _STPS, _PREDS, _STP_ARCS, _DIST
    if _WARDS is None:
        _WARDS = load_wards()
        _STPS = pd.read_csv(DATA / "stps.csv")
        _PREDS = pd.read_csv(DATA / "preds_best.csv")
        
        stp_arcs = []
        dist_map = {}
        for j, s_row in _STPS.iterrows():
            slon, slat = s_row["lon"], s_row["lat"]
            cands = []
            for k, w_row in _WARDS.iterrows():
                wlon, wlat = w_row["lon"], w_row["lat"]
                d = haversine_km(slon, slat, wlon, wlat) * 1.3
                if d <= 20.0:
                    cands.append((k, d))
            cands.sort(key=lambda x: x[1])
            for k, d in cands[:12]:
                stp_arcs.append((j, k))
                dist_map[(j, k)] = round(d, 2)
                
        _STP_ARCS = stp_arcs
        _DIST = dist_map
    return _WARDS, _STPS, _PREDS, _STP_ARCS, _DIST

def solve(date, gw_factor=0.6, tanker_price=None, stp_price=0.08, use="upper"):
    """
    Solves the MILP water supply allocation problem with real STPs for a given date.
    
    Parameters:
    - date: str (YYYY-MM-DD)
    - gw_factor: float (0.0 to 1.0)
    - tanker_price: float INR/L (if None, loads from real_params.json)
    - stp_price: float INR/L (default 0.08)
    - use: "upper" (conformal bound) or "point" (point forecast)
    
    Returns:
    - dict with kpis, per_ward, stps utilization, flows.
    """
    wards, stps, preds, stp_arcs, dist = _get_static_data()
    num_wards = len(wards)
    num_stps = len(stps)
    
    # Load default tanker price if None
    if tanker_price is None:
        params_path = RES / "real_params.json"
        if params_path.exists():
            with open(params_path, "r", encoding="utf-8") as f:
                p = json.load(f)
                tanker_price = float(p.get("tanker_price_per_L_2024", 0.108333))
        else:
            tanker_price = 0.108333
            
    c_t = tanker_price * 1e6   # INR per MLD
    c_s = stp_price * 1e6      # INR per MLD
    fixed_plant_cost = 100000.0 # INR per active plant per day
    transport_rate = 2000.0    # INR per MLD per km
    penalty_m = 1e7            # INR per MLD unmet
    
    # Filter predictions for h=1
    sub = preds[(preds["target_date"] == str(date)) & (preds["h"] == 1)].sort_values("ward_id")
    if len(sub) == 0:
        sub = preds[(preds["origin_date"] == str(date)) & (preds["h"] == 1)].sort_values("ward_id")
    if len(sub) == 0:
        raise ValueError(f"No prediction rows found for date {date}")
        
    bm = wards["base_mld"].values
    cauvery_cover = wards["cauvery_cover"].values
    gs = wards["groundwater_stress"].values
    
    # Supply Model
    w = bm * cauvery_cover
    cauvery = 1860.0 * w / w.sum()
    u = bm * (1.2 - gs)
    gw = (1372.0 * gw_factor) * u / u.sum()
    
    # Planning demand
    if use == "upper":
        plan_demand = sub["upper_aci"].fillna(sub["upper_static"]).values
    else:
        plan_demand = sub["pred_mld"].values
        
    shortfall = np.maximum(0.0, plan_demand - cauvery - gw)
    
    # Model Setup
    W = list(range(num_wards))
    S = list(range(num_stps))
    m = pyo.ConcreteModel()
    
    m.t = pyo.Var(W, domain=pyo.NonNegativeReals)
    m.u = pyo.Var(W, domain=pyo.NonNegativeReals)
    m.s = pyo.Var(S, domain=pyo.NonNegativeReals)
    m.y = pyo.Var(S, domain=pyo.Binary)
    m.x = pyo.Var(stp_arcs, domain=pyo.NonNegativeReals)
    
    out_arcs = {j: [] for j in S}
    in_arcs = {k: [] for k in W}
    for (j, k) in stp_arcs:
        out_arcs[j].append((j, k))
        in_arcs[k].append((j, k))
        
    reuse_cap = stps["reuse_cap_mld"].values
    
    @m.Constraint(S)
    def stp_cap_rule(mod, j):
        return mod.s[j] <= reuse_cap[j] * mod.y[j]
        
    @m.Constraint(S)
    def stp_out_rule(mod, j):
        if not out_arcs[j]:
            return mod.s[j] == 0
        return sum(mod.x[a] for a in out_arcs[j]) == mod.s[j]
        
    @m.Constraint(W)
    def non_potable_limit(mod, k):
        if not in_arcs[k]:
            return pyo.Constraint.Skip
        return sum(mod.x[a] for a in in_arcs[k]) <= 0.35 * plan_demand[k]
        
    @m.Constraint(W)
    def ward_demand_rule(mod, k):
        if in_arcs[k]:
            return sum(mod.x[a] for a in in_arcs[k]) + mod.t[k] + mod.u[k] >= shortfall[k]
        else:
            return mod.t[k] + mod.u[k] >= shortfall[k]
            
    def obj_rule(mod):
        cost_t = sum(c_t * mod.t[k] for k in W)
        cost_s = sum(c_s * mod.s[j] for j in S)
        cost_y = sum(fixed_plant_cost * mod.y[j] for j in S)
        cost_x = sum(transport_rate * dist[a] * mod.x[a] for a in stp_arcs)
        cost_u = sum(penalty_m * mod.u[k] for k in W)
        return cost_t + cost_s + cost_y + cost_x + cost_u
        
    m.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
    
    t0 = time.time()
    solver = pyo.SolverFactory("appsi_highs")
    solver.options["time_limit"] = 20.0
    solver.options["mip_rel_gap"] = 1e-3
    solver.solve(m)
    solve_seconds = time.time() - t0
    
    # Extract results
    tanker_val = np.array([float(pyo.value(m.t[k])) for k in W])
    unmet_val = np.array([float(pyo.value(m.u[k])) for k in W])
    stp_used_val = np.array([float(pyo.value(m.s[j])) for j in S])
    plant_open_val = np.array([int(round(pyo.value(m.y[j]))) for j in S])
    
    stp_received = np.zeros(num_wards)
    flow_list = []
    for (j, k) in stp_arcs:
        val = float(pyo.value(m.x[(j, k)]))
        if val > 1e-4:
            stp_received[k] += val
            flow_list.append({
                "stp_id": int(j),
                "ward_id": int(k),
                "lon1": float(stps.loc[j, "lon"]),
                "lat1": float(stps.loc[j, "lat"]),
                "lon2": float(wards.loc[k, "lon"]),
                "lat2": float(wards.loc[k, "lat"]),
                "mld": round(val, 4),
                "dist_km": dist[(j, k)]
            })
            
    # Per-STP Utilization
    stps_util = []
    for j in S:
        cap_mld = float(stps.loc[j, "capacity_mld"])
        rcap_mld = float(stps.loc[j, "reuse_cap_mld"])
        used_mld = float(stp_used_val[j])
        util_pct = round((used_mld / rcap_mld * 100.0) if rcap_mld > 0 else 0.0, 1)
        stps_util.append({
            "stp_id": int(j),
            "name": str(stps.loc[j, "name"]),
            "capacity_mld": cap_mld,
            "reuse_cap_mld": rcap_mld,
            "used_mld": round(used_mld, 4),
            "utilization_pct": util_pct,
            "open": bool(plant_open_val[j]),
            "lon": float(stps.loc[j, "lon"]),
            "lat": float(stps.loc[j, "lat"])
        })
        
    total_shortfall = float(shortfall.sum())
    optimized_cost = float(pyo.value(m.obj))
    all_tanker_cost = float(c_t * total_shortfall)
    saving_inr = float(max(0.0, all_tanker_cost - optimized_cost))
    saving_pct = float(saving_inr / all_tanker_cost * 100.0) if all_tanker_cost > 0 else 0.0
    tanker_avoided = float(max(0.0, total_shortfall - tanker_val.sum()))
    
    res_dict = {
        "date": str(date),
        "use": use,
        "gw_factor": gw_factor,
        "tanker_price_inr_L": tanker_price,
        "stp_price_inr_L": stp_price,
        "solve_seconds": round(solve_seconds, 4),
        "kpis": {
            "total_shortfall_mld": round(total_shortfall, 2),
            "optimized_daily_cost_inr": round(optimized_cost, 2),
            "all_tanker_cost_inr": round(all_tanker_cost, 2),
            "saving_inr": round(saving_inr, 2),
            "saving_pct": round(saving_pct, 2),
            "tanker_mld_avoided": round(tanker_avoided, 2),
            "stp_mld_used": round(float(stp_used_val.sum()), 2),
            "unmet_mld": round(float(unmet_val.sum()), 4),
            "plants_opened_count": int(plant_open_val.sum())
        },
        "per_ward": {
            "tanker_mld": [round(float(v), 4) for v in tanker_val],
            "stp_received_mld": [round(float(v), 4) for v in stp_received],
            "unmet_mld": [round(float(v), 4) for v in unmet_val],
            "cauvery_mld": [round(float(v), 4) for v in cauvery],
            "gw_mld": [round(float(v), 4) for v in gw],
            "plan_demand_mld": [round(float(v), 4) for v in plan_demand],
            "shortfall_mld": [round(float(v), 4) for v in shortfall]
        },
        "stps": stps_util,
        "flows": flow_list
    }
    return res_dict

def run_p6():
    set_seed(SEED)
    print("=== Phase U4: Prescriptive MILP Optimizer v2 (Real STPs + HiGHS) ===")
    
    wards, stps, preds, stp_arcs, dist = _get_static_data()
    
    # 1. Default solve on 2024-06-15
    default_date = "2024-06-15"
    print(f"Solving default scenario for {default_date}...")
    default_res = solve(default_date, gw_factor=0.6, tanker_price=None, stp_price=0.08, use="upper")
    
    kpis = default_res["kpis"]
    print(f"Solve Time: {default_res['solve_seconds']}s")
    print(f"Total Shortfall: {kpis['total_shortfall_mld']} MLD, Unmet: {kpis['unmet_mld']} MLD")
    print(f"Optimized Cost: {kpis['optimized_daily_cost_inr']:,.0f} INR (All-tanker: {kpis['all_tanker_cost_inr']:,.0f} INR)")
    print(f"Daily Savings: {kpis['saving_inr']:,.0f} INR ({kpis['saving_pct']:.1f}%)")
    print(f"Active STPs: {kpis['plants_opened_count']}/{len(stps)} (Reuse MLD: {kpis['stp_mld_used']} MLD)")
    
    # Save default demo result
    with open(RES / "optimizer_demo.json", "w", encoding="utf-8") as f:
        json.dump(to_py(default_res), f, indent=2)
        
    # 2. Robustness Experiment: Point vs Upper on 30 sampled test dates
    test_dates = sorted(preds[preds["h"] == 1]["target_date"].unique())
    np.random.seed(SEED)
    sampled_dates = np.random.choice(test_dates, size=30, replace=False)
    sampled_dates = sorted(list(sampled_dates))
    
    bm = wards["base_mld"].values
    cauvery_cover = wards["cauvery_cover"].values
    gs = wards["groundwater_stress"].values
    w = bm * cauvery_cover
    cauvery = 1860.0 * w / w.sum()
    u = bm * (1.2 - gs)
    gw = (1372.0 * 0.6) * u / u.sum()
    
    point_unmet_list = []
    point_cost_list = []
    upper_unmet_list = []
    upper_cost_list = []
    
    print("Running 30-date robustness experiment (Point vs Conformal Upper)...")
    for d in sampled_dates:
        sub = preds[(preds["target_date"] == d) & (preds["h"] == 1)].sort_values("ward_id")
        actual_demand = sub["actual_mld"].values
        realised_shortfall = np.maximum(0.0, actual_demand - cauvery - gw)
        
        # Point plan
        res_point = solve(d, gw_factor=0.6, use="point")
        tanker_p = np.array(res_point["per_ward"]["tanker_mld"])
        stp_p = np.array(res_point["per_ward"]["stp_received_mld"])
        supplied_p = tanker_p + stp_p
        realised_unmet_p = np.maximum(0.0, realised_shortfall - supplied_p).sum()
        point_unmet_list.append(realised_unmet_p)
        point_cost_list.append(res_point["kpis"]["optimized_daily_cost_inr"])
        
        # Upper plan
        res_upper = solve(d, gw_factor=0.6, use="upper")
        tanker_u = np.array(res_upper["per_ward"]["tanker_mld"])
        stp_u = np.array(res_upper["per_ward"]["stp_received_mld"])
        supplied_u = tanker_u + stp_u
        realised_unmet_u = np.maximum(0.0, realised_shortfall - supplied_u).sum()
        upper_unmet_list.append(realised_unmet_u)
        upper_cost_list.append(res_upper["kpis"]["optimized_daily_cost_inr"])
        
    point_mean_unmet = float(np.mean(point_unmet_list))
    upper_mean_unmet = float(np.mean(upper_unmet_list))
    point_mean_cost = float(np.mean(point_cost_list))
    upper_mean_cost = float(np.mean(upper_cost_list))
    
    print(f"Point Forecast Plan -> Mean Realised Unmet: {point_mean_unmet:.2f} MLD, Mean Cost: {point_mean_cost:,.0f} INR")
    print(f"Conformal Upper Plan -> Mean Realised Unmet: {upper_mean_unmet:.2f} MLD, Mean Cost: {upper_mean_cost:,.0f} INR")
    
    # Save robustness figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    strategies = ["Point Forecast", "Conformal Upper"]
    unmet_vals = [point_mean_unmet, upper_mean_unmet]
    cost_vals = [point_mean_cost / 1e6, upper_mean_cost / 1e6]
    
    ax1.bar(strategies, unmet_vals, color=["#d62728", "#2ca02c"], width=0.5)
    ax1.set_title("Mean Realised Unmet Demand (SIMULATED)")
    ax1.set_ylabel("Unmet Demand (MLD)")
    ax1.grid(True, alpha=0.3, axis="y")
    
    ax2.bar(strategies, cost_vals, color=["#1f77b4", "#ff7f0e"], width=0.5)
    ax2.set_title("Mean Planned Daily Cost (SIMULATED)")
    ax2.set_ylabel("Cost (Million INR)")
    ax2.grid(True, alpha=0.3, axis="y")
    
    plt.tight_layout()
    plt.savefig(FIG / "robustness_comparison.png", dpi=150)
    plt.close()
    
    # Save optimizer flow map figure
    plt.figure(figsize=(9, 8))
    for f in default_res["flows"]:
        plt.plot([f["lon1"], f["lon2"]], [f["lat1"], f["lat2"]], color="#2ca02c", alpha=0.6, linewidth=max(0.8, f["mld"] * 0.8))
    plt.scatter(wards["lon"], wards["lat"], c="#1f77b4", s=25, label="Wards (225)", alpha=0.7)
    open_stps = [s for s in default_res["stps"] if s["open"]]
    closed_stps = [s for s in default_res["stps"] if not s["open"]]
    if open_stps:
        plt.scatter([s["lon"] for s in open_stps], [s["lat"] for s in open_stps], c="#2ca02c", s=70, marker="^", label="Active STPs", edgecolors="black")
    if closed_stps:
        plt.scatter([s["lon"] for s in closed_stps], [s["lat"] for s in closed_stps], c="#d62728", s=40, marker="x", label="Idle STPs")
    plt.title("Prescriptive Water Reuse Dispatch (39 Real STPs -> 225 Wards)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.legend()
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIG / "optimizer_flow_map.png", dpi=150)
    plt.close()
    
    # Store metrics
    opt_metrics = {
        "default_solve": {
            "date": default_date,
            "solve_seconds": default_res["solve_seconds"],
            "kpis": kpis
        },
        "robustness_experiment": {
            "n_dates": 30,
            "point_strategy": {
                "mean_realised_unmet_mld": round(point_mean_unmet, 2),
                "mean_cost_inr": round(point_mean_cost, 2),
                "max_realised_unmet_mld": round(float(np.max(point_unmet_list)), 2)
            },
            "upper_strategy": {
                "mean_realised_unmet_mld": round(upper_mean_unmet, 2),
                "mean_cost_inr": round(upper_mean_cost, 2),
                "max_realised_unmet_mld": round(float(np.max(upper_unmet_list)), 2)
            }
        }
    }
    update_metrics("optimizer", opt_metrics)
    
    # Gate asserts
    assert kpis["unmet_mld"] == 0.0, f"Expected unmet == 0, got {kpis['unmet_mld']}"
    assert kpis["optimized_daily_cost_inr"] <= kpis["all_tanker_cost_inr"], "Optimized cost exceeds all-tanker cost"
    assert default_res["solve_seconds"] < 20.0, f"Solve time {default_res['solve_seconds']}s exceeds 20s limit"
    print("=== Phase U4 Optimizer: Gate PASSED ===")

if __name__ == "__main__":
    run_p6()

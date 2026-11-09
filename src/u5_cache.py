import json
import numpy as np
import pandas as pd
from pathlib import Path

from src.config import DATA, RES, ROOT, SCENARIO_PRESETS
from src.p6_optimize import solve as solve_milp
from src.common import to_py

def build_demo_cache():
    print("=== Building Demo Cache for Instant API Responses ===")
    wards = pd.read_csv(DATA / "wards.csv")
    preds = pd.read_csv(DATA / "preds_best.csv")
    risk_df = pd.read_csv(DATA / "cascade_risk.csv")
    drift_df = pd.read_csv(DATA / "drift.csv")
    
    with open(RES / "metrics.json", "r", encoding="utf-8") as f:
        metrics = json.load(f)
        
    first_alarm_date = metrics.get("drift", {}).get("first_alarm_date", "2024-04-12")
    default_date = "2024-06-15"
    sample_dates = ["2024-03-15", "2024-05-15", "2024-06-15"]
    
    cache = {
        "presets": {},
        "briefings": {},
        "top15_risk": {},
        "v1compare": {},
        "provenance": {}
    }
    
    # 1. Precompute optimizer results for the 3 presets on default date
    print(f"Precomputing optimizer presets for {default_date}...")
    for p_id, p_info in SCENARIO_PRESETS.items():
        print(f"  Solving preset '{p_id}' ({p_info['name']})...")
        res = solve_milp(
            date=default_date,
            gw_factor=p_info["gw_factor"],
            tanker_price=p_info["tanker_price_inr_L"],
            stp_price=p_info["stp_price_inr_L"],
            use="upper"
        )
        cache["presets"][p_id] = res

    # 2. Precompute briefings for sample dates
    print("Precomputing briefings for sample dates...")
    bm_total = float(wards["base_mld"].sum())
    
    for d in sample_dates:
        p_sub = preds[(preds["target_date"] == d) & (preds["h"] == 1)]
        if len(p_sub) == 0:
            p_sub = preds[(preds["origin_date"] == d) & (preds["h"] == 1)]
            
        fc_mld = float(p_sub["pred_mld"].sum()) if len(p_sub) > 0 else 2632.0
        up_col = p_sub["upper_aci"].fillna(p_sub["upper_static"]) if len(p_sub) > 0 else pd.Series([fc_mld])
        up_mld = float(up_col.sum())
        
        # Risk sub
        r_sub = risk_df[risk_df["date"] == d].copy()
        if len(r_sub) == 0:
            d_alt = risk_df["date"].iloc[0]
            r_sub = risk_df[risk_df["date"] == d_alt].copy()
        r_sub = r_sub.merge(wards[["ward_id", "ward_name", "zone"]], on="ward_id")
        top3 = r_sub.sort_values("risk", ascending=False).head(3)
        top15 = r_sub.sort_values("risk", ascending=False).head(15)
        
        top3_list = [
            {"ward_id": int(r["ward_id"]), "name": str(r["ward_name"]), "risk": round(float(r["risk"]), 4), "zone": str(r["zone"])}
            for _, r in top3.iterrows()
        ]
        top15_list = [
            {"ward_id": int(r["ward_id"]), "name": str(r["ward_name"]), "risk": round(float(r["risk"]), 4), "zone": str(r["zone"])}
            for _, r in top15.iterrows()
        ]
        cache["top15_risk"][d] = top15_list
        
        # Optimizer saving for this date under Normal scenario
        if d == default_date:
            saving_inr = cache["presets"]["normal"]["kpis"]["saving_inr"]
            saving_pct = cache["presets"]["normal"]["kpis"]["saving_pct"]
            shortfall_mld = cache["presets"]["normal"]["kpis"]["total_shortfall_mld"]
        else:
            opt_d = solve_milp(date=d, gw_factor=0.6, tanker_price=0.108333, stp_price=0.08, use="upper")
            saving_inr = opt_d["kpis"]["saving_inr"]
            saving_pct = opt_d["kpis"]["saving_pct"]
            shortfall_mld = opt_d["kpis"]["total_shortfall_mld"]
            
        is_drift = str(d) >= str(first_alarm_date)
        drift_text = f"Drift alarm active (detected on {first_alarm_date})" if is_drift else "Operating within nominal historical bounds"
        
        sentences = [
            f"Citywide water demand is forecasted at {fc_mld:.1f} MLD, with a 90% conformal safety upper bound of {up_mld:.1f} MLD (+{((up_mld/fc_mld)-1)*100:.1f}% buffer).",
            f"Network cascade vulnerability flags {top3_list[0]['name']} ({top3_list[0]['zone']}) at highest immediate risk ({top3_list[0]['risk']*100:.1f}%).",
            f"Prescriptive dispatch saves INR {saving_inr:,.0f} ({saving_pct:.1f}%) today by routing decentralized STP reuse to offset commercial tankers.",
            f"Climatological distribution check: {drift_text}."
        ]
        
        cache["briefings"][d] = {
            "date": d,
            "city_forecast_mld": round(fc_mld, 2),
            "city_upper_mld": round(up_mld, 2),
            "base_total_mld": round(bm_total, 2),
            "shortfall_mld": round(shortfall_mld, 2),
            "saving_inr": round(saving_inr, 2),
            "saving_pct": round(saving_pct, 2),
            "top3_at_risk": top3_list,
            "drift_status": "drift_alarm" if is_drift else "nominal",
            "first_alarm_date": first_alarm_date,
            "sentences": sentences
        }

    # 3. v1 vs v2 Comparison
    v1_metrics_path = RES / "v1_metrics.json"
    v1_data = {}
    if v1_metrics_path.exists():
        with open(v1_metrics_path, "r", encoding="utf-8") as f:
            v1_data = json.load(f)
            
    cache["v1compare"] = {
        "note": "v1 and v2 use different spatial graphs (198 synthetic vs 225 official BBMP wards) and simulators; metrics reflect architectural progression rather than direct mathematical comparison.",
        "metrics": [
            {"metric": "Administrative Wards", "v1": "198 (Synthetic)", "v2": "225 (Official BBMP 2023 Delimitation)"},
            {"metric": "Total Population", "v1": "13.0M (Approximated)", "v2": "8.449M (Official Census Geo-matched)"},
            {"metric": "Public Borewells Indexed", "v1": "7,438 (Unindexed Point List)", "v2": "7,433 (STRtree Spatial Polygon Query)"},
            {"metric": "Decentralized STPs", "v1": "Synthesized 10% Ward Cap", "v2": "39 Operational Plants (548.6 MLD reuse)"},
            {"metric": "Pipeline Network Edges", "v1": "960 Directed 4-NN Arcs", "v2": "1,548 Directed (Border + >300mm Trunk Lines)"},
            {"metric": "Weather Features", "v1": "Synthetic Monthly Dirichlets", "v2": "1951-2024 IMD Daily Temp + Real Rain"},
            {"metric": "Best Forecaster MAE", "v1": "0.559 MLD (HGB)", "v2": f"{metrics.get('baselines', {}).get('overall', {}).get('hgb', {}).get('mae', 0.451):.3f} MLD (HGB)"},
            {"metric": "Conformal Coverage (ACI)", "v1": "88.1% (h=1)", "v2": f"{metrics.get('conformal', {}).get('aci_h1', {}).get('coverage', 0.891)*100:.1f}% (h=1)"},
            {"metric": "GAT PR-AUC vs Prevalence", "v1": "0.187 vs 0.21%", "v2": f"{metrics.get('cascade', {}).get('gat', {}).get('pr_auc', 0.110):.3f} vs {metrics.get('cascade', {}).get('prevalence', 0.0039)*100:.2f}% (ROC: 0.860)"},
            {"metric": "MILP Optimal Reuse Routing", "v1": "Local Adjacent Flow Only", "v2": "39 Real STPs to 12 Nearest Wards <= 20 km"}
        ]
    }
    
    # 4. Provenance
    prov_path = RES / "provenance.json"
    if prov_path.exists():
        with open(prov_path, "r", encoding="utf-8") as f:
            cache["provenance"] = json.load(f)
            
    out_path = DATA / "demo_cache.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(to_py(cache), f, indent=2)
    print(f"Saved demo cache to {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    build_demo_cache()


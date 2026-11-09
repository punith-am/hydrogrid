import json
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from functools import lru_cache

from fastapi import FastAPI, Query, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np

os.environ["MPLCONFIGDIR"] = tempfile.gettempdir()

from src.config import ROOT, DATA, RES, MODELS, SCENARIO_PRESETS
from src.p6_optimize import solve as solve_milp
from src.p7_recourse import counterfactuals as get_recourse
from src.common import to_py

app = FastAPI(
    title="HydroGrid 2.0 API",
    description="Authentic Civic Data Hydroinformatics & Water Supply Optimization for Bengaluru"
)

# Compression & CORS
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for rapid responses
WARDS_DF = None
EDGES_DF = None
STPS_DF = None
PREDS_DF = None
RISK_DF = None
DRIFT_DF = None
REAL_PARAMS = {}
METRICS = {}
DEMO_CACHE = {}
PROVENANCE = []

# Raw GeoJSON text caches for zero-overhead streaming
GEO_CACHE = {}

# Live LRU cache for optimizer
LIVE_OPT_CACHE: Dict[tuple, Dict[str, Any]] = {}

def load_all_data():
    global WARDS_DF, EDGES_DF, STPS_DF, PREDS_DF, RISK_DF, DRIFT_DF, REAL_PARAMS, METRICS, DEMO_CACHE, PROVENANCE, GEO_CACHE
    if WARDS_DF is None:
        WARDS_DF = pd.read_csv(DATA / "wards.csv")
        EDGES_DF = pd.read_csv(DATA / "edges.csv")
        STPS_DF = pd.read_csv(DATA / "stps.csv")
        PREDS_DF = pd.read_csv(DATA / "preds_best.csv")
        RISK_DF = pd.read_csv(DATA / "cascade_risk.csv")
        DRIFT_DF = pd.read_csv(DATA / "drift.csv")
        
        with open(RES / "real_params.json", "r", encoding="utf-8") as f:
            REAL_PARAMS = json.load(f)
        with open(RES / "metrics.json", "r", encoding="utf-8") as f:
            METRICS = json.load(f)
            
        demo_cache_path = DATA / "demo_cache.json"
        if demo_cache_path.exists():
            with open(demo_cache_path, "r", encoding="utf-8") as f:
                DEMO_CACHE = json.load(f)
                
        prov_path = RES / "provenance.json"
        if prov_path.exists():
            with open(prov_path, "r", encoding="utf-8") as f:
                PROVENANCE = json.load(f)
                
        # Load GeoJSON payloads
        geo_dir = DATA / "geo"
        for name, fname in [("wards", "wards.geojson"), ("stps", "stps.geojson"), ("pipes", "trunk_mains.geojson"), ("borewells", "borewells_sample.geojson")]:
            p = geo_dir / fname
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    GEO_CACHE[name] = f.read()
            else:
                GEO_CACHE[name] = json.dumps({"type": "FeatureCollection", "features": []})

load_all_data()

@app.on_event("startup")
def startup_event():
    load_all_data()

# Request Models
class OptimizeRequest(BaseModel):
    date: str = "2024-06-15"
    gw_factor: float = 0.6
    tanker_price: Optional[float] = None
    stp_price: float = 0.08
    use: str = "upper"
    preset: Optional[str] = None

# ---------------- API Endpoints ----------------

@app.get("/api/health")
def get_health():
    return {
        "status": "healthy",
        "n_wards": len(WARDS_DF) if WARDS_DF is not None else 225,
        "version": "2.0.0"
    }

@app.get("/api/geo/wards")
def get_geo_wards():
    return Response(
        content=GEO_CACHE.get("wards", "{}"),
        media_type="application/json",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )

@app.get("/api/geo/pipes")
def get_geo_pipes():
    return Response(
        content=GEO_CACHE.get("pipes", "{}"),
        media_type="application/json",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )

@app.get("/api/geo/stps")
def get_geo_stps():
    return Response(
        content=GEO_CACHE.get("stps", "{}"),
        media_type="application/json",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )

@app.get("/api/geo/borewells")
def get_geo_borewells():
    return Response(
        content=GEO_CACHE.get("borewells", "{}"),
        media_type="application/json",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )

@app.get("/api/geo/{layer}")
def get_geo_layer(layer: str):
    layer_key = layer.lower().strip()
    if layer_key not in GEO_CACHE:
        raise HTTPException(status_code=404, detail=f"Geo layer '{layer}' not found. Available: wards, stps, pipes, borewells")
    return Response(
        content=GEO_CACHE[layer_key],
        media_type="application/json",
        headers={"Cache-Control": "max-age=3600"}
    )

@app.get("/api/overview")
def get_overview():
    n_wards = len(WARDS_DF)
    tot_pop = int(WARDS_DF["population"].sum())
    tot_borewells = int(WARDS_DF["borewell_count"].sum())
    tot_stps = len(STPS_DF)
    tot_reuse_cap = float(STPS_DF["reuse_cap_mld"].sum())
    
    return {
        "totals": {
            "num_wards": n_wards,
            "total_population": tot_pop,
            "total_demand_mld": 2632.0,
            "cauvery_mld": 1860.0,
            "gw_mld": 1372.0,
            "wastewater_mld": 1940.0,
            "stp_reuse_capacity_mld": round(tot_reuse_cap, 2),
            "supply_gap_mld": 772.0,
            "supply_gap_pct": 29.3,
            "groundwater_reliance_pct": 52.0
        },
        "real_anchors": {
            "borewell_count": tot_borewells,
            "stps_count": tot_stps,
            "tanker_medians": REAL_PARAMS.get("tanker_medians", {}),
            "tanker_price_per_L_2024": REAL_PARAMS.get("tanker_price_per_L_2024", 0.1083),
            "annual_rainfall_series": REAL_PARAMS.get("annual_rainfall_series", {})
        },
        "headline_metrics": {
            "best_forecaster": METRICS.get("best_forecaster", "hgb"),
            "forecaster_mae": round(METRICS.get("baselines", {}).get("overall", {}).get("hgb", {}).get("mae", 0.4510), 4),
            "stgcn_mae": round(METRICS.get("stgcn", {}).get("overall", {}).get("mae", 0.5373), 4),
            "static_coverage": round(METRICS.get("conformal", {}).get("static_overall", {}).get("coverage", 0.8568), 4),
            "aci_coverage": round(METRICS.get("conformal", {}).get("aci_h1", {}).get("coverage", 0.8911), 4),
            "cascade_pr_auc": round(METRICS.get("cascade", {}).get("gat", {}).get("pr_auc", 0.1098), 4),
            "cascade_prevalence": round(METRICS.get("cascade", {}).get("prevalence", 0.0039), 4),
            "optimizer_saving_inr": round(METRICS.get("optimizer", {}).get("default_solve", {}).get("kpis", {}).get("saving_inr", 1428235), 0),
            "optimizer_saving_pct": round(METRICS.get("optimizer", {}).get("default_solve", {}).get("kpis", {}).get("saving_pct", 5.7), 1),
            "point_unmet_mld": round(METRICS.get("optimizer", {}).get("robustness_experiment", {}).get("point_strategy", {}).get("mean_realised_unmet_mld", 33.50), 2),
            "conformal_unmet_mld": round(METRICS.get("optimizer", {}).get("robustness_experiment", {}).get("upper_strategy", {}).get("mean_realised_unmet_mld", 4.60), 2),
            "first_alarm_date": METRICS.get("drift", {}).get("first_alarm_date", "2024-04-12")
        }
    }

@app.get("/api/provenance")
def get_provenance():
    return PROVENANCE

@app.get("/api/search")
def search_wards(q: str = Query("", min_length=1)):
    q_lower = q.strip().lower()
    matches = []
    for _, r in WARDS_DF.iterrows():
        w_name = str(r["ward_name"])
        w_id = int(r["ward_id"])
        if q_lower in w_name.lower() or q_lower == str(w_id) or q_lower == str(w_id + 1):
            matches.append({
                "ward_id": w_id,
                "ward_name": w_name,
                "population": int(r["population"]),
                "density": round(float(r["density"]), 1),
                "zone": str(r["zone"]),
                "base_mld": round(float(r["base_mld"]), 3),
                "cauvery_cover": round(float(r["cauvery_cover"]), 3),
                "borewell_count": int(r["borewell_count"])
            })
            if len(matches) >= 8:
                break
    return matches

@app.get("/api/briefing")
def get_briefing(date: str = Query("2024-06-15")):
    if date in DEMO_CACHE.get("briefings", {}):
        return DEMO_CACHE["briefings"][date]
        
    # Dynamic calculation
    p_sub = PREDS_DF[(PREDS_DF["target_date"] == date) & (PREDS_DF["h"] == 1)]
    if len(p_sub) == 0:
        p_sub = PREDS_DF[(PREDS_DF["origin_date"] == date) & (PREDS_DF["h"] == 1)]
    fc_mld = float(p_sub["pred_mld"].sum()) if len(p_sub) > 0 else 2632.0
    up_col = p_sub["upper_aci"].fillna(p_sub["upper_static"]) if len(p_sub) > 0 else pd.Series([fc_mld])
    up_mld = float(up_col.sum())
    
    r_sub = RISK_DF[RISK_DF["date"] == date].copy()
    if len(r_sub) == 0:
        r_sub = RISK_DF[RISK_DF["date"] == RISK_DF["date"].iloc[0]].copy()
    r_sub = r_sub.merge(WARDS_DF[["ward_id", "ward_name", "zone"]], on="ward_id")
    top3 = r_sub.sort_values("risk", ascending=False).head(3)
    top3_list = [
        {"ward_id": int(r["ward_id"]), "name": str(r["ward_name"]), "risk": round(float(r["risk"]), 4), "zone": str(r["zone"])}
        for _, r in top3.iterrows()
    ]
    
    first_alarm = METRICS.get("drift", {}).get("first_alarm_date", "2024-04-12")
    is_drift = str(date) >= str(first_alarm)
    
    return {
        "date": date,
        "city_forecast_mld": round(fc_mld, 2),
        "city_upper_mld": round(up_mld, 2),
        "base_total_mld": round(float(WARDS_DF["base_mld"].sum()), 2),
        "shortfall_mld": round(max(0.0, up_mld - 1860.0 - 823.2), 2),
        "saving_inr": 1428235.0,
        "saving_pct": 5.7,
        "top3_at_risk": top3_list,
        "drift_status": "drift_alarm" if is_drift else "nominal",
        "first_alarm_date": first_alarm,
        "sentences": [
            f"Citywide demand forecast stands at {fc_mld:.1f} MLD, with 90% conformal safety upper bound of {up_mld:.1f} MLD.",
            f"Highest supply cascade risk is identified at {top3_list[0]['name']} ({top3_list[0]['zone']}) with {top3_list[0]['risk']*100:.1f}% onset probability.",
            f"Prescriptive dispatch routes operational STPs to save ~INR 1.43M daily over commercial private water tankers.",
            f"Distribution check: {'Drift alarm triggered' if is_drift else 'Within nominal historical variation'}."
        ]
    }

@app.get("/api/v1compare")
def get_v1compare():
    return DEMO_CACHE.get("v1compare", {})

@app.get("/api/presets")
def get_presets():
    return SCENARIO_PRESETS

@app.get("/api/wards")
def get_wards():
    return {
        "wards": WARDS_DF.to_dict(orient="records"),
        "edges": EDGES_DF.to_dict(orient="records")
    }

@app.get("/api/dates")
def get_dates():
    dates = sorted(PREDS_DF[PREDS_DF["h"] == 1]["target_date"].unique().tolist())
    return {"dates": dates, "default_date": "2024-06-15"}

@app.get("/api/forecast")
def get_forecast(ward_id: int = Query(0), h: int = Query(1)):
    sub = PREDS_DF[(PREDS_DF["ward_id"] == ward_id) & (PREDS_DF["h"] == h)].sort_values("target_date")
    if len(sub) == 0:
        return {"error": "Ward or horizon not found"}
        
    actual = [round(float(v), 3) for v in sub["actual_mld"].tolist()]
    pred = [round(float(v), 3) for v in sub["pred_mld"].tolist()]
    l_static = [round(float(v), 3) for v in sub["lower_static"].tolist()]
    u_static = [round(float(v), 3) for v in sub["upper_static"].tolist()]
    l_aci = [None if np.isnan(v) else round(float(v), 3) for v in sub["lower_aci"].tolist()]
    u_aci = [None if np.isnan(v) else round(float(v), 3) for v in sub["upper_aci"].tolist()]
    
    act_arr = np.array(actual)
    ls_arr = np.array(l_static)
    us_arr = np.array(u_static)
    cov_static = float(np.mean((act_arr >= ls_arr) & (act_arr <= us_arr)))
    width_static = float(np.mean(us_arr - ls_arr))
    
    cov_aci = None
    width_aci = None
    if h == 1 and sub["lower_aci"].notnull().all():
        la_arr = np.array(sub["lower_aci"])
        ua_arr = np.array(sub["upper_aci"])
        cov_aci = float(np.mean((act_arr >= la_arr) & (act_arr <= ua_arr)))
        width_aci = float(np.mean(ua_arr - la_arr))
        
    w_name = str(WARDS_DF.loc[WARDS_DF["ward_id"] == ward_id, "ward_name"].values[0]) if len(WARDS_DF) > ward_id else f"Ward_{ward_id+1:03d}"
    
    return {
        "ward_id": ward_id,
        "ward_name": w_name,
        "h": h,
        "dates": sub["target_date"].tolist(),
        "actual": actual,
        "pred": pred,
        "lower_static": l_static,
        "upper_static": u_static,
        "lower_aci": l_aci,
        "upper_aci": u_aci,
        "kpis": {
            "coverage_static": round(cov_static * 100, 1),
            "width_static_mld": round(width_static, 2),
            "coverage_aci": round(cov_aci * 100, 1) if cov_aci is not None else None,
            "width_aci_mld": round(width_aci, 2) if width_aci is not None else None
        }
    }

@app.get("/api/map")
def get_map(date: str = Query("2024-06-15"), layer: str = Query("demand")):
    res = {}
    if layer == "demand":
        sub = PREDS_DF[(PREDS_DF["target_date"] == date) & (PREDS_DF["h"] == 1)]
        if len(sub) == 0:
            sub = PREDS_DF[(PREDS_DF["origin_date"] == date) & (PREDS_DF["h"] == 1)]
        if len(sub) == 0:
            date = PREDS_DF["target_date"].iloc[0]
            sub = PREDS_DF[PREDS_DF["target_date"] == date]
        for _, r in sub.iterrows():
            res[int(r["ward_id"])] = round(float(r["pred_mld"]), 3)
    elif layer == "stress":
        for _, r in WARDS_DF.iterrows():
            res[int(r["ward_id"])] = round(float(r["groundwater_stress"]), 3)
    elif layer == "population":
        for _, r in WARDS_DF.iterrows():
            res[int(r["ward_id"])] = int(r["population"])
    elif layer == "shortfall":
        sub = PREDS_DF[(PREDS_DF["target_date"] == date) & (PREDS_DF["h"] == 1)]
        if len(sub) == 0:
            sub = PREDS_DF[(PREDS_DF["origin_date"] == date) & (PREDS_DF["h"] == 1)]
        bm = WARDS_DF["base_mld"].values
        cc = WARDS_DF["cauvery_cover"].values
        gs = WARDS_DF["groundwater_stress"].values
        cauvery = 1860.0 * (bm * cc) / (bm * cc).sum()
        gw = (1372.0 * 0.6) * (bm * (1.2 - gs)) / (bm * (1.2 - gs)).sum()
        p_up = sub["upper_aci"].fillna(sub["upper_static"]).values if len(sub) == len(WARDS_DF) else bm
        shortfall_vals = np.maximum(0.0, p_up - cauvery - gw)
        for i, val in enumerate(shortfall_vals):
            res[i] = round(float(val), 3)
    elif layer == "risk":
        sub = RISK_DF[RISK_DF["date"] == date]
        if len(sub) == 0:
            date = RISK_DF["date"].iloc[0]
            sub = RISK_DF[RISK_DF["date"] == date]
        for _, r in sub.iterrows():
            res[int(r["ward_id"])] = round(float(r["risk"]), 4)
    return {"date": date, "layer": layer, "values": res}

@app.get("/api/risk")
def get_risk(date: str = Query("2024-06-15")):
    sub = RISK_DF[RISK_DF["date"] == date].copy()
    if len(sub) == 0:
        date = RISK_DF["date"].iloc[0]
        sub = RISK_DF[RISK_DF["date"] == date].copy()
    sub = sub.merge(WARDS_DF, on="ward_id")
    top15 = sub.sort_values("risk", ascending=False).head(15)
    return {
        "date": date,
        "top15": [
            {
                "ward_id": int(r["ward_id"]),
                "ward_name": str(r["ward_name"]),
                "risk": round(float(r["risk"]), 4),
                "zone": str(r["zone"]),
                "tanker_dependence": round(float(r["tanker_dependence"]), 3),
                "groundwater_stress": round(float(r["groundwater_stress"]), 3)
            }
            for _, r in top15.iterrows()
        ],
        "all_risks": {int(r["ward_id"]): round(float(r["risk"]), 4) for _, r in sub.iterrows()}
    }

@app.post("/api/optimize")
def post_optimize(req: OptimizeRequest):
    # Check exact preset match on default date
    default_date = "2024-06-15"
    if req.date == default_date and req.use == "upper":
        for p_id, p_info in SCENARIO_PRESETS.items():
            if (
                abs(req.gw_factor - p_info["gw_factor"]) < 1e-3
                and abs((req.tanker_price or 0.108333) - p_info["tanker_price_inr_L"]) < 1e-3
                and abs(req.stp_price - p_info["stp_price_inr_L"]) < 1e-3
            ):
                if p_id in DEMO_CACHE.get("presets", {}):
                    cached_res = DEMO_CACHE["presets"][p_id]
                    # Format flows for API format [lon1, lat1, lon2, lat2, mld]
                    return cached_res
                    
    # LRU In-memory cache
    cache_key = (req.date, round(req.gw_factor, 2), round(req.tanker_price or 0.108333, 4), round(req.stp_price, 3), req.use)
    if cache_key in LIVE_OPT_CACHE:
        return LIVE_OPT_CACHE[cache_key]
        
    res = solve_milp(
        date=req.date,
        gw_factor=req.gw_factor,
        tanker_price=req.tanker_price,
        stp_price=req.stp_price,
        use=req.use
    )
    if len(LIVE_OPT_CACHE) > 64:
        LIVE_OPT_CACHE.pop(next(iter(LIVE_OPT_CACHE)))
    LIVE_OPT_CACHE[cache_key] = res
    return res

@app.get("/api/recourse")
def get_recourse_api(ward_id: int = Query(168), date: str = Query("2024-06-15")):
    cfs = get_recourse(ward_id=ward_id, date=date, k=3)
    ward_info = WARDS_DF[WARDS_DF["ward_id"] == ward_id].iloc[0]
    return {
        "ward_id": ward_id,
        "ward_name": str(ward_info["ward_name"]),
        "date": date,
        "zone": str(ward_info["zone"]),
        "base_mld": round(float(ward_info["base_mld"]), 3),
        "counterfactuals": cfs
    }

@app.get("/api/drift")
def get_drift():
    piv = DRIFT_DF.pivot(index="date", columns="feature", values="distance")
    series = []
    for d, row in piv.iterrows():
        series.append({
            "date": str(d),
            "ratio_dev_all": round(float(row.get("ratio_dev", 0.0)), 5),
            "ratio_dev_periphery": round(float(row.get("ratio_dev_periphery", 0.0)), 5),
            "rain_dev": round(float(row.get("rain_dev", 0.0)), 5)
        })
    return {
        "first_alarm_date": METRICS.get("drift", {}).get("first_alarm_date", "2024-04-12"),
        "thresholds": METRICS.get("drift", {}).get("thresholds", {}),
        "continual_learning": METRICS.get("drift", {}).get("continual_learning", {}),
        "series": series
    }

@app.get("/api/methods")
def get_methods():
    return {
        "provenance_table": PROVENANCE,
        "pipeline_steps": [
            {"step": "00 Inventory & Backup", "desc": "Official civic GIS delimitation inventory, census population matching, and complete v1 baseline freeze."},
            {"step": "01 Civic Topology & Graph", "desc": "225 BBMP wards, 774 undirected physical edges (border + >300mm transmission lines), 39 operational STPs."},
            {"step": "02 Simulator v2", "desc": "1951-2024 IMD daily temperature forcing, monthly precipitation calibration, and spatial AR(1) cascading demand."},
            {"step": "03 Predictive Forecasters", "desc": "HistGradientBoostingRegressor (0.451 MAE) & Spatio-Temporal Graph Convolutional Network (STGCN)."},
            {"step": "04 Conformal Guarantees", "desc": "Split Conformal Prediction & Adaptive Conformal Inference (ACI) guaranteeing calibrated 90% confidence bounds."},
            {"step": "05 Cascading Failure GAT", "desc": "2-layer Graph Attention Network with Focal Loss yielding 0.110 PR-AUC (~28x above random baseline)."},
            {"step": "06 Prescriptive Reuse MILP", "desc": "Optimal dispatch of 39 real STPs across transmission arcs, cutting unmet demand by 86% and saving INR 1.43M daily."},
            {"step": "07 Actionable Recourse", "desc": "Surrogate-driven DiCE counterfactuals with 100% feasibility under conformal safety constraints."},
            {"step": "08 Drift & Continual Learning", "desc": "Wasserstein distance detection flagging thermal demand shift with 2.6s warm-start model updates."}
        ],
        "honest_limitations": [
            "Simulated demand time series: Forecaster accuracy reflects calibration to thermal/precipitation curves rather than unmetered household consumption.",
            "Pipeline transmission model: Secondary lateral pipes below 300mm diameter are represented as boundary adjacencies rather than explicit hydraulic pipe network equations.",
            "Water quality assumptions: STP reuse is strictly dedicated to non-potable secondary applications (commercial, industrial, park irrigation) capped at 35% of total ward demand.",
            "Licensing: Citizen tanker price surveys and civic geospatial delimitation are compiled under open CC-BY/CC-BY-NC non-commercial research licensing."
        ]
    }

# Mount static frontend
static_dir = ROOT / "app" / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)

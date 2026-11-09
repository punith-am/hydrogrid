import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import DATA, RES, FIG, SEED, N_WARDS, ALPHA
from src.common import set_seed, load_wards, update_metrics

def compute_winkler(lower, upper, actual, alpha=ALPHA):
    width = upper - lower
    penalty_low = np.maximum(0.0, lower - actual)
    penalty_high = np.maximum(0.0, actual - upper)
    return width + (2.0 / alpha) * penalty_low + (2.0 / alpha) * penalty_high

def run_p4():
    set_seed(SEED)
    print("=== Phase 4: Conformal Prediction (Split + ACI) ===")
    
    # 1. Determine best forecaster from metrics.json
    metrics_path = RES / "metrics.json"
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    best_forecaster = metrics.get("best_forecaster", "hgb")
    print(f"Loading predictions for best forecaster: {best_forecaster.upper()}")
    
    preds_file = DATA / f"preds_{best_forecaster}.csv"
    preds = pd.read_csv(preds_file)
    wards = load_wards()
    
    # Attach base_mld and zone
    bm_map = dict(zip(wards["ward_id"], wards["base_mld"]))
    zone_map = dict(zip(wards["ward_id"], wards["zone"]))
    preds["base_mld"] = preds["ward_id"].map(bm_map)
    preds["zone"] = preds["ward_id"].map(zone_map)
    
    # Nonconformity score s = |actual - pred| / base_mld
    preds["score"] = np.abs(preds["actual_mld"] - preds["pred_mld"]) / preds["base_mld"]
    
    cal_df = preds[preds["split"] == "cal"].copy()
    test_df = preds[preds["split"] == "test"].copy()
    
    # 2. Split Conformal per horizon h
    q_dict = {}
    test_df["lower_static"] = 0.0
    test_df["upper_static"] = 0.0
    
    for h in [1, 2, 3]:
        cal_h = cal_df[cal_df["h"] == h]["score"].values
        n = len(cal_h)
        # Quantile level ceil((n+1)*(1-ALPHA))/n
        level = min(1.0, np.ceil((n + 1) * (1.0 - ALPHA)) / n)
        q_h = float(np.quantile(cal_h, level))
        q_dict[h] = q_h
        
        idx = test_df["h"] == h
        test_df.loc[idx, "lower_static"] = np.maximum(0.0, test_df.loc[idx, "pred_mld"] - q_h * test_df.loc[idx, "base_mld"])
        test_df.loc[idx, "upper_static"] = test_df.loc[idx, "pred_mld"] + q_h * test_df.loc[idx, "base_mld"]
        
    test_df["covered_static"] = (test_df["actual_mld"] >= test_df["lower_static"]) & (test_df["actual_mld"] <= test_df["upper_static"])
    test_df["width_static"] = test_df["upper_static"] - test_df["lower_static"]
    test_df["winkler_static"] = compute_winkler(test_df["lower_static"].values, test_df["upper_static"].values, test_df["actual_mld"].values)
    
    # 3. Adaptive Conformal Inference (ACI) for h=1
    gamma = 0.01
    num_wards = len(wards)
    cal_h1 = cal_df[cal_df["h"] == 1]
    cal_scores_by_ward = {w: cal_h1[cal_h1["ward_id"] == w]["score"].values for w in range(num_wards)}
    
    test_h1 = test_df[test_df["h"] == 1].copy()
    test_dates = sorted(test_h1["origin_date"].unique())
    
    alpha_w = np.full(num_wards, ALPHA)
    aci_lower_dict = {}
    aci_upper_dict = {}
    daily_static_cov = []
    daily_aci_cov = []
    
    for d in test_dates:
        sub = test_h1[test_h1["origin_date"] == d]
        d_static_errs = []
        d_aci_errs = []
        for _, row in sub.iterrows():
            w = int(row["ward_id"])
            q_level = float(np.clip(1.0 - alpha_w[w], 0.01, 0.99))
            q_val = float(np.quantile(cal_scores_by_ward[w], q_level))
            
            low = max(0.0, float(row["pred_mld"] - q_val * row["base_mld"]))
            high = float(row["pred_mld"] + q_val * row["base_mld"])
            act = float(row["actual_mld"])
            
            aci_lower_dict[(row["origin_date"], w)] = low
            aci_upper_dict[(row["origin_date"], w)] = high
            
            err = 1 if (act < low or act > high) else 0
            d_aci_errs.append(err)
            
            static_err = 0 if (act >= row["lower_static"] and act <= row["upper_static"]) else 1
            d_static_errs.append(static_err)
            
            alpha_w[w] = float(np.clip(alpha_w[w] + gamma * (ALPHA - err), 0.01, 0.99))
            
        daily_static_cov.append(1.0 - np.mean(d_static_errs))
        daily_aci_cov.append(1.0 - np.mean(d_aci_errs))
        
    # Map ACI results into test_df
    test_df["lower_aci"] = np.nan
    test_df["upper_aci"] = np.nan
    
    h1_idx = test_df["h"] == 1
    h1_keys = list(zip(test_df.loc[h1_idx, "origin_date"], test_df.loc[h1_idx, "ward_id"]))
    test_df.loc[h1_idx, "lower_aci"] = [aci_lower_dict[k] for k in h1_keys]
    test_df.loc[h1_idx, "upper_aci"] = [aci_upper_dict[k] for k in h1_keys]
    
    test_df["covered_aci"] = (test_df["actual_mld"] >= test_df["lower_aci"]) & (test_df["actual_mld"] <= test_df["upper_aci"])
    test_df["width_aci"] = test_df["upper_aci"] - test_df["lower_aci"]
    test_df["winkler_aci"] = compute_winkler(test_df["lower_aci"].values, test_df["upper_aci"].values, test_df["actual_mld"].values)
    
    # 4. Metrics computation
    # Overall static
    static_cov_overall = float(test_df["covered_static"].mean())
    static_width_overall = float(test_df["width_static"].mean())
    static_winkler_overall = float(test_df["winkler_static"].mean())
    
    # Horizon breakdown
    by_h = {}
    for h in [1, 2, 3]:
        sub = test_df[test_df["h"] == h]
        by_h[f"h_{h}"] = {
            "q_val": q_dict[h],
            "coverage": float(sub["covered_static"].mean()),
            "mean_width": float(sub["width_static"].mean()),
            "winkler": float(sub["winkler_static"].mean())
        }
        
    # ACI h=1 metrics
    sub_aci = test_df[test_df["h"] == 1]
    aci_cov_overall = float(sub_aci["covered_aci"].mean())
    aci_width_overall = float(sub_aci["width_aci"].mean())
    aci_winkler_overall = float(sub_aci["winkler_aci"].mean())
    
    # Zone breakdown (h=1)
    by_zone = {}
    for z in ["core", "mid", "periphery"]:
        sub_z = sub_aci[sub_aci["zone"] == z]
        by_zone[z] = {
            "static_coverage": float(sub_z["covered_static"].mean()),
            "static_width": float(sub_z["width_static"].mean()),
            "aci_coverage": float(sub_z["covered_aci"].mean()),
            "aci_width": float(sub_z["width_aci"].mean())
        }
        
    # Before vs after 2024-07-01 (drift shift)
    drift_split_date = "2024-07-01"
    pre_drift = sub_aci[sub_aci["origin_date"] < drift_split_date]
    post_drift = sub_aci[sub_aci["origin_date"] >= drift_split_date]
    
    drift_comparison = {
        "pre_drift": {
            "n_days": int(pre_drift["origin_date"].nunique()),
            "static_coverage": float(pre_drift["covered_static"].mean()),
            "aci_coverage": float(pre_drift["covered_aci"].mean())
        },
        "post_drift": {
            "n_days": int(post_drift["origin_date"].nunique()),
            "static_coverage": float(post_drift["covered_static"].mean()),
            "aci_coverage": float(post_drift["covered_aci"].mean())
        }
    }
    
    conformal_metrics = {
        "forecaster_used": best_forecaster,
        "nominal_coverage": 1.0 - ALPHA,
        "static_overall": {
            "coverage": static_cov_overall,
            "mean_width_mld": static_width_overall,
            "winkler_score": static_winkler_overall
        },
        "static_by_horizon": by_h,
        "aci_h1": {
            "gamma": gamma,
            "coverage": aci_cov_overall,
            "mean_width_mld": aci_width_overall,
            "winkler_score": aci_winkler_overall
        },
        "by_zone_h1": by_zone,
        "drift_comparison_h1": drift_comparison
    }
    update_metrics("conformal", conformal_metrics)
    
    # 5. Figures
    # Rolling 30-day coverage figure
    roll_static = pd.Series(daily_static_cov).rolling(30, min_periods=5).mean()
    roll_aci = pd.Series(daily_aci_cov).rolling(30, min_periods=5).mean()
    
    plt.figure(figsize=(10, 4.5))
    plt.plot(pd.to_datetime(test_dates), roll_static, label="Split Conformal (Static)", color="#1f77b4", linewidth=1.5)
    plt.plot(pd.to_datetime(test_dates), roll_aci, label="Adaptive Conformal (ACI, gamma=0.01)", color="#2ca02c", linewidth=2.0)
    plt.axhline(0.90, color="crimson", linestyle="--", label="Target Coverage (90%)", linewidth=1.5)
    plt.axvline(pd.to_datetime("2024-07-01"), color="gray", linestyle=":", label="Drift Shift (2024-07-01)")
    plt.title("SIMULATED 30-Day Rolling Coverage: Static vs Adaptive Conformal Inference (ACI)")
    plt.xlabel("Origin Date")
    plt.ylabel("Empirical Coverage")
    plt.ylim(0.70, 1.0)
    plt.legend(loc="lower left")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "rolling_coverage_conformal.png", dpi=150)
    plt.close()
    
    # One periphery ward band figure
    periph_wards = wards[wards["zone"] == "periphery"]["ward_id"].values
    sample_w = int(periph_wards[0])
    w_sub = sub_aci[sub_aci["ward_id"] == sample_w].sort_values("target_date").iloc[:90]
    
    plt.figure(figsize=(10, 4.5))
    d_dates = pd.to_datetime(w_sub["target_date"])
    plt.fill_between(d_dates, w_sub["lower_aci"], w_sub["upper_aci"], color="#2ca02c", alpha=0.25, label="90% ACI Prediction Interval")
    plt.plot(d_dates, w_sub["pred_mld"], color="#1f77b4", label="Forecast (MLD)", linewidth=1.5)
    plt.plot(d_dates, w_sub["actual_mld"], color="black", linestyle="--", label="Actual Demand (MLD)", alpha=0.8, linewidth=1.2)
    plt.title(f"SIMULATED Demand Forecast & Conformal Band for Periphery Ward {sample_w} (First 90 Days)")
    plt.xlabel("Target Date")
    plt.ylabel("Demand (MLD)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "conformal_band_periphery.png", dpi=150)
    plt.close()
    
    # 6. Save preds_best.csv
    out_cols = [
        "origin_date", "target_date", "ward_id", "h",
        "actual_mld", "pred_mld",
        "lower_static", "upper_static",
        "lower_aci", "upper_aci"
    ]
    out_df = test_df[out_cols].copy()
    out_df.to_csv(DATA / "preds_best.csv", index=False)
    
    # 7. Gate asserts
    assert (DATA / "preds_best.csv").exists(), "preds_best.csv does not exist"
    assert 0.80 <= static_cov_overall <= 0.97, f"Static coverage {static_cov_overall:.4f} outside [0.80, 0.97]"
    assert 0.85 <= aci_cov_overall <= 0.95, f"ACI coverage {aci_cov_overall:.4f} outside [0.85, 0.95]"
    
    print(f"Split Conformal Overall Coverage: {static_cov_overall * 100:.2f}% (Target: 90%)")
    print(f"ACI (h=1) Overall Coverage: {aci_cov_overall * 100:.2f}% (Target: 90%)")
    print(f"Saved: data/preds_best.csv ({len(out_df)} test rows)")
    print("=== Phase 4 Conformal: Gate PASSED ===")

if __name__ == "__main__":
    run_p4()


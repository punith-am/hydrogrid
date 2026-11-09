import json
import time
import joblib
import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import DATA, RES, FIG, MODELS, SEED, N_WARDS
from src.common import set_seed, load_wards, load_edges, load_sim, get_splits, update_metrics, to_py

def run_p8():
    set_seed(SEED)
    print("=== Phase U4: Drift Detection & Continual Learning ===")
    
    sim = load_sim()
    wards = load_wards()
    edges = load_edges()
    splits = get_splits()
    
    # Load daily weather
    weather_path = DATA / "weather_daily.csv"
    weather_df = pd.read_csv(weather_path)
    weather_df["date"] = pd.to_datetime(weather_df["date"])
    
    train_end = pd.to_datetime(splits["train_end"])
    cal_end = pd.to_datetime(splits["cal_end"])
    
    dates = np.sort(sim["date"].unique())
    T = len(dates)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    t_train_end = date_to_idx[train_end]
    t_cal_end = date_to_idx[cal_end]
    num_wards = len(wards)
    
    # 1. Deseasonalise using pre-test baseline (Train + Cal: 2020-2023)
    sim["month"] = sim["date"].dt.month
    baseline = sim[sim["date"] <= cal_end]
    mean_r = baseline.groupby(["month", "zone"])["ratio"].mean().to_dict()
    mean_rain = baseline.groupby("month")["rainfall"].mean().to_dict()
    
    sim["train_mean_r"] = [mean_r[(m, z)] for m, z in zip(sim["month"], sim["zone"])]
    sim["ratio_dev"] = sim["ratio"] - sim["train_mean_r"]
    sim["train_mean_rain"] = sim["month"].map(mean_rain)
    sim["rain_dev"] = sim["rainfall"] - sim["train_mean_rain"]
    
    r_dev_mat = sim.pivot(index="date", columns="ward_id", values="ratio_dev").values # [T, N]
    rain_dev_mat = sim.pivot(index="date", columns="ward_id", values="rain_dev").values # [T, N]
    
    periph_idx = wards[wards["zone"] == "periphery"]["ward_id"].values
    
    ref_all = r_dev_mat[:t_cal_end+1].flatten()
    ref_periph = r_dev_mat[:t_cal_end+1, periph_idx].flatten()
    ref_rain = rain_dev_mat[:t_cal_end+1].flatten()
    
    # 2. Thresholds via 300 random 30d windows inside baseline
    np.random.seed(SEED)
    d_all, d_periph, d_rain = [], [], []
    for _ in range(300):
        t_start = np.random.randint(0, t_cal_end - 29)
        w_all = r_dev_mat[t_start:t_start+30].flatten()
        w_p = r_dev_mat[t_start:t_start+30, periph_idx].flatten()
        w_r = rain_dev_mat[t_start:t_start+30].flatten()
        d_all.append(wasserstein_distance(w_all, ref_all))
        d_periph.append(wasserstein_distance(w_p, ref_periph))
        d_rain.append(wasserstein_distance(w_r, ref_rain))
        
    th_all = float(np.percentile(d_all, 99))
    th_periph = float(np.percentile(d_periph, 99))
    th_rain = float(np.percentile(d_rain, 99))
    
    # 3. Track daily Wasserstein distances across 2024 test year
    eval_range = range(t_cal_end + 1, T)
    drift_records = []
    
    consec_periph = 0
    first_alarm_date = None
    
    dates_eval = []
    dist_all_list = []
    dist_periph_list = []
    dist_rain_list = []
    
    for t in eval_range:
        d_cur = dates[t]
        d_str = str(pd.to_datetime(d_cur).date())
        dates_eval.append(pd.to_datetime(d_cur))
        
        w_all = r_dev_mat[t-29:t+1].flatten()
        w_p = r_dev_mat[t-29:t+1, periph_idx].flatten()
        w_r = rain_dev_mat[t-29:t+1].flatten()
        
        dist_a = float(wasserstein_distance(w_all, ref_all))
        dist_p = float(wasserstein_distance(w_p, ref_periph))
        dist_r = float(wasserstein_distance(w_r, ref_rain))
        
        dist_all_list.append(dist_a)
        dist_periph_list.append(dist_p)
        dist_rain_list.append(dist_r)
        
        alarm_a = (dist_a > th_all)
        alarm_p = (dist_p > th_periph)
        alarm_r = (dist_r > th_rain)
        
        if alarm_p:
            consec_periph += 1
            if consec_periph >= 3 and first_alarm_date is None:
                first_alarm_date = d_str
        else:
            consec_periph = 0
            
        drift_records.append({"date": d_str, "feature": "ratio_dev", "distance": round(dist_a, 5), "threshold": round(th_all, 5), "alarm": int(alarm_a)})
        drift_records.append({"date": d_str, "feature": "ratio_dev_periphery", "distance": round(dist_p, 5), "threshold": round(th_periph, 5), "alarm": int(alarm_p)})
        drift_records.append({"date": d_str, "feature": "rain_dev", "distance": round(dist_r, 5), "threshold": round(th_rain, 5), "alarm": int(alarm_r)})
        
    drift_df = pd.DataFrame(drift_records)
    drift_df.to_csv(DATA / "drift.csv", index=False)
    print(f"First Alarm Date (Periphery Drift): {first_alarm_date}")
    
    # 4. Save figure
    plt.figure(figsize=(10, 5))
    plt.plot(dates_eval, dist_periph_list, label="Periphery Ratio Dev (Distance)", color="#d62728", linewidth=1.8)
    plt.axhline(th_periph, color="#d62728", linestyle="--", alpha=0.7, label=f"Periphery 99% Threshold ({th_periph:.4f})")
    plt.plot(dates_eval, dist_all_list, label="All Wards Ratio Dev (Distance)", color="#1f77b4", linewidth=1.2)
    plt.axhline(th_all, color="#1f77b4", linestyle="--", alpha=0.7, label=f"All Wards Threshold ({th_all:.4f})")
    if first_alarm_date:
        plt.axvline(pd.to_datetime(first_alarm_date), color="black", linestyle=":", linewidth=2, label=f"Alarm Trigger ({first_alarm_date})")
    plt.axvline(pd.to_datetime("2024-07-01"), color="purple", linestyle="--", alpha=0.5, label="Simulated Shift (2024-07-01)")
    plt.title("SIMULATED Trailing 30-Day Wasserstein Distance & Drift Detection")
    plt.xlabel("Date")
    plt.ylabel("Wasserstein Distance to Train Reference")
    plt.legend(loc="upper left")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "drift_detection.png", dpi=150)
    plt.close()
    
    # 5. Continual Learning comparison post alarm date
    ratio_mat = sim.pivot(index="date", columns="ward_id", values="ratio").values
    rain_mat = sim.pivot(index="date", columns="ward_id", values="rainfall").values
    
    adj_list = {i: [] for i in range(num_wards)}
    for _, r in edges.iterrows():
        adj_list[int(r["src"])].append(int(r["dst"]))
    A = np.zeros((num_wards, num_wards))
    for i in range(num_wards):
        for j in adj_list[i]:
            A[i, j] = 1.0
        if len(adj_list[i]) > 0:
            A[i] /= len(adj_list[i])
        else:
            A[i, i] = 1.0
    neigh_mean = ratio_mat @ A.T
    
    roll7 = np.zeros_like(ratio_mat)
    for t in range(6, T):
        roll7[t] = ratio_mat[t-6:t+1].mean(axis=0)
        
    dates_pd = pd.Series(dates)
    dows = dates_pd.dt.day_of_week.values
    months = dates_pd.dt.month.values
    sin_dow = np.sin(2 * np.pi * dows / 7.0)
    cos_dow = np.cos(2 * np.pi * dows / 7.0)
    sin_mon = np.sin(2 * np.pi * months / 12.0)
    cos_mon = np.cos(2 * np.pi * months / 12.0)
    
    bm = wards["base_mld"].values
    td = wards["tanker_dependence"].values
    gs = wards["groundwater_stress"].values
    x_km_arr = wards["x_km"].values
    y_km_arr = wards["y_km"].values
    dist_center_km_arr = wards["dist_center_km"].values
    log_density_arr = np.log1p(wards["density"].values)
    borewell_density_arr = wards["borewell_density"].values
    cauvery_cover_arr = wards["cauvery_cover"].values
    
    w_indexed = weather_df.set_index("date").reindex(dates)
    tmax_all = (w_indexed["tmax"].values / 40.0)
    tmin_all = (w_indexed["tmin"].values / 40.0)
    
    def build_features_for_origins(origin_list, h=1):
        rows = []
        y_list = []
        base_mld_list = []
        for t in origin_list:
            tgt = t + h
            tmax_val = tmax_all[tgt]
            tmin_val = tmin_all[tgt]
            for w in range(num_wards):
                rows.append([
                    ratio_mat[t, w],
                    ratio_mat[t-1, w],
                    ratio_mat[t-2, w],
                    ratio_mat[t-6, w],
                    roll7[t, w],
                    neigh_mean[t, w],
                    rain_mat[tgt, w] / 50.0,
                    sin_dow[tgt],
                    cos_dow[tgt],
                    sin_mon[tgt],
                    cos_mon[tgt],
                    h,
                    bm[w],
                    td[w],
                    gs[w],
                    tmax_val,
                    tmin_val,
                    log_density_arr[w],
                    borewell_density_arr[w],
                    cauvery_cover_arr[w],
                    x_km_arr[w],
                    y_km_arr[w],
                    dist_center_km_arr[w]
                ])
                y_list.append(ratio_mat[tgt, w])
                base_mld_list.append(bm[w])
        return np.array(rows, dtype=np.float32), np.array(y_list, dtype=np.float32), np.array(base_mld_list, dtype=np.float32)
        
    alarm_date_str = first_alarm_date if first_alarm_date else "2024-07-15"
    t_alarm = date_to_idx[pd.to_datetime(alarm_date_str)]
    test_origins_post_d = [t for t in range(t_alarm + 1, T - 1)]
    
    X_test_post, y_test_post, bm_test = build_features_for_origins(test_origins_post_d, h=1)
    actual_mld = y_test_post * bm_test
    
    # Model (a): Frozen HGB
    frozen = joblib.load(MODELS / "hgb.pkl")
    p_frozen = frozen.predict(X_test_post) * bm_test
    mae_frozen = float(mean_absolute_error(actual_mld, p_frozen))
    rmse_frozen = float(np.sqrt(mean_squared_error(actual_mld, p_frozen)))
    
    # Model (b): Full retrain on data up to D
    train_origins_up_to_d = [t for t in range(7, t_alarm + 1)]
    X_retrain, y_retrain, _ = build_features_for_origins(train_origins_up_to_d, h=1)
    t0 = time.time()
    full_model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, random_state=SEED)
    full_model.fit(X_retrain, y_retrain)
    fit_time_full = float(time.time() - t0)
    p_full = full_model.predict(X_test_post) * bm_test
    mae_full = float(mean_absolute_error(actual_mld, p_full))
    rmse_full = float(np.sqrt(mean_squared_error(actual_mld, p_full)))
    
    # Model (c): Incremental update on recent data up to D
    recent_origins = [t for t in range(max(7, t_alarm - 60), t_alarm + 1)]
    X_recent, y_recent, _ = build_features_for_origins(recent_origins, h=1)
    t0 = time.time()
    inc_model = HistGradientBoostingRegressor(warm_start=True, max_iter=100, learning_rate=0.08, random_state=SEED)
    inc_model.fit(X_recent, y_recent)
    fit_time_inc = float(time.time() - t0)
    p_inc = inc_model.predict(X_test_post) * bm_test
    mae_inc = float(mean_absolute_error(actual_mld, p_inc))
    rmse_inc = float(np.sqrt(mean_squared_error(actual_mld, p_inc)))
    
    continual_results = {
        "frozen": {"mae_mld": round(mae_frozen, 4), "rmse_mld": round(rmse_frozen, 4), "fit_seconds": 0.0},
        "full_retrain": {"mae_mld": round(mae_full, 4), "rmse_mld": round(rmse_full, 4), "fit_seconds": round(fit_time_full, 3)},
        "incremental": {"mae_mld": round(mae_inc, 4), "rmse_mld": round(rmse_inc, 4), "fit_seconds": round(fit_time_inc, 3)}
    }
    
    print("Continual Learning Comparison (post-alarm period):")
    print(f"  Frozen HGB:       MAE = {mae_frozen:.4f} MLD (0.0s)")
    print(f"  Full Retrain:     MAE = {mae_full:.4f} MLD ({fit_time_full:.2f}s)")
    print(f"  Incremental:      MAE = {mae_inc:.4f} MLD ({fit_time_inc:.2f}s)")
    
    drift_metrics = {
        "first_alarm_date": first_alarm_date,
        "thresholds": {"ratio_dev_all": th_all, "ratio_dev_periphery": th_periph, "rain_dev": th_rain},
        "continual_learning": continual_results
    }
    update_metrics("drift", drift_metrics)
    
    assert first_alarm_date is not None, "No alarm triggered"
    assert pd.to_datetime(first_alarm_date) >= pd.to_datetime("2024-01-01"), f"Alarm triggered in pre-test period: {first_alarm_date}"
    assert (DATA / "drift.csv").exists(), "drift.csv not found"
    assert (FIG / "drift_detection.png").exists(), "drift_detection.png not found"
    print("=== Phase U4 Drift: Gate PASSED ===")

if __name__ == "__main__":
    run_p8()

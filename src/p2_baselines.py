import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.inspection import permutation_importance
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import DATA, RES, FIG, MODELS, SEED, N_WARDS
from src.common import set_seed, load_sim, load_wards, load_edges, get_splits, update_metrics

def run_p2():
    set_seed(SEED)
    print("=== Phase U3a: Baselines and Tabular Forecaster (HGB) ===")
    
    sim = load_sim()
    wards = load_wards()
    edges = load_edges()
    splits = get_splits()
    
    # Load daily weather
    weather_path = DATA / "weather_daily.csv"
    if not weather_path.exists():
        raise FileNotFoundError(f"Missing {weather_path}. Run p1_graph_sim first.")
    weather_df = pd.read_csv(weather_path)
    weather_df["date"] = pd.to_datetime(weather_df["date"])
    
    train_end = pd.to_datetime(splits["train_end"])
    cal_end = pd.to_datetime(splits["cal_end"])
    
    dates = np.sort(sim["date"].unique())
    T = len(dates)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    
    t_train_end = date_to_idx[train_end]
    t_cal_end = date_to_idx[cal_end]
    
    # Pre-build matrices
    num_wards = len(wards)
    ratio_mat = sim.pivot(index="date", columns="ward_id", values="ratio").values # [T, N]
    rain_mat = sim.pivot(index="date", columns="ward_id", values="rainfall").values # [T, N]
    
    # Neighborhood mean ratio matrix
    adj_list = {i: [] for i in range(num_wards)}
    for _, r in edges.iterrows():
        adj_list[int(r["src"])].append(int(r["dst"]))
    
    # Normalized adjacency
    A = np.zeros((num_wards, num_wards))
    for i in range(num_wards):
        for j in adj_list[i]:
            A[i, j] = 1.0
        if len(adj_list[i]) > 0:
            A[i] /= len(adj_list[i])
        else:
            A[i, i] = 1.0
    
    neigh_mean_ratio = ratio_mat @ A.T # [T, N]
    
    base_mld_arr = wards["base_mld"].values
    td_arr = wards["tanker_dependence"].values
    gs_arr = wards["groundwater_stress"].values
    zone_arr = wards["zone"].values
    x_km_arr = wards["x_km"].values
    y_km_arr = wards["y_km"].values
    dist_center_km_arr = wards["dist_center_km"].values
    log_density_arr = np.log1p(wards["density"].values)
    borewell_density_arr = wards["borewell_density"].values
    cauvery_cover_arr = wards["cauvery_cover"].values
    
    # Reindex weather to match simulation dates
    w_indexed = weather_df.set_index("date").reindex(dates)
    tmax_all = (w_indexed["tmax"].values / 40.0)
    tmin_all = (w_indexed["tmin"].values / 40.0)
    
    # Rolling 7 mean of ratio: mean of t-6..t inclusive
    roll7_mat = np.zeros_like(ratio_mat)
    for t in range(6, T):
        roll7_mat[t] = ratio_mat[t-6:t+1].mean(axis=0)
        
    dates_pd = pd.Series(dates)
    dows = dates_pd.dt.day_of_week.values
    months = dates_pd.dt.month.values
    sin_dow_all = np.sin(2 * np.pi * dows / 7.0)
    cos_dow_all = np.cos(2 * np.pi * dows / 7.0)
    sin_mon_all = np.sin(2 * np.pi * months / 12.0)
    cos_mon_all = np.cos(2 * np.pi * months / 12.0)
    
    # Determine origin dates per split
    train_origins = [t for t in range(7, t_train_end - 2)]
    cal_origins = [t for t in range(t_train_end + 1, t_cal_end - 2)]
    test_origins = [t for t in range(t_cal_end + 1, T - 3)]
    
    print(f"Origin dates count: Train={len(train_origins)}, Cal={len(cal_origins)}, Test={len(test_origins)}")
    
    feature_names = [
        "ratio_t", "ratio_t_1", "ratio_t_2", "ratio_t_6", "roll7_ratio",
        "neigh_mean_ratio", "rain_next", "sin_dow", "cos_dow", "sin_mon", "cos_mon",
        "h", "base_mld", "tanker_dependence", "groundwater_stress",
        "tmax_next", "tmin_next", "log_density", "borewell_density", "cauvery_cover",
        "x_km", "y_km", "dist_center_km"
    ]
    
    # Build dataset efficiently in blocks
    def build_split_data(origins, split_name):
        X_list, y_list, meta_list = [], [], []
        naive_list, s_naive_list = [], []
        
        for t in origins:
            orig_d = dates[t]
            r_t = ratio_mat[t]
            r_t1 = ratio_mat[t-1]
            r_t2 = ratio_mat[t-2]
            r_t6 = ratio_mat[t-6]
            roll7 = roll7_mat[t]
            n_mean = neigh_mean_ratio[t]
            
            for h in [1, 2, 3]:
                t_target = t + h
                target_d = dates[t_target]
                r_target = ratio_mat[t_target]
                act_mld = r_target * base_mld_arr
                
                # Naive: ratio_t
                p_naive = r_t * base_mld_arr
                # Seasonal naive: ratio 7 days before target day
                p_s_naive = ratio_mat[t_target - 7] * base_mld_arr
                
                # Features for this (t, h) across all N wards
                rain_next = rain_mat[t_target] / 50.0
                sin_d = np.full(num_wards, sin_dow_all[t_target])
                cos_d = np.full(num_wards, cos_dow_all[t_target])
                sin_m = np.full(num_wards, sin_mon_all[t_target])
                cos_m = np.full(num_wards, cos_mon_all[t_target])
                h_feat = np.full(num_wards, h)
                tmax_next_f = np.full(num_wards, tmax_all[t_target])
                tmin_next_f = np.full(num_wards, tmin_all[t_target])
                
                block_X = np.column_stack([
                    r_t, r_t1, r_t2, r_t6, roll7,
                    n_mean, rain_next, sin_d, cos_d, sin_m, cos_m,
                    h_feat, base_mld_arr, td_arr, gs_arr,
                    tmax_next_f, tmin_next_f, log_density_arr, borewell_density_arr, cauvery_cover_arr,
                    x_km_arr, y_km_arr, dist_center_km_arr
                ])
                
                X_list.append(block_X)
                y_list.append(r_target)
                
                meta_block = pd.DataFrame({
                    "origin_date": orig_d,
                    "target_date": target_d,
                    "ward_id": np.arange(num_wards),
                    "h": h,
                    "actual_mld": act_mld,
                    "split": split_name,
                    "zone": zone_arr,
                    "base_mld": base_mld_arr
                })
                meta_list.append(meta_block)
                naive_list.append(p_naive)
                s_naive_list.append(p_s_naive)
                
        X = np.vstack(X_list)
        y = np.concatenate(y_list)
        meta = pd.concat(meta_list, ignore_index=True)
        naive_mld = np.concatenate(naive_list)
        s_naive_mld = np.concatenate(s_naive_list)
        return X, y, meta, naive_mld, s_naive_mld

    print("Building feature matrices for Train, Cal, Test...")
    X_train, y_train, meta_train, _, _ = build_split_data(train_origins, "train")
    X_cal, y_cal, meta_cal, naive_cal, s_naive_cal = build_split_data(cal_origins, "cal")
    X_test, y_test, meta_test, naive_test, s_naive_test = build_split_data(test_origins, "test")
    
    print(f"Matrix shapes: X_train={X_train.shape}, X_cal={X_cal.shape}, X_test={X_test.shape}")
    
    # Train HistGradientBoostingRegressor
    print("Training HistGradientBoostingRegressor on Train set...")
    hgb = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, random_state=SEED)
    hgb.fit(X_train, y_train)
    joblib.dump(hgb, MODELS / "hgb.pkl")
    print("Model saved to models/hgb.pkl")
    
    # Predictions
    pred_ratio_cal = hgb.predict(X_cal)
    pred_ratio_test = hgb.predict(X_test)
    
    hgb_cal_mld = pred_ratio_cal * meta_cal["base_mld"].values
    hgb_test_mld = pred_ratio_test * meta_test["base_mld"].values
    
    # Save unified prediction files (cal and test rows only)
    df_naive = pd.concat([
        meta_cal.assign(pred_mld=naive_cal),
        meta_test.assign(pred_mld=naive_test)
    ], ignore_index=True)[["origin_date", "target_date", "ward_id", "h", "actual_mld", "pred_mld", "split"]]
    df_naive.to_csv(DATA / "preds_naive.csv", index=False)
    
    df_s_naive = pd.concat([
        meta_cal.assign(pred_mld=s_naive_cal),
        meta_test.assign(pred_mld=s_naive_test)
    ], ignore_index=True)[["origin_date", "target_date", "ward_id", "h", "actual_mld", "pred_mld", "split"]]
    df_s_naive.to_csv(DATA / "preds_seasonal.csv", index=False)
    
    df_hgb = pd.concat([
        meta_cal.assign(pred_mld=hgb_cal_mld),
        meta_test.assign(pred_mld=hgb_test_mld)
    ], ignore_index=True)[["origin_date", "target_date", "ward_id", "h", "actual_mld", "pred_mld", "split"]]
    df_hgb.to_csv(DATA / "preds_hgb.csv", index=False)
    print("Saved preds_naive.csv, preds_seasonal.csv, preds_hgb.csv")
    
    # Compute Metrics on Test set
    y_test_mld = meta_test["actual_mld"].values
    
    def calc_metrics(act, pred):
        mae = float(mean_absolute_error(act, pred))
        rmse = float(np.sqrt(mean_squared_error(act, pred)))
        return mae, rmse

    naive_mae, naive_rmse = calc_metrics(y_test_mld, naive_test)
    s_naive_mae, s_naive_rmse = calc_metrics(y_test_mld, s_naive_test)
    hgb_mae, hgb_rmse = calc_metrics(y_test_mld, hgb_test_mld)
    
    h_metrics = {}
    for h_val in [1, 2, 3]:
        mask_h = (meta_test["h"] == h_val).values
        n_mae, n_rmse = calc_metrics(y_test_mld[mask_h], naive_test[mask_h])
        sn_mae, sn_rmse = calc_metrics(y_test_mld[mask_h], s_naive_test[mask_h])
        hg_mae, hg_rmse = calc_metrics(y_test_mld[mask_h], hgb_test_mld[mask_h])
        h_metrics[f"h_{h_val}"] = {
            "naive": {"mae": n_mae, "rmse": n_rmse},
            "seasonal_naive": {"mae": sn_mae, "rmse": sn_rmse},
            "hgb": {"mae": hg_mae, "rmse": hg_rmse}
        }
    
    zone_metrics = {}
    for z in ["core", "mid", "periphery"]:
        mask_z = (meta_test["zone"] == z).values
        z_mae, z_rmse = calc_metrics(y_test_mld[mask_z], hgb_test_mld[mask_z])
        zone_metrics[z] = {"mae": z_mae, "rmse": z_rmse}
    
    # Permutation importance (3 repeats, 20k sample)
    print("Computing permutation importance on 20k test sample...")
    sample_idx = np.random.choice(len(X_test), size=min(20000, len(X_test)), replace=False)
    X_sample = X_test[sample_idx]
    y_sample = y_test[sample_idx]
    
    perm = permutation_importance(hgb, X_sample, y_sample, n_repeats=3, random_state=SEED)
    perm_dict = dict(zip(feature_names, perm.importances_mean.tolist()))
    
    metrics_summary = {
        "overall": {
            "naive": {"mae": naive_mae, "rmse": naive_rmse},
            "seasonal_naive": {"mae": s_naive_mae, "rmse": s_naive_rmse},
            "hgb": {"mae": hgb_mae, "rmse": hgb_rmse}
        },
        "by_horizon": h_metrics,
        "by_zone_hgb": zone_metrics,
        "permutation_importance": perm_dict
    }
    update_metrics("baselines", metrics_summary)
    
    # Figures
    plt.figure(figsize=(7, 4))
    models_labels = ["Naive (lag 1)", "Seasonal (lag 7)", "HistGradientBoosting"]
    maes = [naive_mae, s_naive_mae, hgb_mae]
    bars = plt.bar(models_labels, maes, color=["#6c757d", "#495057", "#0d6efd"], edgecolor="black")
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, h + 0.01, f"{h:.3f}", ha="center", va="bottom", fontsize=10)
    plt.title("Test MAE - Baselines vs GBDT (SIMULATED data)")
    plt.ylabel("MAE (MLD)")
    plt.ylim(0, max(maes) * 1.25)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "test_mae_baselines.png", dpi=150)
    plt.close()
    
    sorted_feat_idx = perm.importances_mean.argsort()
    plt.figure(figsize=(8, 6))
    plt.barh(np.array(feature_names)[sorted_feat_idx], perm.importances_mean[sorted_feat_idx], color="teal", edgecolor="black")
    plt.title("Feature Permutation Importance (SIMULATED data)")
    plt.xlabel("Importance")
    plt.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "permutation_importance_hgb.png", dpi=150)
    plt.close()
    
    # Gate check
    hgb_mae_h1 = h_metrics["h_1"]["hgb"]["mae"]
    naive_mae_h1 = h_metrics["h_1"]["naive"]["mae"]
    print(f"\n--- Gate Check ---")
    print(f"HGB Test MAE (h=1): {hgb_mae_h1:.4f} MLD | Naive Test MAE (h=1): {naive_mae_h1:.4f} MLD")
    print(f"Overall Test MAE: Naive = {naive_mae:.4f}, Seasonal = {s_naive_mae:.4f}, HGB = {hgb_mae:.4f} MLD")
    assert hgb_mae_h1 < naive_mae_h1, f"Gate failed: HGB ({hgb_mae_h1}) >= Naive ({naive_mae_h1})"
    print("Gate Passed: HGB outperforms Naive baseline!")

if __name__ == "__main__":
    run_p2()

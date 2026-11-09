import json
import re
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import ROOT, RAW, DATA, RES, FIG, SEED, N_WARDS, TOTAL_MLD, START, END
from src.common import set_seed, update_metrics, to_py

def run_p1():
    set_seed(SEED)
    print("=== Phase U2: Simulator v2 with Real Anchors, Wards, Graph, Weather & Demand ===")
    
    # ---------------- A. Real Parameters ----------------
    print("[1/5] Extracting real-data anchors...")
    # 1. Rainfall Series
    rain_path = ROOT / "new_dataset" / "rainfall" / "Bengaluru Monthly Rainfall Data (1900-2025).csv"
    if not rain_path.exists():
        rain_path = RAW / "Bengaluru Monthly Rainfall Data (1900-2025).csv"
    rain_raw = pd.read_csv(rain_path)
    
    rain_numeric = rain_raw[rain_raw["Year"].astype(str).str.isnumeric()].copy()
    rain_numeric["Year"] = rain_numeric["Year"].astype(int)
    annual_rain = dict(zip(rain_numeric["Year"].astype(str), rain_numeric["Total"].astype(float)))
    
    # 2. Tanker Surveys
    def extract_prices(file_name, col_name):
        path = RAW / file_name
        if not path.exists():
            path = ROOT / "new_dataset" / "tankers" / file_name
        if not path.exists():
            return []
        try:
            df = pd.read_csv(path, on_bad_lines="skip")
            if col_name in df.columns:
                series = df[col_name].dropna().astype(str)
                cleaned = series.str.extract(r"(\d+[\.\d]*)")[0].astype(float)
                cleaned = cleaned[cleaned > 0]
                return cleaned.tolist()
        except Exception as e:
            print(f"Warning reading {file_name}: {e}")
        return []

    p2015 = extract_prices("tanker_2015.csv", "Average tanker price")
    p2019 = extract_prices("tanker_2019.csv", "Average tanker price")
    p2024 = extract_prices("tanker_2024.csv", "How much do you pay for a single tanker of water?")
    
    median_2015 = float(np.median(p2015)) if p2015 else 500.0
    median_2019 = float(np.median(p2019)) if p2019 else 800.0
    median_2024 = float(np.median(p2024)) if p2024 else 1500.0
    tanker_price_per_L_2024 = median_2024 / 12000.0 # INR per Liter
    
    # 3. Borewells count
    wards_path = DATA / "wards.csv"
    if not wards_path.exists():
        raise FileNotFoundError(f"Missing {wards_path}. Run u1_geo first.")
    wards_df = pd.read_csv(wards_path)
    borewell_count = int(wards_df["borewell_count"].sum())
    
    real_params = {
        "annual_rainfall_series": annual_rain,
        "tanker_medians": {
            "2015": {"median": median_2015, "count": len(p2015)},
            "2019": {"median": median_2019, "count": len(p2019)},
            "2024": {"median": median_2024, "count": len(p2024)},
        },
        "tanker_price_per_L_2024": tanker_price_per_L_2024,
        "borewell_count": borewell_count
    }
    with open(RES / "real_params.json", "w", encoding="utf-8") as f:
        json.dump(real_params, f, indent=2)
    print(f"Real anchors saved: Tanker 2024 median = {median_2024:.0f} INR, Borewells = {borewell_count}")
    
    # ---------------- B. Load Real Wards ----------------
    num_wards = len(wards_df)
    print(f"[2/5] Loaded {num_wards} real BBMP wards from {wards_path}")
    ward_ids = wards_df["ward_id"].values
    base_mld = wards_df["base_mld"].values
    groundwater_stress = wards_df["groundwater_stress"].values
    tanker_dependence = wards_df["tanker_dependence"].values
    zone = wards_df["zone"].values
    x_km = wards_df["x_km"].values
    y_km = wards_df["y_km"].values
    lon = wards_df["lon"].values
    lat = wards_df["lat"].values
    
    # ---------------- C. Load Real Graph ----------------
    edges_path = DATA / "edges.csv"
    if not edges_path.exists():
        raise FileNotFoundError(f"Missing {edges_path}. Run u1_geo first.")
    edges_df = pd.read_csv(edges_path)
    print(f"[3/5] Loaded {len(edges_df)} directed edges from {edges_path}")
    
    adj_list = {i: [] for i in range(num_wards)}
    for _, r in edges_df.iterrows():
        adj_list[int(r["src"])].append(int(r["dst"]))
        
    # Verify graph connectivity
    src_nodes = edges_df["src"].values
    dst_nodes = edges_df["dst"].values
    w_ones = np.ones(len(edges_df))
    adj_mat = coo_matrix((w_ones, (src_nodes, dst_nodes)), shape=(num_wards, num_wards))
    n_comp, _ = connected_components(csgraph=adj_mat, directed=False)
    assert n_comp == 1, f"Ward graph is not connected: {n_comp} components"
    
    # ---------------- D. Real Daily Weather & Rainfall ----------------
    print("[4/5] Preparing real daily weather & rainfall (2020-2024)...")
    dates = pd.date_range(START, END, freq="D")
    num_days = len(dates)
    assert num_days == 1827, f"Expected 1827 days in 2020-2024, got {num_days}"
    
    # Load temperature
    temp_path = ROOT / "new_dataset" / "rainfall" / "Bengaluru Daily Temperature Data 1951 to 2024.csv"
    df_temp = pd.read_csv(temp_path)
    df_temp["date"] = pd.to_datetime(df_temp["Date"], format="%d-%m-%Y", errors="coerce")
    df_temp = df_temp.dropna(subset=["date"]).sort_values("date")
    df_temp["tmax"] = pd.to_numeric(df_temp["Temp Max"], errors="coerce")
    df_temp["tmin"] = pd.to_numeric(df_temp["Temp Min"], errors="coerce")
    
    w_df = pd.DataFrame({"date": dates})
    w_df = w_df.merge(df_temp[["date", "tmax", "tmin"]], on="date", how="left")
    
    # Fill missing days (e.g. late 2024) using historical day-of-year average
    hist = df_temp[(df_temp["date"].dt.year >= 2010) & (df_temp["date"].dt.year <= 2023)].copy()
    hist["doy"] = hist["date"].dt.day_of_year
    doy_map_tmax = hist.groupby("doy")["tmax"].mean().to_dict()
    doy_map_tmin = hist.groupby("doy")["tmin"].mean().to_dict()
    
    w_df["doy"] = w_df["date"].dt.day_of_year
    w_df["tmax"] = w_df["tmax"].fillna(w_df["doy"].map(doy_map_tmax)).round(2)
    w_df["tmin"] = w_df["tmin"].fillna(w_df["doy"].map(doy_map_tmin)).round(2)
    tmax = w_df["tmax"].values
    tmin = w_df["tmin"].values
    
    # Rainfall calibrated to real IMD monthly totals
    month_cols = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "June",
        7: "July", 8: "Aug", 9: "Sept", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    
    city_rainfall = np.zeros(num_days)
    monthly_real_map = {}
    for y_val in [2020, 2021, 2022, 2023, 2024]:
        r_row = rain_numeric[rain_numeric["Year"] == y_val]
        for m in range(1, 13):
            c_name = month_cols[m]
            m_total = float(r_row[c_name].values[0]) if len(r_row) > 0 else 0.0
            idx = np.where((dates.year == y_val) & (dates.month == m))[0]
            n_d = len(idx)
            monthly_real_map[(y_val, m)] = (m_total, idx)
            
            if m_total == 0.0:
                city_rainfall[idx] = 0.0
            else:
                p_rain = 0.30 if m in [6, 7, 8, 9, 10] else 0.10
                is_r = np.random.rand(n_d) < p_rain
                if not np.any(is_r):
                    is_r[np.random.randint(0, n_d)] = True
                weights = np.random.dirichlet(np.ones(int(is_r.sum())))
                city_rainfall[idx[is_r]] = weights * m_total
                
    # Verify monthly rainfall sums match real values
    for (y_val, m), (m_total, idx) in monthly_real_map.items():
        daily_sum = city_rainfall[idx].sum()
        assert abs(daily_sum - m_total) < 1e-4, f"Rainfall mismatch in {y_val}-{m}: {daily_sum} vs {m_total}"
        
    # Save weather_daily.csv
    weather_daily = pd.DataFrame({
        "date": dates,
        "tmax": tmax,
        "tmin": tmin,
        "rain_city_mm": np.round(city_rainfall, 2)
    })
    weather_daily.to_csv(DATA / "weather_daily.csv", index=False)
    print(f"weather_daily.csv saved: {len(weather_daily)} days (2020-2024)")
    
    # Ward rainfall = city rainfall x ward factor U(0.8, 1.2)
    ward_rain_factors = np.random.uniform(0.8, 1.2, size=num_wards)
    ward_rainfall = np.outer(city_rainfall, ward_rain_factors)
    
    # ---------------- E. Simulation & Cascading Failures ----------------
    print("[5/5] Simulating daily demand with temperature effect and cascading failures...")
    
    # Spatial AR(1) shock process smoothed over real graph
    raw_s = np.zeros((num_days, num_wards))
    shocks = np.zeros((num_days, num_wards))
    for t in range(num_days):
        if t == 0:
            raw_s[t] = np.random.normal(0, 0.03, size=num_wards)
        else:
            raw_s[t] = 0.85 * raw_s[t-1] + np.random.normal(0, 0.03, size=num_wards)
        nbr_means = np.array([np.mean(raw_s[t, adj_list[i]]) if adj_list[i] else raw_s[t, i] for i in range(num_wards)])
        shocks[t] = 0.4 * raw_s[t] + 0.6 * nbr_means
        
    temp_effect = 1.0 + 0.006 * np.maximum(0.0, tmax - 28.0)
    weekday = np.where(np.isin(dates.day_of_week.values, [5, 6]), 1.05, 1.0)
    dry_month = np.isin(dates.month.values, [2, 3, 4, 5]).astype(float)
    gw_effect = 1.0 + 0.05 * groundwater_stress[None, :] * dry_month[:, None]
    rain_effect = 1.0 - 0.002 * np.minimum(ward_rainfall, 50.0)
    
    # Drift: 1.08 for periphery wards from 2024-07-01 onward (SIMULATED shift)
    drift_mask = (dates >= "2024-07-01")[:, None] & (zone == "periphery")[None, :]
    drift_factor = np.where(drift_mask, 1.08, 1.0)
    
    noise = np.random.normal(0, 0.03 * base_mld[None, :], size=(num_days, num_wards))
    
    base_demand = (
        base_mld[None, :]
        * temp_effect[:, None]
        * weekday[:, None]
        * rain_effect
        * gw_effect
        * drift_factor
        * (1.0 + shocks)
        + noise
    )
    demand = np.maximum(0.0, base_demand)
    
    # Cascading supply failures
    n_primary = 450
    supply_failure = np.zeros((num_days, num_wards), dtype=int)
    demand_multiplier = np.ones((num_days, num_wards))
    
    city_rain_s = pd.Series(city_rainfall)
    trail_30_rain = city_rain_s.rolling(30, min_periods=1).mean().values
    median_trail_rain = np.median(trail_30_rain)
    rain_boost = np.where(trail_30_rain < median_trail_rain, 1.3, 1.0)
    
    date_probs = (1.0 + 1.5 * dry_month) * rain_boost
    date_probs = date_probs[:num_days - 12] / date_probs[:num_days - 12].sum()
    ward_probs = tanker_dependence / tanker_dependence.sum()
    
    events_queue = []
    for _ in range(n_primary):
        w = np.random.choice(num_wards, p=ward_probs)
        t_s = np.random.choice(num_days - 12, p=date_probs)
        dur = np.random.randint(3, 11)
        events_queue.append((w, t_s, dur, "primary"))
        
    while events_queue:
        w, t_s, dur, level = events_queue.pop(0)
        for dt in range(dur):
            t_curr = t_s + dt
            if t_curr < num_days:
                supply_failure[t_curr, w] = 1
                demand_multiplier[t_curr, w] = max(demand_multiplier[t_curr, w], 1.3)
                if dt < 5:
                    spill = 1.10 - 0.02 * dt
                    for nbr in adj_list[w]:
                        demand_multiplier[t_curr, nbr] = max(demand_multiplier[t_curr, nbr], spill)
        if level in ["primary", "secondary"]:
            p_cascade = 0.3 * (0.5 + tanker_dependence[w])
            if level == "secondary":
                p_cascade *= 0.5
            for nbr in adj_list[w]:
                if np.random.rand() < p_cascade:
                    sec_t = t_s + 2
                    sec_dur = np.random.randint(2, 7)
                    next_level = "secondary" if level == "primary" else "tertiary"
                    if sec_t < num_days - 8:
                        events_queue.append((nbr, sec_t, sec_dur, next_level))
                        
    demand = demand * demand_multiplier
    
    # Rescale ALL demand by ONE constant so mean daily city total = 2632.0 MLD
    raw_mean_city = demand.sum(axis=1).mean()
    scale_const = TOTAL_MLD / raw_mean_city
    demand = demand * scale_const
    
    # ---------------- F. Output Dataframe & Splits ----------------
    dates_rep = np.repeat(dates, num_wards)
    wards_rep = np.tile(ward_ids, num_days)
    
    sim_df = pd.DataFrame({
        "date": dates_rep,
        "ward_id": wards_rep,
        "rainfall": np.round(ward_rainfall.flatten(), 4),
        "demand_mld": np.round(demand.flatten(), 4),
        "supply_failure": supply_failure.flatten()
    })
    sim_df = sim_df.sort_values(by=["ward_id", "date"]).reset_index(drop=True)
    sim_df.to_csv(DATA / "simulated_demand.csv", index=False)
    print(f"simulated_demand.csv saved: shape {sim_df.shape}")
    
    # Split dates: Train (to 2022-12-31), Cal (2023), Test (2024)
    split_info = {
        "train_end": "2022-12-31",
        "cal_end": "2023-12-31"
    }
    with open(DATA / "split_dates.json", "w", encoding="utf-8") as f:
        json.dump(split_info, f, indent=2)
    print(f"split_dates.json saved: {split_info}")
    
    # ---------------- G. Figures with SIMULATED Titles ----------------
    city_tot_demand = sim_df.groupby("date")["demand_mld"].sum()
    
    # 1. Timeline
    plt.figure(figsize=(10, 4))
    plt.plot(city_tot_demand.index, city_tot_demand.values, color="royalblue", lw=1)
    plt.title("SIMULATED Total City Water Demand (2020-2024)")
    plt.ylabel("Demand (MLD)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "simulated_city_demand_timeline.png", dpi=150)
    plt.close()
    
    # 2. Core vs Periphery
    c_w = wards_df[wards_df["zone"] == "core"].iloc[0]["ward_id"]
    p_w = wards_df[wards_df["zone"] == "periphery"].iloc[0]["ward_id"]
    sim_2023 = sim_df[sim_df["date"].dt.year == 2023]
    
    plt.figure(figsize=(10, 4))
    plt.plot(sim_2023[sim_2023["ward_id"] == c_w]["date"], sim_2023[sim_2023["ward_id"] == c_w]["demand_mld"], label=f"Core Ward {c_w}", color="navy")
    plt.plot(sim_2023[sim_2023["ward_id"] == p_w]["date"], sim_2023[sim_2023["ward_id"] == p_w]["demand_mld"], label=f"Periphery Ward {p_w}", color="orange")
    plt.title("SIMULATED Daily Demand: Core vs Periphery Ward (2023)")
    plt.ylabel("Demand (MLD)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "simulated_core_vs_periphery_2023.png", dpi=150)
    plt.close()
    
    # 3. Rainfall 2023
    rain_s = pd.Series(city_rainfall, index=dates)
    rain_2023 = rain_s[rain_s.index.year == 2023]
    plt.figure(figsize=(10, 4))
    plt.bar(rain_2023.index, rain_2023.values, color="dodgerblue", width=1.0)
    plt.title("SIMULATED City Daily Rainfall (2023) Calibrated to Real IMD")
    plt.ylabel("Rainfall (mm)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "simulated_city_rainfall_2023.png", dpi=150)
    plt.close()
    
    # 4. Ward Graph Scatter
    plt.figure(figsize=(8, 8))
    for _, r in edges_df[edges_df["src"] < edges_df["dst"]].iterrows():
        u, v = int(r["src"]), int(r["dst"])
        plt.plot([lon[u], lon[v]], [lat[u], lat[v]], color="grey", alpha=0.35, lw=0.8)
    z_colors = {"core": "royalblue", "mid": "orange", "periphery": "forestgreen"}
    for z in ["core", "mid", "periphery"]:
        sub = wards_df[wards_df["zone"] == z]
        plt.scatter(sub["lon"], sub["lat"], c=z_colors[z], label=f"{z.capitalize()} ({len(sub)})", s=35, edgecolors="black", lw=0.5, zorder=3)
    plt.title("REAL Administrative Ward Network Topology (N=225)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "simulated_ward_graph.png", dpi=150)
    plt.close()
    
    # ---------------- GATE CHECKS ----------------
    print("\n--- Running Phase U2 Gate Checks ---")
    expected_rows = num_wards * num_days
    assert sim_df.shape == (expected_rows, 5), f"sim shape mismatch: expected ({expected_rows}, 5), got {sim_df.shape}"
    assert sim_df.isnull().sum().sum() == 0, "sim has nulls"
    assert (sim_df["demand_mld"] >= 0).all(), "Negative demand found"
    
    mean_city_demand = city_tot_demand.mean()
    print(f"Mean city daily demand: {mean_city_demand:.2f} MLD")
    assert 2600.0 <= mean_city_demand <= 2660.0, f"Mean daily demand outside [2600, 2660]: {mean_city_demand}"
    
    # Correlation with tmax > 0.3
    corr_tmax = np.corrcoef(city_tot_demand.values, tmax)[0, 1]
    print(f"Correlation of city demand with tmax: {corr_tmax:.4f}")
    assert corr_tmax > 0.3, f"Correlation with tmax too low: {corr_tmax}"
    
    # Ratio correlation check: neighbour vs non-neighbour
    sim_df["ratio"] = sim_df["demand_mld"] / np.repeat(base_mld, num_days)
    ratio_table = sim_df.pivot(index="date", columns="ward_id", values="ratio").values
    corr_matrix = np.corrcoef(ratio_table.T)
    nbr_corrs = []
    non_nbr_corrs = []
    for i in range(num_wards):
        nbrs = adj_list[i]
        for n in nbrs:
            nbr_corrs.append(corr_matrix[i, n])
        non_nbrs = [j for j in range(num_wards) if j != i and j not in nbrs]
        chosen = np.random.choice(non_nbrs, size=min(30, len(non_nbrs)), replace=False)
        for c in chosen:
            non_nbr_corrs.append(corr_matrix[i, c])
            
    mean_nbr_corr = np.mean(nbr_corrs)
    mean_non_nbr_corr = np.mean(non_nbr_corrs)
    corr_diff = mean_nbr_corr - mean_non_nbr_corr
    print(f"Neighbour ratio correlation: {mean_nbr_corr:.4f}, Non-neighbour: {mean_non_nbr_corr:.4f}, Diff: {corr_diff:.4f}")
    assert corr_diff >= 0.10, f"Spatial correlation difference too small: {corr_diff}"
    
    # Failure counts & onsets
    fail_mat = sim_df.pivot(index="date", columns="ward_id", values="supply_failure").values
    onsets_all = int(((fail_mat[:-1] == 0) & (fail_mat[1:] == 1)).sum())
    
    idx_2024 = np.where(dates.year == 2024)[0]
    fail_2024 = fail_mat[idx_2024]
    onsets_2024 = int(((fail_2024[:-1] == 0) & (fail_2024[1:] == 1)).sum())
    
    print(f"Failure onsets overall: {onsets_all} (Gate: >= 300)")
    print(f"Failure onsets in 2024: {onsets_2024} (Gate: >= 60)")
    assert onsets_all >= 300, f"Overall onsets too low: {onsets_all}"
    assert onsets_2024 >= 60, f"2024 onsets too low: {onsets_2024}"
    
    # Record metrics
    update_metrics("phase_2_simulator_v2", {
        "num_wards": num_wards,
        "num_days": num_days,
        "mean_daily_demand_mld": float(mean_city_demand),
        "corr_demand_tmax": float(corr_tmax),
        "mean_neighbour_corr": float(mean_nbr_corr),
        "mean_non_neighbour_corr": float(mean_non_nbr_corr),
        "corr_diff": float(corr_diff),
        "failure_onsets_all": onsets_all,
        "failure_onsets_2024": onsets_2024
    })
    
    print("=== Phase U2 Gate: ALL PASSED ===")

if __name__ == "__main__":
    run_p1()

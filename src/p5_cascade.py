import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import precision_recall_curve, auc, roc_auc_score, precision_score, recall_score, f1_score
from sklearn.ensemble import HistGradientBoostingClassifier
from imblearn.over_sampling import SMOTE
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import DATA, RES, FIG, MODELS, SEED, N_WARDS
from src.common import set_seed, load_sim, load_wards, load_edges, get_splits, update_metrics

class GAT(nn.Module):
    def __init__(self, in_channels=15):
        super().__init__()
        from torch_geometric.nn import GATConv
        self.conv1 = GATConv(in_channels, 32, heads=4)
        self.conv2 = GATConv(128, 32, heads=2)
        self.out = nn.Linear(64, 1)

    def forward(self, x, edge_index):
        h = F.elu(self.conv1(x, edge_index))
        h = F.elu(self.conv2(h, edge_index))
        return self.out(h).squeeze(-1)

def focal_loss(logits, targets, mask, gamma=2.0, alpha=0.75):
    p = torch.sigmoid(logits)
    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    p_t = targets * p + (1.0 - targets) * (1.0 - p)
    alpha_t = targets * alpha + (1.0 - targets) * (1.0 - alpha)
    loss = alpha_t * ((1.0 - p_t) ** gamma) * bce
    m = mask.float()
    return (loss * m).sum() / (m.sum() + 1e-8)

def compute_pr_auc(y_true, y_prob):
    p, r, _ = precision_recall_curve(y_true, y_prob)
    return float(auc(r, p))

def find_best_threshold(y_true, y_prob):
    best_f1 = -1.0
    best_th = 0.5
    for th in np.linspace(0.01, 0.99, 99):
        pred = (y_prob >= th).astype(int)
        f = f1_score(y_true, pred, zero_division=0)
        if f > best_f1:
            best_f1 = f
            best_th = th
    return float(best_th), float(best_f1)

def run_p5():
    set_seed(SEED)
    print("=== Phase U3b: Cascading-Failure Early Warning (GAT) ===")
    
    sim = load_sim()
    wards = load_wards()
    edges = load_edges()
    splits = get_splits()
    
    # Load daily weather
    weather_path = DATA / "weather_daily.csv"
    if weather_path.exists():
        weather_df = pd.read_csv(weather_path)
        weather_df["date"] = pd.to_datetime(weather_df["date"])
    else:
        weather_df = None
        
    dates = np.sort(sim["date"].unique())
    T = len(dates)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    num_wards = len(wards)
    
    # Adjacency
    adj_list = {i: [] for i in range(num_wards)}
    for _, r in edges.iterrows():
        adj_list[int(r["src"])].append(int(r["dst"]))
        
    A = np.zeros((num_wards, num_wards))
    for i in range(num_wards):
        for j in adj_list[i]:
            A[i, j] = 1.0
            
    # Base matrices
    fail_mat = sim.pivot(index="date", columns="ward_id", values="supply_failure").values.astype(float)
    ratio_mat = sim.pivot(index="date", columns="ward_id", values="ratio").values
    rain_mat = sim.pivot(index="date", columns="ward_id", values="rainfall").values
    
    # Feature engineering
    # 1. fail_today
    f_today = fail_mat
    # 2. n_fail_neighbours_today
    f_neigh = fail_mat @ A.T
    # 3. fail_count_last3
    f_last3 = pd.DataFrame(fail_mat).rolling(3, min_periods=1).sum().values
    # 4. ratio_t
    r_t = ratio_mat
    # 5. ratio_t - mean(previous 30d)
    r_mean30 = pd.DataFrame(ratio_mat).shift(1).rolling(30, min_periods=1).mean().values
    r_diff30 = r_t - r_mean30
    # 6. rain_7d / 100
    rain_7d = pd.DataFrame(rain_mat).rolling(7, min_periods=1).sum().values / 100.0
    # 7. rain_30d / 300
    rain_30d = pd.DataFrame(rain_mat).rolling(30, min_periods=1).sum().values / 300.0
    # 8, 9. sin/cos month
    months = pd.Series(dates).dt.month.values
    sin_mon = np.tile(np.sin(2 * np.pi * months / 12.0)[:, None], (1, num_wards))
    cos_mon = np.tile(np.cos(2 * np.pi * months / 12.0)[:, None], (1, num_wards))
    # 10. tanker_dependence
    td = np.tile(wards["tanker_dependence"].values[None, :], (T, 1))
    # 11. groundwater_stress
    gs = np.tile(wards["groundwater_stress"].values[None, :], (T, 1))
    # 12. base_mld / max(base_mld)
    bm_norm = np.tile((wards["base_mld"].values / wards["base_mld"].max())[None, :], (T, 1))
    
    # 13. tmax / 40.0
    if weather_df is not None:
        tmax_vals = weather_df.set_index("date").reindex(dates)["tmax"].values / 40.0
        tmax_feat = np.tile(tmax_vals[:, None], (1, num_wards))
    else:
        tmax_feat = np.full((T, num_wards), 0.75)
        
    # 14. cauvery_cover
    cauvery_feat = np.tile(wards["cauvery_cover"].values[None, :], (T, 1))
    
    # 15. borewell_density (normalized)
    max_bw = max(wards["borewell_density"].max(), 1.0)
    bw_feat = np.tile((wards["borewell_density"].values / max_bw)[None, :], (T, 1))
    
    # Stack [T, N, 15]
    feats = np.stack([
        f_today, f_neigh, f_last3, r_t, r_diff30,
        rain_7d, rain_30d, sin_mon, cos_mon, td, gs, bm_norm,
        tmax_feat, cauvery_feat, bw_feat
    ], axis=-1).astype(np.float32)
    
    # Target and mask
    y_mat = np.zeros((T, num_wards), dtype=np.float32)
    mask_mat = np.zeros((T, num_wards), dtype=bool)
    for t in range(T - 1):
        mask_mat[t] = (fail_mat[t] == 0)
        y_mat[t] = ((fail_mat[t] == 0) & (fail_mat[t + 1] == 1)).astype(np.float32)
        
    # Edge index
    ei_single = torch.from_numpy(np.stack([edges["src"].values, edges["dst"].values]).copy()).long()
    
    # Split ranges
    t_train_end = date_to_idx[pd.to_datetime(splits["train_end"])]
    t_cal_end = date_to_idx[pd.to_datetime(splits["cal_end"])]
    
    train_days = [t for t in range(30, t_train_end)]
    cal_days = [t for t in range(t_train_end + 1, t_cal_end)]
    test_days = [t for t in range(t_cal_end + 1, T - 1)]
    
    n_val_days = max(1, int(0.10 * len(train_days)))
    train_sub_days = train_days[:-n_val_days]
    val_days = train_days[-n_val_days:]
    
    pos_train_days = [t for t in train_sub_days if y_mat[t].sum() > 0]
    neg_train_days = [t for t in train_sub_days if y_mat[t].sum() == 0]
    
    model = GAT(in_channels=15)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    
    def batch_forward(day_indices, is_train=True):
        B = len(day_indices)
        x_list = [feats[t] for t in day_indices] # [B, N, 15]
        x_cat = torch.from_numpy(np.concatenate(x_list, axis=0)).float() # [B*N, 15]
        
        ei_batch = torch.cat([ei_single + b * num_wards for b in range(B)], dim=1)
        logits = model(x_cat, ei_batch)
        
        y_list = [y_mat[t] for t in day_indices]
        m_list = [mask_mat[t] for t in day_indices]
        y_cat = torch.from_numpy(np.concatenate(y_list, axis=0)).float()
        m_cat = torch.from_numpy(np.concatenate(m_list, axis=0)).bool()
        
        return logits, y_cat, m_cat

    best_val_prauc = -1.0
    best_state = None
    patience = 10
    patience_cnt = 0
    batch_size = 16
    
    print(f"Training GAT (in_channels=15) for up to 60 epochs...")
    for epoch in range(1, 61):
        model.train()
        epoch_days = neg_train_days + pos_train_days * 5
        np.random.shuffle(epoch_days)
        
        for i in range(0, len(epoch_days), batch_size):
            b_days = epoch_days[i : i + batch_size]
            optimizer.zero_grad()
            logits, y_cat, m_cat = batch_forward(b_days, is_train=True)
            loss = focal_loss(logits, y_cat, m_cat)
            loss.backward()
            optimizer.step()
            
        model.eval()
        with torch.no_grad():
            v_logits, v_y, v_m = batch_forward(val_days, is_train=False)
            v_prob = torch.sigmoid(v_logits).numpy()
            v_y_np = v_y.numpy()
            v_m_np = v_m.numpy()
            
            v_prauc = compute_pr_auc(v_y_np[v_m_np], v_prob[v_m_np])
            
        if epoch % 10 == 0 or epoch == 1:
            print(f"Epoch {epoch:02d}/60 | Val PR-AUC: {v_prauc:.4f}")
            
        if v_prauc > best_val_prauc:
            best_val_prauc = v_prauc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_cnt = 0
        else:
            patience_cnt += 1
            if patience_cnt >= patience:
                print(f"Early stopping at epoch {epoch}")
                break
                
    model.load_state_dict(best_state)
    torch.save(best_state, MODELS / "gat.pt")
    print(f"Best GAT model saved to {MODELS / 'gat.pt'} (best val PR-AUC: {best_val_prauc:.4f})")
    
    # 2. Calibration & Threshold tuning
    model.eval()
    with torch.no_grad():
        cal_logits, cal_y, cal_m = batch_forward(cal_days, is_train=False)
        cal_prob = torch.sigmoid(cal_logits).numpy()
        cal_y_np = cal_y.numpy()
        cal_m_np = cal_m.numpy()
        
    cal_mask = cal_m_np
    gat_th, gat_cal_f1 = find_best_threshold(cal_y_np[cal_mask], cal_prob[cal_mask])
    
    # 3. Tabular comparison: HistGradientBoostingClassifier + SMOTE
    print("Training benchmark SMOTE + HGB classifier...")
    train_x_rows, train_y_rows = [], []
    for t in train_days:
        m = mask_mat[t]
        train_x_rows.append(feats[t][m])
        train_y_rows.append(y_mat[t][m])
    X_train_flat = np.concatenate(train_x_rows, axis=0)
    y_train_flat = np.concatenate(train_y_rows, axis=0)
    
    smote = SMOTE(random_state=SEED)
    X_res, y_res = smote.fit_resample(X_train_flat, y_train_flat)
    
    hgb = HistGradientBoostingClassifier(random_state=SEED, max_iter=200)
    hgb.fit(X_res, y_res)
    
    cal_x_rows, cal_y_rows = [], []
    for t in cal_days:
        m = mask_mat[t]
        cal_x_rows.append(feats[t][m])
        cal_y_rows.append(y_mat[t][m])
    X_cal_flat = np.concatenate(cal_x_rows, axis=0)
    y_cal_flat = np.concatenate(cal_y_rows, axis=0)
    hgb_cal_prob = hgb.predict_proba(X_cal_flat)[:, 1]
    hgb_th, hgb_cal_f1 = find_best_threshold(y_cal_flat, hgb_cal_prob)
    
    # 4. Evaluation on test_days
    with torch.no_grad():
        test_logits, test_y, test_m = batch_forward(test_days, is_train=False)
        test_prob_all = torch.sigmoid(test_logits).numpy()
        test_y_all = test_y.numpy()
        test_m_all = test_m.numpy()
        
    test_mask = test_m_all
    y_test = test_y_all[test_mask]
    gat_test_prob = test_prob_all[test_mask]
    gat_test_pred = (gat_test_prob >= gat_th).astype(int)
    
    test_x_rows = []
    for t in test_days:
        m = mask_mat[t]
        test_x_rows.append(feats[t][m])
    X_test_flat = np.concatenate(test_x_rows, axis=0)
    hgb_test_prob = hgb.predict_proba(X_test_flat)[:, 1]
    hgb_test_pred = (hgb_test_prob >= hgb_th).astype(int)
    
    trivial_scores = X_test_flat[:, 1]
    trivial_pred = (trivial_scores > 0).astype(int)
    
    prevalence = float(np.mean(y_test))
    
    def get_metrics_dict(y_t, prob, pred, th=None):
        return {
            "threshold": float(th) if th is not None else 0.5,
            "pr_auc": float(compute_pr_auc(y_t, prob)),
            "roc_auc": float(roc_auc_score(y_t, prob)),
            "precision": float(precision_score(y_t, pred, zero_division=0)),
            "recall": float(recall_score(y_t, pred, zero_division=0)),
            "f1": float(f1_score(y_t, pred, zero_division=0))
        }
        
    gat_metrics = get_metrics_dict(y_test, gat_test_prob, gat_test_pred, gat_th)
    hgb_metrics = get_metrics_dict(y_test, hgb_test_prob, hgb_test_pred, hgb_th)
    trivial_metrics = {
        "threshold": "> 0 failing neighbours",
        "pr_auc": float(compute_pr_auc(y_test, trivial_scores)),
        "roc_auc": float(roc_auc_score(y_test, trivial_scores)),
        "precision": float(precision_score(y_test, trivial_pred, zero_division=0)),
        "recall": float(recall_score(y_test, trivial_pred, zero_division=0)),
        "f1": float(f1_score(y_test, trivial_pred, zero_division=0))
    }
    
    cascade_results = {
        "prevalence": prevalence,
        "gat": gat_metrics,
        "hgb_smote": hgb_metrics,
        "trivial": trivial_metrics
    }
    update_metrics("cascade", cascade_results)
    
    # 5. Save PR-curve figure
    plt.figure(figsize=(8, 5))
    p_gat, r_gat, _ = precision_recall_curve(y_test, gat_test_prob)
    p_hgb, r_hgb, _ = precision_recall_curve(y_test, hgb_test_prob)
    p_triv, r_triv, _ = precision_recall_curve(y_test, trivial_scores)
    
    plt.plot(r_gat, p_gat, label=f"GAT (AUC = {gat_metrics['pr_auc']:.3f})", color="#1f77b4", linewidth=2.0)
    plt.plot(r_hgb, p_hgb, label=f"SMOTE + HGB (AUC = {hgb_metrics['pr_auc']:.3f})", color="#ff7f0e", linewidth=1.8)
    plt.plot(r_triv, p_triv, label=f"Trivial Baseline (AUC = {trivial_metrics['pr_auc']:.3f})", color="#7f7f7f", linestyle="--")
    plt.axhline(prevalence, color="crimson", linestyle=":", label=f"Random Prevalence ({prevalence*100:.2f}%)")
    plt.title("SIMULATED Cascading-Failure Precision-Recall Curve")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "pr_curve_cascade.png", dpi=150)
    plt.close()
    
    # 6. Save cascade_risk.csv for test days
    risk_mat = test_prob_all.reshape(len(test_days), num_wards)
    risk_records = []
    for idx, t in enumerate(test_days):
        d_str = str(pd.to_datetime(dates[t]).date())
        for w in range(num_wards):
            risk_records.append({
                "date": d_str,
                "ward_id": w,
                "risk": round(float(risk_mat[idx, w]), 4)
            })
    risk_df = pd.DataFrame(risk_records)
    risk_df.to_csv(DATA / "cascade_risk.csv", index=False)
    print(f"Saved cascade_risk.csv: {len(risk_df)} rows")
    
    # 7. Gate asserts
    assert (MODELS / "gat.pt").exists(), "gat.pt not found"
    assert (DATA / "cascade_risk.csv").exists(), "cascade_risk.csv not found"
    assert len(risk_df) == len(test_days) * num_wards, "Unexpected risk_df row count"
    assert gat_metrics["pr_auc"] > prevalence, f"GAT PR-AUC {gat_metrics['pr_auc']:.4f} <= prevalence {prevalence:.4f}"
    
    print(f"\n--- Gate Comparison ---")
    print(f"Test Prevalence: {prevalence*100:.2f}%")
    print(f"GAT PR-AUC: {gat_metrics['pr_auc']:.4f} vs Prevalence: {prevalence:.4f} (ROC-AUC: {gat_metrics['roc_auc']:.4f}, F1: {gat_metrics['f1']:.4f})")
    print(f"HGB+SMOTE PR-AUC: {hgb_metrics['pr_auc']:.4f}, Trivial PR-AUC: {trivial_metrics['pr_auc']:.4f}")
    print("=== Phase U3b Gate: ALL PASSED ===")

if __name__ == "__main__":
    run_p5()

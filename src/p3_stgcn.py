import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import DATA, RES, FIG, MODELS, SEED, N_WARDS
from src.common import set_seed, load_sim, load_wards, load_edges, get_splits, update_metrics, build_tensors

class SpatioTemporalDataset(Dataset):
    def __init__(self, X, Y, C, origin_indices):
        self.X = torch.from_numpy(X.astype(np.float32))
        self.Y = torch.from_numpy(Y.astype(np.float32))
        self.C = torch.from_numpy(C.astype(np.float32))
        self.origins = origin_indices

    def __len__(self):
        return len(self.origins)

    def __getitem__(self, idx):
        t = self.origins[idx]
        x = self.X[t - 13 : t + 1] # [14, N, 7]
        c_fut = self.C[t + 1 : t + 4] # [3, N, 6]
        y_fut = self.Y[t + 1 : t + 4] # [3, N]
        return x, c_fut, y_fut, t

class STGCN(nn.Module):
    def __init__(self, in_features=7, hidden_gcn=32, hidden_gru=64, emb_dim=8, cov_dim=6, num_wards=N_WARDS):
        super().__init__()
        from torch_geometric.nn import ChebConv
        self.conv = ChebConv(in_features, hidden_gcn, K=3)
        self.gru = nn.GRU(hidden_gcn, hidden_gru, batch_first=True)
        self.attn = nn.Linear(hidden_gru, 1)
        self.ward_emb = nn.Embedding(num_wards, emb_dim)
        in_dim = hidden_gru + emb_dim + cov_dim
        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(in_dim, 32),
                nn.ReLU(),
                nn.Linear(32, 1)
            ) for _ in range(3)
        ])

    def forward(self, x, c_fut, edge_index, edge_weight):
        B, W, N, F_ = x.shape
        x_flat = x.view(B * W, N, F_)
        h = F.relu(self.conv(x_flat, edge_index, edge_weight=edge_weight))
        h = h.view(B, W, N, -1).permute(0, 2, 1, 3).contiguous().view(B * N, W, -1)
        gru_out, _ = self.gru(h)
        attn_w = F.softmax(self.attn(gru_out), dim=1)
        ctx = (attn_w * gru_out).sum(dim=1).view(B, N, -1)
        
        w_idx = torch.arange(N, device=x.device)
        w_emb = self.ward_emb(w_idx).unsqueeze(0).expand(B, N, -1)
        
        preds = []
        for h_idx in range(3):
            c_h = c_fut[:, h_idx, :, :]
            feat = torch.cat([ctx, w_emb, c_h], dim=-1)
            p = self.heads[h_idx](feat).squeeze(-1)
            preds.append(p)
        return torch.stack(preds, dim=1)

def run_p3():
    set_seed(SEED)
    print("=== Phase U3a: STGCN Forecaster ===")
    
    sim = load_sim()
    wards = load_wards()
    edges = load_edges()
    splits = get_splits()
    
    num_wards = len(wards)
    ei = torch.from_numpy(np.stack([edges["src"].values, edges["dst"].values]).copy()).long()
    ew = torch.from_numpy(edges["weight"].values.copy()).float()
    
    X, Y, C, dates = build_tensors(sim)
    T = len(dates)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    
    t_train_end = date_to_idx[pd.to_datetime(splits["train_end"])]
    t_cal_end = date_to_idx[pd.to_datetime(splits["cal_end"])]
    
    train_origins = [t for t in range(13, t_train_end - 2)]
    cal_origins = [t for t in range(t_train_end + 1, t_cal_end - 2)]
    test_origins = [t for t in range(t_cal_end + 1, T - 3)]
    
    n_val = max(1, int(0.10 * len(train_origins)))
    train_sub = train_origins[:-n_val]
    val_sub = train_origins[-n_val:]
    
    train_loader = DataLoader(SpatioTemporalDataset(X, Y, C, train_sub), batch_size=32, shuffle=True)
    val_loader = DataLoader(SpatioTemporalDataset(X, Y, C, val_sub), batch_size=32, shuffle=False)
    
    model = STGCN(in_features=7, cov_dim=6, num_wards=num_wards)
    optimizer = torch.optim.Adam(model.parameters(), lr=2e-3)
    
    best_val_loss = float("inf")
    best_state = None
    patience = 8
    patience_counter = 0
    train_losses = []
    val_losses = []
    
    epochs = 80
    print(f"Training STGCN for up to {epochs} epochs (patience={patience})...")
    for epoch in range(1, epochs + 1):
        model.train()
        t_loss = 0.0
        for bx, bc, by, _ in train_loader:
            optimizer.zero_grad()
            pred = model(bx, bc, ei, ew)
            loss = F.l1_loss(pred, by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            t_loss += loss.item() * len(bx)
        t_loss /= len(train_sub)
        train_losses.append(t_loss)
        
        model.eval()
        v_loss = 0.0
        with torch.no_grad():
            for bx, bc, by, _ in val_loader:
                pred = model(bx, bc, ei, ew)
                loss = F.l1_loss(pred, by)
                v_loss += loss.item() * len(bx)
        v_loss /= len(val_sub)
        val_losses.append(v_loss)
        
        if epoch % 5 == 0 or epoch == 1:
            print(f"Epoch {epoch:02d}/{epochs:02d} | Train L1: {t_loss:.4f} | Val L1: {v_loss:.4f}")
            
        if v_loss < best_val_loss:
            best_val_loss = v_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping triggered at epoch {epoch}")
                break
                
    model.load_state_dict(best_state)
    torch.save(best_state, MODELS / "stgcn.pt")
    print(f"Best STGCN model saved to {MODELS / 'stgcn.pt'} (best val loss: {best_val_loss:.4f})")
    
    # Save loss curve figure
    plt.figure(figsize=(8, 4))
    plt.plot(train_losses, label="Train L1 Loss")
    plt.plot(val_losses, label="Val L1 Loss")
    plt.title("STGCN Training and Validation Loss (SIMULATED data)")
    plt.xlabel("Epoch")
    plt.ylabel("L1 Loss (Ratio)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG / "loss_curve_stgcn.png", dpi=150)
    plt.close()
    
    # Generate predictions on cal and test splits
    base_mld = wards["base_mld"].values
    zone_dict = dict(zip(wards["ward_id"], wards["zone"]))
    
    pred_records = []
    
    def predict_split(origins, split_name):
        loader = DataLoader(SpatioTemporalDataset(X, Y, C, origins), batch_size=32, shuffle=False)
        model.eval()
        with torch.no_grad():
            for bx, bc, by, b_t in loader:
                preds = model(bx, bc, ei, ew).numpy() # [B, 3, N]
                actuals = by.numpy() # [B, 3, N]
                b_t_np = b_t.numpy()
                for b_idx in range(len(b_t_np)):
                    t_val = b_t_np[b_idx]
                    o_date_str = str(pd.to_datetime(dates[t_val]).date())
                    for h_idx in range(3):
                        h = h_idx + 1
                        tgt_date_str = str(pd.to_datetime(dates[t_val + h]).date())
                        for w in range(num_wards):
                            bm = base_mld[w]
                            pred_records.append({
                                "origin_date": o_date_str,
                                "target_date": tgt_date_str,
                                "ward_id": w,
                                "h": h,
                                "actual_mld": float(actuals[b_idx, h_idx, w] * bm),
                                "pred_mld": float(preds[b_idx, h_idx, w] * bm),
                                "split": split_name
                            })
                            
    predict_split(cal_origins, "cal")
    predict_split(test_origins, "test")
    
    preds_df = pd.DataFrame(pred_records)
    preds_df.to_csv(DATA / "preds_stgcn.csv", index=False)
    print(f"preds_stgcn.csv saved: {len(preds_df)} rows")
    
    # Metrics computation on test set
    test_df = preds_df[preds_df["split"] == "test"].copy()
    test_mae = float(np.mean(np.abs(test_df["actual_mld"] - test_df["pred_mld"])))
    test_rmse = float(np.sqrt(np.mean((test_df["actual_mld"] - test_df["pred_mld"]) ** 2)))
    
    by_h = {}
    for h in [1, 2, 3]:
        sub = test_df[test_df["h"] == h]
        by_h[f"h_{h}"] = {
            "mae": float(np.mean(np.abs(sub["actual_mld"] - sub["pred_mld"]))),
            "rmse": float(np.sqrt(np.mean((sub["actual_mld"] - sub["pred_mld"]) ** 2)))
        }
        
    test_df["zone"] = test_df["ward_id"].map(zone_dict)
    by_zone = {}
    for z in ["core", "mid", "periphery"]:
        sub = test_df[test_df["zone"] == z]
        by_zone[z] = {
            "mae": float(np.mean(np.abs(sub["actual_mld"] - sub["pred_mld"]))),
            "rmse": float(np.sqrt(np.mean((sub["actual_mld"] - sub["pred_mld"]) ** 2)))
        }
        
    stgcn_metrics = {
        "overall": {"mae": test_mae, "rmse": test_rmse},
        "by_horizon": by_h,
        "by_zone": by_zone,
        "epochs_trained": len(train_losses),
        "best_val_loss": float(best_val_loss)
    }
    update_metrics("stgcn", stgcn_metrics)
    
    # Load HGB metrics for comparison
    with open(RES / "metrics.json", "r", encoding="utf-8") as f:
        all_metrics = json.load(f)
        
    hgb_metrics = all_metrics.get("baselines", {}).get("overall", {}).get("hgb", {})
    hgb_test_mae = hgb_metrics.get("mae", 999.0)
    naive_test_mae = all_metrics.get("baselines", {}).get("overall", {}).get("naive", {}).get("mae", 999.0)
    
    hgb_mae_h1 = all_metrics.get("baselines", {}).get("by_horizon", {}).get("h_1", {}).get("hgb", {}).get("mae", 999.0)
    stgcn_mae_h1 = by_h["h_1"]["mae"]
    
    best_forecaster = "stgcn" if test_mae <= hgb_test_mae else "hgb"
    all_metrics["best_forecaster"] = best_forecaster
    with open(RES / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)
        
    # Copy best predictions to preds_best.csv
    best_df = preds_df if best_forecaster == "stgcn" else pd.read_csv(DATA / "preds_hgb.csv")
    best_df.to_csv(DATA / "preds_best.csv", index=False)
    print(f"Saved preds_best.csv from {best_forecaster.upper()}")
    
    # Gate Asserts
    expected_rows = (len(cal_origins) + len(test_origins)) * 3 * num_wards
    assert len(preds_df) == expected_rows, f"Expected {expected_rows} rows, got {len(preds_df)}"
    assert set(preds_df["split"].unique()) == {"cal", "test"}, "Invalid splits"
    assert not preds_df.isnull().any().any(), "NaN found in predictions"
    assert (DATA / "preds_best.csv").exists(), "preds_best.csv missing"
    
    print(f"\n--- Gate Comparison ---")
    print(f"Overall Test MAE: Naive = {naive_test_mae:.4f} | HGB = {hgb_test_mae:.4f} | STGCN = {test_mae:.4f} MLD")
    print(f"H=1 Test MAE: HGB = {hgb_mae_h1:.4f} | STGCN = {stgcn_mae_h1:.4f} MLD")
    print(f"Best Forecaster Selected: {best_forecaster.upper()} (Note: v1 and v2 numbers NOT directly comparable due to new simulator & 225 real wards)")

if __name__ == "__main__":
    run_p3()

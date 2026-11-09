import os
import sys
from datetime import datetime
from pathlib import Path
from src.config import RAW, RES

def run_gate():
    print("--- Running Phase 0 Gate ---")
    
    # 1. Imports
    import torch
    import torch_geometric
    from torch_geometric.nn import ChebConv, GATConv
    import pyomo.environ as pyo
    from pyomo.contrib.appsi.solvers.highs import Highs
    import sklearn
    import fastapi
    import uvicorn
    import imblearn
    
    print(f"torch: {torch.__version__}")
    print(f"torch_geometric: {torch_geometric.__version__}")
    import pyomo
    print(f"pyomo: {pyomo.__version__}")
    print(f"sklearn: {sklearn.__version__}")
    print(f"fastapi: {fastapi.__version__}")
    print(f"uvicorn: {uvicorn.__version__}")
    print(f"imblearn: {imblearn.__version__}")
    
    # 2. ChebConv forward pass
    conv = ChebConv(in_channels=4, out_channels=8, K=2)
    x = torch.randn(10, 4)
    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 0]], dtype=torch.long)
    out = conv(x, edge_index)
    assert out.shape == (10, 8), f"ChebConv forward pass failed: {out.shape}"
    print("ChebConv forward pass: PASSED")
    
    # 3. Pyomo + HiGHS trivial LP
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(0, 10))
    model.obj = pyo.Objective(expr=model.x, sense=pyo.minimize)
    model.c = pyo.Constraint(expr=model.x >= 2.5)
    
    solver = pyo.SolverFactory("appsi_highs")
    res = solver.solve(model)
    assert abs(pyo.value(model.x) - 2.5) < 1e-4, "HiGHS LP solve failed"
    print("Pyomo + HiGHS LP solve: PASSED")
    
    # 4. Check raw files
    raw_files = ["rainfall_monthly.csv", "tanker_2015.csv", "tanker_2019.csv", "tanker_2024.csv", "borewells.kml"]
    for rf in raw_files:
        p = RAW / rf
        assert p.exists() and p.stat().st_size > 0, f"Raw file missing or empty: {rf}"
    print("All raw data files verified: PASSED")
    
    # Append to PROGRESS.md
    today = datetime.now().strftime("%Y-%m-%d")
    progress_file = RES / "PROGRESS.md"
    entry = f"P0 done | {today} | Python 3.12, torch, pyomo+highs, all raw data verified\n"
    with open(progress_file, "a", encoding="utf-8") as f:
        f.write(entry)
    print("Phase 0 Gate: ALL PASSED")

if __name__ == "__main__":
    run_gate()

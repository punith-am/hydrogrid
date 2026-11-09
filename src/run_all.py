import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MODULES = [
    ("Phase U1: Civic GIS, Graph Topology & GeoJSONs", "src.u1_geo"),
    ("Phase U2: Simulator v2 with Real IMD Weather", "src.p1_graph_sim"),
    ("Phase U3a: HistGradientBoosting Tabular Forecaster", "src.p2_baselines"),
    ("Phase U3a: Spatio-Temporal Graph Forecaster (STGCN)", "src.p3_stgcn"),
    ("Phase U3b: Conformal Prediction (Split + ACI)", "src.p4_conformal"),
    ("Phase U3b: Cascading Early Warning (GAT)", "src.p5_cascade"),
    ("Phase U4: Prescriptive HiGHS MILP Optimizer", "src.p6_optimize"),
    ("Phase U4: Actionable DiCE Counterfactual Recourse", "src.p7_recourse"),
    ("Phase U4: Wasserstein Drift & Continual Learning", "src.p8_drift"),
    ("Phase U5: Demo Cache Generator for Instant Presets", "src.u5_cache")
]

def run_all():
    print("=" * 75)
    print("  HydroGrid 2.0: Official End-to-End Civic AI Pipeline")
    print("  225 BBMP Wards • 8.449M Pop • 7,433 Borewells • 39 STPs • 774 Edges")
    print("=" * 75)
    t_start = time.time()

    # Step 0: Inventory check
    inv_file = ROOT / "results" / "dataset_inventory.json"
    if not inv_file.exists():
        print("\n>>> Running Phase U0: Dataset Inventory (src.u0_inventory)...")
        res = subprocess.run([sys.executable, "-m", "src.u0_inventory"])
        if res.returncode != 0:
            print("[ERROR] Inventory failed. Halting.")
            sys.exit(res.returncode)
    else:
        print("[OK] Dataset inventory verified (Phase U0).")

    for name, module in MODULES:
        print(f"\n>>> Running {name} ({module})...")
        t0 = time.time()
        res = subprocess.run([sys.executable, "-m", module])
        if res.returncode != 0:
            print(f"\n[ERROR] Module {module} failed with return code {res.returncode}. Halting pipeline.")
            sys.exit(res.returncode)
        print(f">>> {name} completed successfully in {time.time()-t0:.2f}s.")

    print("\n" + "=" * 75)
    print(f"  All pipeline phases completed successfully in {time.time()-t_start:.2f}s!")
    print("=" * 75)

if __name__ == "__main__":
    run_all()

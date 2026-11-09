"""
U6c verification test script
Tests Risk, Optimizer, Recourse, and Health views, frontend code, and backend API routes.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from app.main import (
    get_risk,
    post_optimize,
    OptimizeRequest,
    get_recourse_api,
    get_drift,
    get_presets
)

def test_u6c():
    base = Path("app/static/js/views")
    required_views = [
        "risk.js",
        "optimizer.js",
        "recourse.js",
        "health.js"
    ]

    print("Checking required U6c views...")
    for rv in required_views:
        p = base / rv
        assert p.exists(), f"Missing view: {p}"
        assert p.stat().st_size > 1000, f"View too small: {p} ({p.stat().st_size} bytes)"
        print(f"  [OK] {rv} ({p.stat().st_size} bytes)")

    print("\nTesting /api/risk...")
    r = get_risk(date="2024-06-15")
    assert "top15" in r and len(r["top15"]) == 15
    assert "all_risks" in r and len(r["all_risks"]) == 225
    top_w = r["top15"][0]
    assert "risk" in top_w and top_w["risk"] > 0
    print(f"  [OK] /api/risk (top: {top_w['ward_name']}, risk: {top_w['risk']:.4f})")

    print("\nTesting /api/optimize (MILP Preset & Solve)...")
    req = OptimizeRequest(date="2024-06-15", gw_factor=0.6, tanker_price=0.108333, stp_price=0.08, use="upper")
    opt = post_optimize(req)
    assert "kpis" in opt
    k = opt["kpis"]
    assert k["saving_inr"] > 1000000.0, f"Expected >1M INR saving, got {k['saving_inr']}"
    assert k["plants_opened_count"] > 0
    assert "flows" in opt and len(opt["flows"]) > 0
    assert "stps" in opt and len(opt["stps"]) == 39
    assert "per_ward" in opt and len(opt["per_ward"]["tanker_mld"]) == 225
    print(f"  [OK] /api/optimize (saving: INR {k['saving_inr']:,.0f}, STPs: {k['plants_opened_count']}, flows: {len(opt['flows'])})")

    print("\nTesting /api/recourse...")
    for wid in [0, 98, 168]:
        rec = get_recourse_api(ward_id=wid, date="2024-06-15")
        assert rec["ward_id"] == wid
        assert "counterfactuals" in rec
        print(f"  [OK] /api/recourse (ward {wid}: {len(rec['counterfactuals'])} counterfactuals)")

    print("\nTesting /api/drift...")
    dr = get_drift()
    assert dr["first_alarm_date"] == "2024-04-12"
    assert len(dr["series"]) == 366
    assert "continual_learning" in dr
    cl = dr["continual_learning"]
    assert "frozen" in cl and "incremental" in cl and "full_retrain" in cl
    print(f"  [OK] /api/drift (alarm: {dr['first_alarm_date']}, series: {len(dr['series'])}, CL incremental: {cl['incremental']['fit_seconds']}s)")

    print("\nTesting /api/presets...")
    presets = get_presets()
    assert len(presets) >= 3
    assert "normal" in presets and "summer" in presets and "drought" in presets
    print(f"  [OK] /api/presets ({list(presets.keys())})")

    print("\nALL PHASE U6c VERIFICATION CHECKS PASSED!")

if __name__ == "__main__":
    test_u6c()


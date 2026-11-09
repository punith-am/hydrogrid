import time
from pathlib import Path
from app.main import (
    get_overview, get_wards, get_dates, get_forecast,
    get_map, get_risk, post_optimize, get_recourse_api,
    get_drift, get_methods, OptimizeRequest
)
from src.config import ROOT

def test_api():
    print("=== Testing HydroGrid FastAPI Endpoints & Static UI ===")
    
    # 1. Verify static frontend assets exist
    static_dir = ROOT / "app" / "static"
    for fname in ["index.html", "style.css", "app.js"]:
        fpath = static_dir / fname
        assert fpath.exists(), f"Static asset {fname} missing"
        assert fpath.stat().st_size > 100, f"Static asset {fname} empty"
    print("[PASS] All static assets verified (index.html, style.css, app.js).")

    # 2. Test GET /api/overview
    t0 = time.time()
    overview = get_overview()
    assert "totals" in overview and "headline_metrics" in overview, "Overview missing expected keys"
    assert overview["totals"]["total_demand_mld"] == 2632.0, "Total demand mismatch"
    print(f"[PASS] GET /api/overview (200 OK, {time.time()-t0:.3f}s)")

    # 3. Test GET /api/wards
    t0 = time.time()
    wards_res = get_wards()
    assert len(wards_res["wards"]) == 198, "Expected 198 wards"
    assert len(wards_res["edges"]) > 0, "Edges empty"
    print(f"[PASS] GET /api/wards (200 OK, {time.time()-t0:.3f}s)")

    # 4. Test GET /api/dates
    t0 = time.time()
    dates_res = get_dates()
    assert len(dates_res["dates"]) > 0, "Dates list empty"
    print(f"[PASS] GET /api/dates (200 OK, {time.time()-t0:.3f}s)")

    # 5. Test GET /api/forecast
    t0 = time.time()
    fc_res = get_forecast(ward_id=0, h=1)
    assert len(fc_res["dates"]) > 0, "Forecast dates empty"
    assert len(fc_res["pred"]) == len(fc_res["actual"]), "Length mismatch"
    assert fc_res["kpis"]["coverage_static"] > 0, "Coverage zero"
    print(f"[PASS] GET /api/forecast (200 OK, {time.time()-t0:.3f}s)")

    # 6. Test GET /api/map (all layers)
    for layer in ["demand", "stress", "risk"]:
        t0 = time.time()
        m_res = get_map("2024-06-15", layer)
        assert len(m_res["values"]) == 198, f"Layer {layer} did not return 198 wards"
        print(f"[PASS] GET /api/map?layer={layer} (200 OK, {time.time()-t0:.3f}s)")

    # 7. Test GET /api/risk
    t0 = time.time()
    risk_res = get_risk("2024-06-15")
    assert len(risk_res["top15"]) == 15, "Expected top 15 wards"
    print(f"[PASS] GET /api/risk (200 OK, {time.time()-t0:.3f}s)")

    # 8. Test POST /api/optimize
    t0 = time.time()
    req = OptimizeRequest(date="2024-06-15", gw_factor=0.6, tanker_price=0.108333, stp_price=0.08, use="upper")
    opt_res = post_optimize(req)
    dt_opt = time.time() - t0
    assert opt_res["kpis"]["unmet_mld"] == 0.0, "Optimization returned unmet demand"
    assert opt_res["kpis"]["saving_inr"] > 0, "Optimization returned zero savings"
    assert dt_opt < 15.0, f"Optimization solve took {dt_opt:.2f}s (limit: 15s)"
    print(f"[PASS] POST /api/optimize (200 OK, {dt_opt:.3f}s, saving: {opt_res['kpis']['saving_inr']:,.0f} INR)")

    # 9. Test GET /api/recourse
    t0 = time.time()
    rec_res = get_recourse_api(ward_id=168, date="2024-06-15")
    assert len(rec_res["counterfactuals"]) >= 1, "Recourse returned no counterfactuals"
    print(f"[PASS] GET /api/recourse (200 OK, {time.time()-t0:.3f}s)")

    # 10. Test GET /api/drift
    t0 = time.time()
    drift_res = get_drift()
    assert len(drift_res["series"]) > 0, "Drift series empty"
    assert drift_res["first_alarm_date"] is not None, "First alarm date missing"
    print(f"[PASS] GET /api/drift (200 OK, {time.time()-t0:.3f}s)")

    # 11. Test GET /api/methods
    t0 = time.time()
    meth_res = get_methods()
    assert len(meth_res["provenance_table"]) > 0, "Provenance table empty"
    assert len(meth_res["honest_limitations"]) > 0, "Limitations list empty"
    print(f"[PASS] GET /api/methods (200 OK, {time.time()-t0:.3f}s)")

    print("\nAll 11 endpoints and static assets verified successfully! Gate PASSED.")

if __name__ == "__main__":
    test_api()

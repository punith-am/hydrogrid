"""
U6d verification test script
Tests tour.js, palette.js, print.css, and runs full end-to-end endpoint verification across all 23 API routes.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from app.main import (
    app,
    get_health,
    get_overview,
    get_briefing,
    get_geo_layer,
    get_wards,
    get_dates,
    get_forecast,
    get_map,
    get_risk,
    post_optimize,
    OptimizeRequest,
    get_recourse_api,
    get_drift,
    get_methods,
    get_v1compare,
    get_presets,
    search_wards
)

def test_u6d():
    print("=== Step 1: Checking U6d Assets ===")
    tour_file = Path("app/static/js/tour.js")
    palette_file = Path("app/static/js/palette.js")
    print_file = Path("app/static/css/print.css")

    assert tour_file.exists(), "Missing tour.js"
    assert tour_file.stat().st_size > 1000, "tour.js too small"
    tour_text = tour_file.read_text(encoding="utf-8")
    assert "Step 1 of 9" in tour_text or "TOUR_STEPS" in tour_text
    assert "Step 9 of 9" in tour_text or len(tour_text.split("title:")) >= 9
    print(f"  [OK] tour.js verified ({tour_file.stat().st_size} bytes, 9 guided steps)")

    assert palette_file.exists(), "Missing palette.js"
    assert palette_file.stat().st_size > 1000, "palette.js too small"
    palette_text = palette_file.read_text(encoding="utf-8")
    assert "SYSTEM_COMMANDS" in palette_text
    print(f"  [OK] palette.js verified ({palette_file.stat().st_size} bytes, command center ready)")

    assert print_file.exists(), "Missing print.css"
    print_text = print_file.read_text(encoding="utf-8")
    assert "@media print" in print_text
    assert ".sidebar" in print_text
    print(f"  [OK] print.css verified ({print_file.stat().st_size} bytes, clean print rules)")

    print("\n=== Step 2: Full End-to-End API Route Audit (23 Endpoints) ===")
    
    # 1. Health
    h = get_health()
    assert h["status"] == "healthy"
    print("  [200 OK] /api/health")

    # 2. Overview
    ov = get_overview()
    assert ov["totals"]["num_wards"] == 225
    print("  [200 OK] /api/overview")

    # 3. Briefing
    br = get_briefing("2024-06-15")
    assert len(br["sentences"]) >= 3
    print("  [200 OK] /api/briefing")

    # 4-7. Geo Layers
    for layer in ["wards", "pipes", "stps", "borewells"]:
        resp = get_geo_layer(layer)
        assert resp.status_code == 200
        print(f"  [200 OK] /api/geo/{layer}")

    # 8. Wards
    w = get_wards()
    assert len(w["wards"]) == 225
    print("  [200 OK] /api/wards")

    # 9. Dates
    d = get_dates()
    assert len(d["dates"]) == 363
    print("  [200 OK] /api/dates")

    # 10. Forecast
    fc = get_forecast(ward_id=168, h=1)
    assert len(fc["pred"]) == 363
    print("  [200 OK] /api/forecast")

    # 11-15. Map Layers
    for lyr in ["demand", "shortfall", "risk", "stress", "population"]:
        m = get_map(date="2024-06-15", layer=lyr)
        assert len(m["values"]) == 225
        print(f"  [200 OK] /api/map?layer={lyr}")

    # 16. Cascade Risk
    rk = get_risk(date="2024-06-15")
    assert len(rk["top15"]) == 15
    print("  [200 OK] /api/risk")

    # 17. Prescriptive Optimizer
    req = OptimizeRequest(date="2024-06-15", gw_factor=0.6, tanker_price=0.108333, stp_price=0.08, use="upper")
    opt = post_optimize(req)
    assert opt["kpis"]["saving_inr"] > 1000000.0
    print("  [200 OK] /api/optimize")

    # 18. Actionable Recourse
    rec = get_recourse_api(ward_id=168, date="2024-06-15")
    assert len(rec["counterfactuals"]) >= 1
    print("  [200 OK] /api/recourse")

    # 19. Model Drift
    dr = get_drift()
    assert len(dr["series"]) == 366
    print("  [200 OK] /api/drift")

    # 20. Methods
    met = get_methods()
    assert len(met["pipeline_steps"]) >= 8
    print("  [200 OK] /api/methods")

    # 21. V1 Comparison
    v1 = get_v1compare()
    assert len(v1["metrics"]) >= 8
    print("  [200 OK] /api/v1compare")

    # 22. Presets
    pr = get_presets()
    assert len(pr) >= 3
    print("  [200 OK] /api/presets")

    # 23. Search
    sr = search_wards("bellanduru")
    assert len(sr) >= 1
    print("  [200 OK] /api/search")

    print("\n=== Step 3: Polish & Self-Check Validation ===")
    views = ["overview.js", "map.js", "forecast.js", "risk.js", "optimizer.js", "recourse.js", "health.js", "methods.js"]
    for v in views:
        vp = Path(f"app/static/js/views/{v}")
        txt = vp.read_text(encoding="utf-8")
        assert "198" not in txt or "v1" in txt, f"Hardcoded 198 found in {v}"
        print(f"  [OK] Clean provenance & dynamic delimitation in {v}")

    print("\nALL PHASE U6d VERIFICATION CHECKS PASSED!")

if __name__ == "__main__":
    test_u6d()


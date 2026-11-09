"""
U6b verification test script
Tests all Map and Forecast views, assets, and backend API endpoints.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from app.main import (
    get_geo_layer,
    get_map,
    get_forecast,
    get_dates,
    get_wards
)

def test_u6b():
    base = Path("app/static")
    required_files = [
        "js/map.js",
        "js/views/map.js",
        "js/views/forecast.js"
    ]
    
    print("Checking required U6b files...")
    for rf in required_files:
        p = base / rf
        assert p.exists(), f"Missing file: {p}"
        assert p.stat().st_size > 500, f"File too small: {p} ({p.stat().st_size} bytes)"
        print(f"  [OK] {rf} ({p.stat().st_size} bytes)")

    print("\nVerifying GeoJSON endpoints...")
    for layer in ["wards", "pipes", "stps", "borewells"]:
        resp = get_geo_layer(layer)
        assert resp.status_code == 200
        geo = json.loads(resp.body)
        assert "features" in geo or "type" in geo
        count = len(geo.get("features", []))
        print(f"  [OK] /api/geo/{layer} ({count} features, {len(resp.body)} bytes)")

    print("\nVerifying Map Layer Data endpoints...")
    for lyr in ["demand", "shortfall", "risk", "stress", "population"]:
        m = get_map(date="2024-06-15", layer=lyr)
        assert m["layer"] == lyr
        assert len(m["values"]) == 225
        print(f"  [OK] /api/map (layer={lyr}, 225 wards mapped)")

    print("\nVerifying Dates endpoint...")
    d = get_dates()
    assert len(d["dates"]) == 363
    print(f"  [OK] /api/dates ({len(d['dates'])} dates available)")

    print("\nVerifying Forecast endpoints across horizons & wards...")
    for wid in [0, 107, 168]:
        for h in [1, 2, 3]:
            fc = get_forecast(ward_id=wid, h=h)
            assert fc["ward_id"] == wid
            assert fc["h"] == h
            assert len(fc["dates"]) == 363
            assert len(fc["actual"]) == 363
            assert len(fc["pred"]) == 363
            assert "kpis" in fc
    print("  [OK] /api/forecast verified across wards (0, 107, 168) and horizons (h=1,2,3)")

    print("\nALL PHASE U6b VERIFICATION CHECKS PASSED!")

if __name__ == "__main__":
    test_u6b()

"""
U6a verification test script
Tests all frontend assets and endpoints required for Phase U6a.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import json
from app.main import (
    get_overview,
    get_briefing,
    get_methods,
    get_v1compare,
    get_provenance,
    search_wards,
    get_health
)

def test_u6a():
    base = Path("app/static")
    required_files = [
        "css/tokens.css",
        "css/base.css",
        "css/components.css",
        "css/print.css",
        "js/api.js",
        "js/charts.js",
        "js/ui.js",
        "js/main.js",
        "js/views/overview.js",
        "js/views/methods.js",
        "index.html"
    ]
    
    print("Checking required files...")
    for rf in required_files:
        p = base / rf
        assert p.exists(), f"Missing file: {p}"
        assert p.stat().st_size > 50, f"File too small: {p}"
        print(f"  [OK] {rf} ({p.stat().st_size} bytes)")

    print("\nVerifying index.html contents...")
    html = (base / "index.html").read_text(encoding="utf-8")
    assert "HydroGrid" in html
    assert "tokens.css" in html
    assert "base.css" in html
    assert "components.css" in html
    assert "print.css" in html
    assert "js/main.js" in html
    assert "data-route=\"overview\"" in html
    assert "data-route=\"methods\"" in html
    assert "skip-link" in html
    assert "offline-banner" in html
    assert "SIMULATED DEMAND" in html.upper() or "SIMULATED" in html.upper()
    # Check that neon style is gone
    assert "glass-card" not in html
    print("  [OK] index.html structure verified")

    print("\nTesting backend endpoints for Overview & Methods...")
    ov = get_overview()
    assert ov["totals"]["num_wards"] == 225
    assert ov["totals"]["total_population"] == 8449004
    print("  [OK] /api/overview")

    br = get_briefing("2024-06-15")
    assert "sentences" in br and len(br["sentences"]) >= 3
    print("  [OK] /api/briefing")

    met = get_methods()
    assert len(met["provenance_table"]) >= 10
    assert len(met["pipeline_steps"]) >= 8
    print("  [OK] /api/methods")

    v1c = get_v1compare()
    assert len(v1c.get("metrics", [])) >= 8
    print("  [OK] /api/v1compare")

    prov = get_provenance()
    assert len(prov) >= 10
    print("  [OK] /api/provenance")

    srch = search_wards("bellandur")
    assert len(srch) >= 1
    print(f"  [OK] /api/search (found {srch[0]['ward_name']})")

    hlth = get_health()
    assert hlth["status"] == "healthy"
    assert hlth["n_wards"] == 225
    print("  [OK] /api/health")

    print("\nALL PHASE U6a VERIFICATION CHECKS PASSED!")

if __name__ == "__main__":
    test_u6a()

import time
import json
from app.main import (
    get_health, get_overview, get_geo_layer, get_provenance,
    search_wards, get_briefing, get_v1compare, get_presets,
    get_wards, get_dates, get_forecast, get_map, get_risk,
    post_optimize, get_recourse_api, get_drift, get_methods,
    OptimizeRequest
)

def run_u5_gate():
    print("=== Phase U5 Gate: Testing All API Endpoints & Latencies ===")
    
    # 1. Health
    h = get_health()
    assert h["status"] == "healthy" and h["n_wards"] == 225, f"Health check failed: {h}"
    print(f"  Health: OK (n_wards={h['n_wards']})")
    
    # 2. Overview
    ov = get_overview()
    assert ov["totals"]["num_wards"] == 225, "Overview ward count mismatch"
    assert ov["totals"]["total_population"] == 8449004, "Overview population mismatch"
    print(f"  Overview: OK (Pop: {ov['totals']['total_population']:,}, STPs: {ov['real_anchors']['stps_count']})")
    
    # 3. Geo Layers (Cache-Control & content)
    for layer in ["wards", "stps", "pipes", "borewells"]:
        resp = get_geo_layer(layer)
        assert resp.status_code == 200, f"Geo layer {layer} returned non-200"
        assert "max-age=3600" in resp.headers.get("Cache-Control", ""), f"Missing Cache-Control on {layer}"
        data = json.loads(resp.body.decode("utf-8"))
        features = data.get("features", [])
        assert len(features) > 0, f"Empty features in {layer}"
        print(f"  Geo {layer:10s}: OK ({len(resp.body)/1024:.1f} KB, {len(features)} features)")
        
    # 4. Search
    sw = search_wards("hebbal")
    assert len(sw) > 0, "No wards found for 'hebbal'"
    print(f"  Search: OK ({len(sw)} matches for 'hebbal')")
    
    # 5. Briefing
    br = get_briefing("2024-06-15")
    assert "sentences" in br and len(br["sentences"]) == 4, "Briefing sentences missing"
    print(f"  Briefing: OK ({br['sentences'][0][:60]}...)")
    
    # 6. v1compare & Presets
    v1c = get_v1compare()
    assert len(v1c.get("metrics", [])) > 0, "Missing v1compare metrics"
    print(f"  v1 Compare: OK ({len(v1c['metrics'])} comparisons)")
    
    presets = get_presets()
    assert "normal" in presets and "summer" in presets and "drought" in presets, "Presets missing"
    print(f"  Presets: OK ({list(presets.keys())})")
    
    # 7. Map layers
    for lay in ["demand", "stress", "population", "shortfall", "risk"]:
        m_res = get_map(date="2024-06-15", layer=lay)
        assert len(m_res["values"]) == 225, f"Map layer {lay} expected 225 values, got {len(m_res['values'])}"
        print(f"  Map layer {lay:12s}: OK (225 values)")
        
    # 8. Forecast, Risk, Recourse, Drift, Methods
    fc = get_forecast(ward_id=0, h=1)
    assert "actual" in fc and len(fc["actual"]) > 0, "Forecast failed"
    print(f"  Forecast (w=0, h=1): OK (Coverage ACI: {fc['kpis']['coverage_aci']}%)")
    
    rk = get_risk("2024-06-15")
    assert len(rk["top15"]) == 15, "Risk top15 missing"
    print(f"  Risk top15: OK (Highest: {rk['top15'][0]['ward_name']} - {rk['top15'][0]['risk']})")
    
    rc = get_recourse_api(ward_id=168, date="2024-06-15")
    assert len(rc["counterfactuals"]) > 0, "Recourse counterfactuals empty"
    print(f"  Recourse (w=168): OK ({len(rc['counterfactuals'])} counterfactuals)")
    
    df_res = get_drift()
    assert len(df_res["series"]) > 0, "Drift series empty"
    print(f"  Drift: OK (First alarm: {df_res['first_alarm_date']})")
    
    meth = get_methods()
    assert len(meth["pipeline_steps"]) == 9, "Methods missing steps"
    print(f"  Methods: OK ({len(meth['pipeline_steps'])} steps, {len(meth['provenance_table'])} provenance items)")
    
    # 9. Preset Optimize (< 1s from cache)
    t0 = time.time()
    req_p = OptimizeRequest(date="2024-06-15", gw_factor=0.6, tanker_price=0.108333, stp_price=0.08, use="upper")
    opt_p = post_optimize(req_p)
    t_preset = time.time() - t0
    assert opt_p["kpis"]["unmet_mld"] == 0.0, "Preset optimize had unmet demand"
    assert t_preset < 1.0, f"Preset optimize took too long: {t_preset:.4f} s"
    print(f"\n  Preset Optimize Latency: {t_preset*1000:.2f} ms (Gate: < 1000 ms) | Saving: {opt_p['kpis']['saving_inr']:,.0f} INR")
    
    # 10. Live Optimize (< 20s)
    t0 = time.time()
    req_l = OptimizeRequest(date="2024-05-15", gw_factor=0.45, tanker_price=0.14, stp_price=0.08, use="upper")
    opt_l = post_optimize(req_l)
    t_live = time.time() - t0
    assert opt_l["kpis"]["unmet_mld"] == 0.0, "Live optimize had unmet demand"
    assert t_live < 20.0, f"Live optimize took too long: {t_live:.3f} s"
    print(f"  Live Optimize Latency:   {t_live:.3f} s (Gate: < 20.0 s) | Saving: {opt_l['kpis']['saving_inr']:,.0f} INR")
    
    print("\n=== Phase U5 Gate: ALL PASSED ===")

if __name__ == "__main__":
    run_u5_gate()

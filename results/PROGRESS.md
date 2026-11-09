P0 done | 2026-11-05 | Python 3.12, torch, pyomo+highs, all raw data verified
P1 done | 2026-11-05 | 198 wards, 960 edges, sim shape (217008, 5), 3923 failures, 773 onsets
P2 done | 2026-11-05 | HGB MAE: 0.595 MLD (h=1: 0.559), Naive MAE: 0.732 MLD
P3 done | 2026-11-05 | STGCN MAE: 0.7291 MLD (h=1: 0.7132), best: hgb
P4 done | 2026-11-05 | Static cov: 83.0%, ACI cov: 88.1%, Winkler: 2.980
P5 done | 2026-11-05 | GAT PR-AUC: 0.1870 (prev: 0.21%), ROC-AUC: 0.8592, F1: 0.3178
P6 done | 2026-11-05 | MILP solve: 0.08s, unmet: 0, saving: 517,399 INR, robustness unmet: 7.24 MLD (point: 75.08 MLD)
P7 done | 2026-11-05 | Recourse validity: 100.0%, mean proximity: 1.576, conformal valid: 38.1% (point: 54.2%)
P8 done | 2026-11-05 | Drift alarm: 2024-07-16, MAE frozen: 0.5866 vs inc: 0.4312 MLD (fit: 0.17s)
P9 done | 2026-11-05 | FastAPI backend, 11 endpoints verified 200 OK, dark glassmorphism 8-tab UI
P10 done | 2026-11-05 | run_all.py orchestrator, requirements.txt, comprehensive README.md, all 43 artifacts verified
U0 partial | step 1 done
U0 done | 2026-11-05 | v1 backed up, shapely 2.2 installed, 32 files inventoried, provenance.json created
U1a done | 2026-11-05 | 225 real BBMP wards, 8.449M pop, 7433 borewells indexed, real_wards.png saved
U1b done | 2026-11-05 | 774 undirected edges (border+trunk), 39 STPs (548.6 MLD reuse), 3 GeoJSONs (1.30 MB total), graph connected
U2 done | 2026-11-05 | 411075 sim rows (225w x 1827d), weather_daily.csv created, mean demand 2632 MLD, tmax corr 0.598, onsets 1259/311
U3a done | 2026-11-05 | HGB MAE: 0.451 MLD, STGCN MAE: 0.537 MLD, Naive: 0.621 MLD; HGB chosen best
U3b done | 2026-11-05 | Conformal static cov: 85.7%, ACI cov: 89.1%, GAT PR-AUC: 0.110 vs prevalence 0.39% (ROC-AUC 0.860)
U4 done | 2026-11-05 | MILP solve: 0.50s, 0 unmet, 1.43M INR daily saving, recourse validity: 100%, drift alarm: 2024-04-12
U5 done | 2026-11-06 | 13 API endpoints active, GZip middleware, demo_cache.json (0ms preset, 0.5s live), all tests passed
U6a done | 2026-11-06 | Editorial UI shell, tokens/base/components/print CSS, hash router, theme toggle, Overview & Methods views verified
U6b done | 2026-11-06 | Leaflet map with 5 layers & 3 toggles, date playback, ward drawer, Forecast view with 90% ACI band & model benchmark
U6c done | 2026-11-06 | Risk (GAT PR-AUC 0.110), Optimizer (MILP flow lines & presets), Recourse (DiCE 100% validity), Health (Wasserstein drift & CL) views verified
U6d done | 2026-11-06 | 9-step guided tour (tour.js), command palette (palette.js), print stylesheet, all 23 API endpoints verified
U7 done | 2026-11-06 | Orchestrator src/run_all.py updated, frozen requirements.txt, comprehensive README.md with Evaluator Kit & honesty statements, all gates passed

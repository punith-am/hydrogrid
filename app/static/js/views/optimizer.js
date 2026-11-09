// MILP Prescriptive Supply & Reuse Optimizer View for HydroGrid 2.0
import { fetchApi } from '../api.js';
import { createChip, createKpiCard, renderInlineBar } from '../ui.js';
import { renderChart, getThemeTokens } from '../charts.js';
import { initLeafletMap, createWardLayer, createStpsLayer } from '../map.js';

let activeAbortController = null;
let optMapInstance = null;
let flowLinesGroup = null;

export async function renderOptimizer(container, appState) {
  const currentDate = appState.date || '2024-06-15';
  let currentGw = 0.6;
  let currentTanker = 0.108333;
  let currentStp = 0.08;
  let currentUse = 'upper';

  container.innerHTML = `
    <div class="optimizer-view" style="max-width: var(--maxw); margin: 0 auto;">
      <!-- Presets & Planning Strategy Bar -->
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 12px 18px; margin-bottom: 24px;">
        <!-- Scenario Presets -->
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 11px; font-feature-settings: 'c2sc', 'smcp'; text-transform: uppercase; color: var(--text-3); font-weight: 600;">Scenario Presets</span>
          <button class="btn btn-primary preset-btn active" data-preset="normal" style="padding: 4px 10px; font-size: 12px;">Normal Day (0ms)</button>
          <button class="btn btn-ghost preset-btn" data-preset="summer" style="padding: 4px 10px; font-size: 12px;">Summer Scarcity</button>
          <button class="btn btn-ghost preset-btn" data-preset="drought" style="padding: 4px 10px; font-size: 12px;">Drought Crisis</button>
        </div>

        <!-- Planning Strategy (Conformal Upper Bound vs Point Forecast) -->
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 11px; font-feature-settings: 'c2sc', 'smcp'; text-transform: uppercase; color: var(--text-3); font-weight: 600;">Safety Buffer</span>
          <div class="segmented-control" id="opt-use-control">
            <button class="segmented-btn active" data-use="upper">Conformal Upper Bound (Robust 90%)</button>
            <button class="segmented-btn" data-use="point">Point Forecast (Nominal)</button>
          </div>
        </div>
      </div>

      <!-- Two-Column Layout: Controls (Left) and Results KPIs (Right) -->
      <div style="display: grid; grid-template-columns: 320px 1fr; gap: 20px; margin-bottom: 24px;">
        <!-- Left Control Panel -->
        <div class="card" data-tour="optimizer-controls" style="padding: 20px;">
          <div class="card-header" style="margin-bottom: 16px;">
            <div>
              <h3 class="card-title">Economic & Hydrological Levers</h3>
              <p class="card-subtitle">Mixed-Integer Linear Program constraints</p>
            </div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 18px;">
            <!-- Groundwater Factor Slider -->
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                <span style="color: var(--text); font-weight: 500;">Groundwater Availability</span>
                <span id="label-gw-val" style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-ink);">60%</span>
              </div>
              <input type="range" id="slider-gw" min="20" max="100" step="5" value="60" style="width: 100%; accent-color: var(--accent); cursor: pointer;">
              <div style="font-size: 11px; color: var(--text-3); margin-top: 4px;">Baseline extraction: 1,372 MLD across 7,433 wells</div>
            </div>

            <!-- Tanker Price Slider -->
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                <span style="color: var(--text); font-weight: 500;">Commercial Tanker Price</span>
                <span id="label-tanker-val" style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-ink);">₹1,300 / 12kL</span>
              </div>
              <input type="range" id="slider-tanker" min="800" max="2200" step="50" value="1300" style="width: 100%; accent-color: var(--accent); cursor: pointer;">
              <div style="font-size: 11px; color: var(--text-3); margin-top: 4px;">Private water market rate (₹0.108 / L)</div>
            </div>

            <!-- Treated Water Price Slider -->
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                <span style="color: var(--text); font-weight: 500;">Treated STP Water Price</span>
                <span id="label-stp-val" style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-ink);">₹0.080 / L</span>
              </div>
              <input type="range" id="slider-stp" min="40" max="140" step="5" value="80" style="width: 100%; accent-color: var(--accent); cursor: pointer;">
              <div style="font-size: 11px; color: var(--text-3); margin-top: 4px;">BWSSB secondary treated bulk reuse tariff</div>
            </div>

            <button id="btn-run-opt" class="btn btn-primary" style="justify-content: center; padding: 10px; font-size: 13px; margin-top: 8px;">
              Solve MILP Dispatch →
            </button>
            <div id="opt-solve-meta" style="font-size: 11.5px; color: var(--text-3); text-align: center;">
              Instant from cache (0.00s)
            </div>
          </div>
        </div>

        <!-- Right Results KPIs Grid -->
        <div style="display: flex; flex-direction: column; gap: 16px;">
          <div class="kpi-grid" id="opt-kpi-grid">
            ${createKpiCard({ label: 'Optimized Daily Cost', value: '₹23.70M', unit: '', sub: 'Includes reuse transport & tanker fills' })}
            ${createKpiCard({ label: 'All-Tanker Baseline', value: '₹25.13M', unit: '', sub: 'Cost if deficit met only by private tankers' })}
            ${createKpiCard({ label: 'Daily Public Saving', value: '₹1.43M', unit: '', sub: '5.7% fiscal saving for municipal wards' })}
            ${createKpiCard({ label: 'Tanker Fills Avoided', value: '123.05', unit: 'MLD', sub: '10,250 tanker truck trips eliminated' })}
          </div>

          <div class="kpi-grid">
            ${createKpiCard({ label: 'Active STP Plants', value: '11', unit: '/ 39', sub: 'Dispatched to 12 nearest wards <= 20km' })}
            ${createKpiCard({ label: 'Realized Unmet Deficit', value: '0.00', unit: 'MLD', sub: 'Zero civic unmet demand under upper bound' })}
            ${createKpiCard({ label: 'Mean Arc Transport', value: '8.4', unit: 'km', sub: 'Haversine distance × 1.3 road circuity' })}
            ${createKpiCard({ label: 'Max Secondary Reuse', value: '35%', unit: 'Cap', sub: 'Non-potable applications only' })}
          </div>
        </div>
      </div>

      <!-- Flow Lines Map & Top 25 Wards Stacked Bars -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px;">
        <!-- Left: Leaflet STP to Ward Flow Map -->
        <div class="card" style="display: flex; flex-direction: column;">
          <div class="card-header">
            <div>
              <h3 class="card-title">Prescriptive STP-to-Ward Routing Arcs</h3>
              <p class="card-subtitle">Optimal pipeline & tanker routing from 39 treatment plants</p>
            </div>
            ${createChip('derived')}
          </div>
          <div class="card-body" style="flex: 1; padding: 0; min-height: 440px; position: relative;">
            <div id="opt-map-canvas" style="width: 100%; height: 100%; min-height: 440px;"></div>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>Blue circles represent operational STPs; orange lines depict dispatched volume to deficit wards (thickness proportional to MLD flow).</span>
          </div>
        </div>

        <!-- Right: Top 25 Wards Supply Source Stack -->
        <div class="card" style="display: flex; flex-direction: column;">
          <div class="card-header">
            <div>
              <h3 class="card-title">Top 25 Deficit Wards Supply Stack</h3>
              <p class="card-subtitle">Breakdown of Tanker Water vs Treated Reuse vs Cauvery</p>
            </div>
            ${createChip('simulated')}
          </div>
          <div class="card-body">
            <div id="opt-stack-chart" style="height: 400px; width: 100%;"></div>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>Treated water replaces expensive private tankers up to the statutory 35% non-potable ward demand ceiling.</span>
          </div>
        </div>
      </div>

      <!-- Secondary Row: STP Utilization Table & Robustness Evaluation Card -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px;">
        <!-- STP Utilization Table -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">Dispatched STP Utilization Table</h3>
              <p class="card-subtitle">Operational capacity vs active routed secondary flow</p>
            </div>
            ${createChip('real')}
          </div>
          <div class="card-body" style="padding: 0; max-height: 360px; overflow-y: auto;">
            <table class="data-table" id="stp-util-table">
              <thead>
                <tr>
                  <th>Treatment Plant</th>
                  <th class="num">Capacity</th>
                  <th class="num">Routed Flow</th>
                  <th style="width: 35%;">Utilization</th>
                </tr>
              </thead>
              <tbody id="stp-util-tbody">
                <tr><td colspan="4" style="text-align: center; color: var(--text-3); padding: 24px;">Loading STP dispatches...</td></tr>
              </tbody>
            </table>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>39 real municipal STPs mapped to official BBMP wards; only plants with demand within 20km are opened to minimize trucking emissions.</span>
          </div>
        </div>

        <!-- Robustness Planning Card -->
        <div class="card" style="border-left: 4px solid var(--accent);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Robustness Benchmark: Point vs Conformal Upper Bound</h3>
              <p class="card-subtitle">30-day out-of-sample stress test evaluation</p>
            </div>
            ${createChip('derived')}
          </div>
          <div class="card-body" style="font-size: 13px; color: var(--text-2); line-height: 1.6;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
              <div style="background: var(--surface-2); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-3); font-weight: 600;">Point Forecast Planning</div>
                <div style="font-family: var(--font-mono); font-size: 20px; font-weight: 600; color: var(--red); margin: 4px 0;">33.50 MLD</div>
                <div style="font-size: 11.5px; color: var(--text-3);">Mean realized unmet shortage during summer heatwaves</div>
              </div>
              <div style="background: var(--accent-soft); padding: 12px; border-radius: var(--radius-sm); border: 1px solid rgba(193, 95, 60, 0.2);">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--accent-ink); font-weight: 600;">Conformal Upper Planning</div>
                <div style="font-family: var(--font-mono); font-size: 20px; font-weight: 600; color: var(--accent-ink); margin: 4px 0;">4.60 MLD</div>
                <div style="font-size: 11.5px; color: var(--accent-ink);">86.3% reduction in realized civic water deficits</div>
              </div>
            </div>
            <p style="margin: 0;">
              <strong style="color: var(--text);">Key Policy Takeaway:</strong> Point forecasts underestimate thermal demand surges, leaving peripheral wards vulnerable to emergency shortages. Sizing municipal treated water dispatch against the 90% conformal safety upper bound eliminates 86% of civic shortages at an incremental cost of just ₹0.02 per kiloliter.
            </p>
          </div>
        </div>
      </div>
    </div>
  `;

  // Initialize Map
  const isDark = appState.theme === 'dark';
  const mapObj = initLeafletMap('opt-map-canvas', isDark);
  if (!mapObj) return;
  const { map } = mapObj;
  optMapInstance = map;
  flowLinesGroup = L.layerGroup().addTo(map);

  let wardsGeo = null;
  let stpsGeo = null;

  try {
    [wardsGeo, stpsGeo] = await Promise.all([
      fetchApi('/api/geo/wards'),
      fetchApi('/api/geo/stps')
    ]);

    // Add STPs to Map
    createStpsLayer(stpsGeo).addTo(map);

    // Initial solve / load preset
    await executeOptimization();

  } catch (err) {
    console.error('Error loading optimizer base data:', err);
  }

  // Sliders and controls listeners
  const gwSlider = document.getElementById('slider-gw');
  const tankerSlider = document.getElementById('slider-tanker');
  const stpSlider = document.getElementById('slider-stp');

  gwSlider.addEventListener('input', (e) => {
    currentGw = parseInt(e.target.value, 10) / 100.0;
    document.getElementById('label-gw-val').innerText = `${e.target.value}%`;
  });

  tankerSlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value, 10);
    currentTanker = val / 12000.0;
    document.getElementById('label-tanker-val').innerText = `₹${val.toLocaleString()} / 12kL`;
  });

  stpSlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value, 10);
    currentStp = val / 1000.0;
    document.getElementById('label-stp-val').innerText = `₹${(val / 1000).toFixed(3)} / L`;
  });

  // Strategy segmented toggle
  const useBtns = document.querySelectorAll('#opt-use-control .segmented-btn');
  useBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      useBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentUse = btn.getAttribute('data-use');
      executeOptimization();
    });
  });

  // Preset Buttons
  const presetBtns = document.querySelectorAll('.preset-btn');
  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      presetBtns.forEach(b => b.classList.remove('active', 'btn-primary'));
      presetBtns.forEach(b => b.classList.add('btn-ghost'));
      btn.classList.add('active', 'btn-primary');
      btn.classList.remove('btn-ghost');

      const pType = btn.getAttribute('data-preset');
      if (pType === 'normal') {
        gwSlider.value = 60; currentGw = 0.6;
        tankerSlider.value = 1300; currentTanker = 0.108333;
        stpSlider.value = 80; currentStp = 0.08;
      } else if (pType === 'summer') {
        gwSlider.value = 40; currentGw = 0.4;
        tankerSlider.value = 1680; currentTanker = 0.14;
        stpSlider.value = 80; currentStp = 0.08;
      } else if (pType === 'drought') {
        gwSlider.value = 20; currentGw = 0.2;
        tankerSlider.value = 2160; currentTanker = 0.18;
        stpSlider.value = 80; currentStp = 0.08;
      }
      document.getElementById('label-gw-val').innerText = `${gwSlider.value}%`;
      document.getElementById('label-tanker-val').innerText = `₹${parseInt(tankerSlider.value, 10).toLocaleString()} / 12kL`;
      document.getElementById('label-stp-val').innerText = `₹${(parseInt(stpSlider.value, 10) / 1000).toFixed(3)} / L`;

      executeOptimization();
    });
  });

  document.getElementById('btn-run-opt').addEventListener('click', () => {
    executeOptimization();
  });

  // Solve & Render Results
  async function executeOptimization() {
    const runBtn = document.getElementById('btn-run-opt');
    runBtn.innerText = 'Solving HiGHS MILP...';
    runBtn.disabled = true;

    if (activeAbortController) {
      activeAbortController.abort();
    }
    activeAbortController = new AbortController();

    try {
      const payload = {
        date: currentDate,
        gw_factor: currentGw,
        tanker_price: currentTanker,
        stp_price: currentStp,
        use: currentUse
      };

      const res = await fetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: activeAbortController.signal
      }).then(r => r.json());

      const k = res.kpis || {};
      const t = getThemeTokens();

      // Update KPI Cards
      const kpiContainer = document.getElementById('opt-kpi-grid');
      kpiContainer.innerHTML = `
        ${createKpiCard({ label: 'Optimized Daily Cost', value: `₹${(k.optimized_daily_cost_inr / 1e6).toFixed(2)}M`, unit: '', sub: 'Includes reuse transport & tanker fills' })}
        ${createKpiCard({ label: 'All-Tanker Baseline', value: `₹${(k.all_tanker_cost_inr / 1e6).toFixed(2)}M`, unit: '', sub: 'Cost if deficit met only by private tankers' })}
        ${createKpiCard({ label: 'Daily Public Saving', value: `₹${(k.saving_inr / 1e6).toFixed(2)}M`, unit: '', sub: `${k.saving_pct.toFixed(1)}% fiscal savings for wards` })}
        ${createKpiCard({ label: 'Tanker Fills Avoided', value: (k.tanker_mld_avoided || 0).toFixed(1), unit: 'MLD', sub: `${Math.round((k.tanker_mld_avoided || 0) * 1e6 / 12000).toLocaleString()} truck trips eliminated` })}
      `;

      document.getElementById('opt-solve-meta').innerText = `Solved in ${(res.solve_seconds || 0).toFixed(3)}s with ${k.plants_opened_count} active STPs`;

      // Draw Flow Lines on Leaflet
      flowLinesGroup.clearLayers();
      const flows = res.flows || [];
      flows.forEach(f => {
        // [lon1, lat1, lon2, lat2, mld]
        const [lon1, lat1, lon2, lat2, mld] = f;
        const weight = Math.max(1.5, Math.min(6, Math.sqrt(mld) * 1.5));
        const line = L.polyline([[lat1, lon1], [lat2, lon2]], {
          color: '#C15F3C',
          weight: weight,
          opacity: 0.75,
          dashArray: '4, 4'
        });
        line.bindTooltip(`${mld.toFixed(2)} MLD Flow`, { sticky: true });
        flowLinesGroup.addLayer(line);
      });

      // Populate STP Utilization Table
      const stpTbody = document.getElementById('stp-util-tbody');
      const stpList = res.stps || [];
      const activeStps = stpList.filter(s => s.used_mld > 0.01).sort((a, b) => b.used_mld - a.used_mld);

      if (activeStps.length === 0) {
        stpTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-3); padding: 18px;">No STPs dispatched under current parameters</td></tr>`;
      } else {
        stpTbody.innerHTML = activeStps.map(s => `
          <tr>
            <td style="font-weight: 500; color: var(--text);">${s.name}</td>
            <td class="num">${s.capacity_mld} MLD</td>
            <td class="num" style="color: var(--accent-ink); font-weight: 600;">${s.used_mld.toFixed(2)} MLD</td>
            <td>${renderInlineBar(s.util_pct, 100)}</td>
          </tr>
        `).join('');
      }

      // Top 25 Deficit Wards Stacked Bar Chart
      const perWard = res.per_ward || {};
      const tMld = perWard.tanker_mld || [];
      const sMld = perWard.stp_mld || [];
      const uMld = perWard.unmet_mld || [];

      // Sort by total deficit
      const wardIndices = Array.from({ length: 225 }, (_, i) => i);
      wardIndices.sort((a, b) => ((tMld[b] || 0) + (sMld[b] || 0) + (uMld[b] || 0)) - ((tMld[a] || 0) + (sMld[a] || 0) + (uMld[a] || 0)));
      const top25 = wardIndices.slice(0, 25);

      const xLabels = top25.map(i => `W${i + 1}`);
      const tankerVals = top25.map(i => tMld[i] || 0);
      const stpVals = top25.map(i => sMld[i] || 0);
      const unmetVals = top25.map(i => uMld[i] || 0);

      const stackTraces = [
        {
          x: xLabels,
          y: stpVals,
          name: 'Treated STP Reuse',
          type: 'bar',
          marker: { color: t.accent }
        },
        {
          x: xLabels,
          y: tankerVals,
          name: 'Private Tanker Water',
          type: 'bar',
          marker: { color: t.blue }
        },
        {
          x: xLabels,
          y: unmetVals,
          name: 'Unmet Deficit',
          type: 'bar',
          marker: { color: t.red || '#B3402F' }
        }
      ];

      renderChart('opt-stack-chart', stackTraces, {
        barmode: 'stack',
        title: { text: '' },
        xaxis: { title: { text: 'Top 25 Deficit Wards' } },
        yaxis: { title: { text: 'Supply Mix (MLD)' } }
      });

    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Optimization error:', err);
      }
    } finally {
      runBtn.innerText = 'Solve MILP Dispatch →';
      runBtn.disabled = false;
    }
  }
}


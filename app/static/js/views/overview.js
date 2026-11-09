// Overview View for HydroGrid 2.0
import { fetchApi } from '../api.js';
import { createCard, createKpiCard, createChip } from '../ui.js';
import { renderChart, getThemeTokens } from '../charts.js';

export async function renderOverview(container) {
  container.innerHTML = `<div style="padding: 40px 0; text-align: center; color: var(--text-2);">Loading civic overview & briefing...</div>`;
  
  try {
    const [overview, briefing] = await Promise.all([
      fetchApi('/api/overview'),
      fetchApi('/api/briefing?date=2024-06-15')
    ]);

    const t = overview.totals;
    const anch = overview.real_anchors;

    container.innerHTML = `
      <div class="overview-view">
        <!-- Editorial Hero -->
        <div style="margin-bottom: 32px;">
          <div style="font-size: 11px; font-feature-settings: 'c2sc', 'smcp'; text-transform: uppercase; letter-spacing: 0.8px; color: var(--accent); font-weight: 600; margin-bottom: 6px;">
            Municipal Water Informatics • Bengaluru 2024
          </div>
          <h1 style="font-family: var(--font-serif); font-size: 26px; font-weight: 400; line-height: 1.35; color: var(--text); max-width: 920px;">
            Bengaluru is short about ${t.supply_gap_mld} MLD of its ${t.total_demand_mld.toLocaleString()} MLD daily demand. 
            HydroGrid forecasts localized deficits, bounds uncertainty with statistical guarantees, and prescriptive dispatches treated wastewater reuse to close the gap.
          </h1>
        </div>

        <!-- KPI Grid -->
        <div class="kpi-grid" data-tour="kpi-grid">
          ${createKpiCard({ label: 'City Daily Demand', value: t.total_demand_mld.toLocaleString(), unit: 'MLD', sub: `225 BBMP Wards (${t.total_population.toLocaleString()} pop)` })}
          ${createKpiCard({ label: 'Cauvery Piped Supply', value: t.cauvery_mld.toLocaleString(), unit: 'MLD', sub: `${((t.cauvery_mld / t.total_demand_mld) * 100).toFixed(1)}% of baseline demand` })}
          ${createKpiCard({ label: 'Groundwater Reliance', value: t.groundwater_reliance_pct, unit: '%', sub: `${anch.borewell_count.toLocaleString()} indexed public borewells` })}
          ${createKpiCard({ label: 'Wastewater Generated', value: t.wastewater_mld.toLocaleString(), unit: 'MLD', sub: `39 STPs (${t.stp_reuse_capacity_mld} MLD reuse cap)` })}
        </div>

        <!-- Today's Briefing Card -->
        <div class="briefing-card" data-tour="briefing-card">
          <div class="briefing-header">
            <h2 class="briefing-title">Operations Briefing: ${briefing.date}</h2>
            <div style="display: flex; gap: 8px;">
              ${createChip('derived')}
              <span class="chip ${briefing.drift_status === 'nominal' ? 'chip-real' : 'chip-sim'}">${briefing.drift_status === 'nominal' ? 'Nominal Regime' : 'Drift Alert Active'}</span>
            </div>
          </div>
          <div class="briefing-list">
            ${briefing.sentences.map(s => `
              <div class="briefing-item">
                <div class="briefing-bullet"></div>
                <div>${s}</div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Real vs Simulated Distinction Strip -->
        <div style="display: flex; align-items: center; justify-content: space-between; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 12px 18px; margin-bottom: 28px;">
          <div style="font-size: 13px; color: var(--text-2);">
            <strong style="color: var(--text);">Methodological Transparency:</strong> 225 ward geometries, pipeline mains, and STPs are authentic civic data; demand time series and failure onsets are mathematically simulated.
          </div>
          <a href="#/methods" class="btn btn-ghost" style="padding: 4px 10px; font-size: 12px;">Inspect Provenance →</a>
        </div>

        <!-- Charts Grid: 1. Annual Rainfall (IMD 1901-2024), 2. Tanker Price Trend -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr)); gap: 20px; margin-bottom: 28px;">
          <div id="card-rain-box"></div>
          <div id="card-tanker-box"></div>
        </div>

        <!-- End-to-End Pipeline Architecture Diagram -->
        <div class="card" style="margin-bottom: 28px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">End-to-End AI Engineering Architecture</h3>
              <p class="card-subtitle">From civic GIS and meteorological anchors to verifiable prescriptive dispatch</p>
            </div>
            ${createChip('derived')}
          </div>
          <div style="padding: 12px 0; overflow-x: auto;">
            <svg viewBox="0 0 960 90" style="width: 100%; min-width: 800px; height: auto; font-family: var(--font-sans); font-size: 12px;">
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 8 5 L 0 9 z" fill="var(--text-3)"/>
                </marker>
              </defs>
              <!-- Node 1 -->
              <rect x="10" y="20" width="95" height="50" rx="4" fill="var(--surface-2)" stroke="var(--border)" stroke-width="1"/>
              <text x="57" y="42" text-anchor="middle" font-weight="600" fill="var(--text)">01. Anchors</text>
              <text x="57" y="58" text-anchor="middle" font-size="10" fill="var(--text-3)">IMD / KMLs</text>
              <line x1="105" y1="45" x2="125" y2="45" stroke="var(--text-3)" stroke-width="1.5" marker-end="url(#arrow)"/>

              <!-- Node 2 -->
              <rect x="130" y="20" width="95" height="50" rx="4" fill="var(--surface-2)" stroke="var(--border)" stroke-width="1"/>
              <text x="177" y="42" text-anchor="middle" font-weight="600" fill="var(--text)">02. Topology</text>
              <text x="177" y="58" text-anchor="middle" font-size="10" fill="var(--text-3)">225 Wards / Graph</text>
              <line x1="225" y1="45" x2="245" y2="45" stroke="var(--text-3)" stroke-width="1.5" marker-end="url(#arrow)"/>

              <!-- Node 3 -->
              <rect x="250" y="20" width="95" height="50" rx="4" fill="var(--surface-2)" stroke="var(--border)" stroke-width="1"/>
              <text x="297" y="42" text-anchor="middle" font-weight="600" fill="var(--text)">03. Forecaster</text>
              <text x="297" y="58" text-anchor="middle" font-size="10" fill="var(--text-3)">HGB (0.451 MAE)</text>
              <line x1="345" y1="45" x2="365" y2="45" stroke="var(--text-3)" stroke-width="1.5" marker-end="url(#arrow)"/>

              <!-- Node 4 -->
              <rect x="370" y="20" width="105" height="50" rx="4" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="1"/>
              <text x="422" y="42" text-anchor="middle" font-weight="600" fill="var(--accent-ink)">04. Conformal</text>
              <text x="422" y="58" text-anchor="middle" font-size="10" fill="var(--accent-ink)">89.1% ACI Bound</text>
              <line x1="475" y1="45" x2="495" y2="45" stroke="var(--text-3)" stroke-width="1.5" marker-end="url(#arrow)"/>

              <!-- Node 5 -->
              <rect x="500" y="20" width="95" height="50" rx="4" fill="var(--surface-2)" stroke="var(--border)" stroke-width="1"/>
              <text x="547" y="42" text-anchor="middle" font-weight="600" fill="var(--text)">05. GAT Alert</text>
              <text x="547" y="58" text-anchor="middle" font-size="10" fill="var(--text-3)">PR-AUC 0.110</text>
              <line x1="595" y1="45" x2="615" y2="45" stroke="var(--text-3)" stroke-width="1.5" marker-end="url(#arrow)"/>

              <!-- Node 6 -->
              <rect x="620" y="20" width="100" height="50" rx="4" fill="var(--surface-2)" stroke="var(--border)" stroke-width="1"/>
              <text x="670" y="42" text-anchor="middle" font-weight="600" fill="var(--text)">06. MILP Route</text>
              <text x="670" y="58" text-anchor="middle" font-size="10" fill="var(--text-3)">39 Real STPs</text>
              <line x1="720" y1="45" x2="740" y2="45" stroke="var(--text-3)" stroke-width="1.5" marker-end="url(#arrow)"/>

              <!-- Node 7 -->
              <rect x="745" y="20" width="95" height="50" rx="4" fill="var(--surface-2)" stroke="var(--border)" stroke-width="1"/>
              <text x="792" y="42" text-anchor="middle" font-weight="600" fill="var(--text)">07. Recourse</text>
              <text x="792" y="58" text-anchor="middle" font-size="10" fill="var(--text-3)">100% Feasibility</text>
              <line x1="840" y1="45" x2="860" y2="45" stroke="var(--text-3)" stroke-width="1.5" marker-end="url(#arrow)"/>

              <!-- Node 8 -->
              <rect x="865" y="20" width="85" height="50" rx="4" fill="var(--surface-2)" stroke="var(--border)" stroke-width="1"/>
              <text x="907" y="42" text-anchor="middle" font-weight="600" fill="var(--text)">08. Drift</text>
              <text x="907" y="58" text-anchor="middle" font-size="10" fill="var(--text-3)">Wasserstein</text>
            </svg>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>Nine-stage pipeline coupling statistical learning with mathematical optimization and distribution drift safeguards.</span>
          </div>
        </div>
      </div>
    `;

    // Render Rainfall Chart
    const rainData = anch.annual_rainfall_series || {};
    const years = Object.keys(rainData).map(Number).sort((a,b)=>a-b);
    const rainVals = years.map(y => rainData[y]);
    
    // 10-year rolling average
    const roll10 = [];
    for (let i = 0; i < years.length; i++) {
      const slice = rainVals.slice(Math.max(0, i - 9), i + 1);
      roll10.push(slice.reduce((a,b)=>a+b, 0) / slice.length);
    }

    const rainHtml = `<div id="plotly-rain" style="height: 280px;"></div>`;
    document.getElementById('card-rain-box').innerHTML = createCard({
      title: 'Historical Precipitation Series (1900–2024)',
      subtitle: 'IMD Station Annual Precipitation & 10-Year Moving Average',
      provenance: 'real',
      bodyHtml: rainHtml,
      captionText: 'Precipitation drives seasonal groundwater recharge and baseline reservoir replenishment.'
    });

    const tok = getThemeTokens();
    renderChart('plotly-rain', [
      {
        x: years,
        y: rainVals,
        type: 'bar',
        name: 'Annual Rainfall (mm)',
        marker: { color: tok.isDark ? '#2E4B65' : '#D0E3F0' }
      },
      {
        x: years,
        y: roll10,
        type: 'scatter',
        mode: 'lines',
        name: '10-Yr Rolling Mean',
        line: { color: tok.blue, width: 2 }
      }
    ], {
      yaxis: { title: { text: 'Rainfall (mm)' } },
      xaxis: { title: { text: 'Year' } }
    });

    // Render Tanker Survey Chart
    const tankerData = anch.tanker_medians || {};
    const surveyYears = Object.keys(tankerData).sort();
    const surveyMedians = surveyYears.map(y => tankerData[y].median);
    const surveyRatesPerL = surveyMedians.map(m => (m / 12000).toFixed(4));

    const tankerHtml = `<div id="plotly-tanker" style="height: 280px;"></div>`;
    document.getElementById('card-tanker-box').innerHTML = createCard({
      title: 'Private Water Tanker Market Inflation',
      subtitle: 'Citizen Survey Medians (2015, 2019, 2024; 12,000L loads)',
      provenance: 'real',
      bodyHtml: tankerHtml,
      captionText: 'Commercial tanker prices surged from ₹500 in 2015 to ₹1,300+ in the 2024 scarcity peak.'
    });

    renderChart('plotly-tanker', [
      {
        x: surveyYears.map(y => `Survey ${y}`),
        y: surveyMedians,
        type: 'bar',
        name: 'Median Tanker Cost (INR / 12kL)',
        marker: { color: tok.accent }
      }
    ], {
      yaxis: { title: { text: 'Cost (INR per 12,000L)' } }
    });

  } catch (err) {
    container.innerHTML = `<div style="padding: 30px; color: #C93B2B;">Failed to load overview: ${err.message}</div>`;
  }
}


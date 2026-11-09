// Methods & Provenance View for HydroGrid 2.0
import { fetchApi } from '../api.js';
import { createCard, createChip } from '../ui.js';

export async function renderMethods(container) {
  container.innerHTML = `<div style="padding: 40px 0; text-align: center; color: var(--text-2);">Loading civic provenance and methodology...</div>`;

  try {
    const [methodsData, v1compare] = await Promise.all([
      fetchApi('/api/methods'),
      fetchApi('/api/v1compare')
    ]);

    const provTable = methodsData.provenance_table || [];
    const steps = methodsData.pipeline_steps || [];
    const limitations = methodsData.honest_limitations || [];
    const v1metrics = v1compare.metrics || [];

    container.innerHTML = `
      <div class="methods-view" style="max-width: var(--maxw); margin: 0 auto;">
        <!-- Editorial Header -->
        <div style="margin-bottom: 28px;">
          <div style="font-size: 11px; font-feature-settings: 'c2sc', 'smcp'; text-transform: uppercase; letter-spacing: 0.8px; color: var(--accent); font-weight: 600; margin-bottom: 6px;">
            Scientific Audit & Civic Data Integrity
          </div>
          <h1 style="font-family: var(--font-serif); font-size: 26px; font-weight: 400; line-height: 1.3; color: var(--text); margin-bottom: 8px;">
            Methodology, Provenance & Honest Limitations
          </h1>
          <p style="font-size: 15px; color: var(--text-2); max-width: 860px; line-height: 1.55;">
            HydroGrid combines authentic municipal GIS boundaries, meteorological observations, and physical trunk mains with mathematically simulated demand time series. 
            Every model, metric, and data layer carries an explicit provenance disclosure.
          </p>
        </div>

        <!-- 1. What Changed from v1 -->
        <div class="card" style="margin-bottom: 24px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">Version 1 vs Version 2 Architectural Progression</h3>
              <p class="card-subtitle">${v1compare.note || 'Key architectural shifts from synthetic prototype to official civic delimitation.'}</p>
            </div>
            ${createChip('derived')}
          </div>
          <div class="card-body" style="padding: 0; overflow-x: auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 28%;">Civic Dimension / Metric</th>
                  <th style="width: 34%;">v1 Prototype (Synthetic Baseline)</th>
                  <th style="width: 38%;">v2 HydroGrid (Authentic Civic Data)</th>
                </tr>
              </thead>
              <tbody>
                ${v1metrics.map(m => `
                  <tr>
                    <td style="font-weight: 500; color: var(--text);">${m.metric}</td>
                    <td style="color: var(--text-2); font-family: monospace; font-size: 12.5px;">${m.v1}</td>
                    <td style="color: var(--accent-ink); font-weight: 500; font-family: monospace; font-size: 12.5px;">${m.v2}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>v1 and v2 use distinct administrative graphs (198 vs 225 wards); metrics represent structural advances.</span>
          </div>
        </div>

        <!-- 2. Provenance Inventory Table -->
        <div class="card" style="margin-bottom: 24px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">Civic Dataset Inventory & Provenance</h3>
              <p class="card-subtitle">Official sources, delimitation boundaries, and integration mechanics</p>
            </div>
            ${createChip('real')}
          </div>
          <div class="card-body" style="padding: 0; overflow-x: auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 22%;">Component</th>
                  <th style="width: 38%;">Source File / Dataset Authority</th>
                  <th style="width: 14%;">Classification</th>
                  <th style="width: 26%;">Description & Processing</th>
                </tr>
              </thead>
              <tbody>
                ${provTable.map(p => `
                  <tr>
                    <td style="font-weight: 500; color: var(--text);">${p.component.replace(/_/g, ' ')}</td>
                    <td style="font-family: monospace; font-size: 11.5px; color: var(--text-2); word-break: break-all;">${p.chosen_file}</td>
                    <td>${createChip(p.status)}</td>
                    <td style="font-size: 12.5px; color: var(--text-2);">${p.note}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>Green indicates official civic ground truth; Blue indicates derived graph topology; Amber indicates calibrated simulation models.</span>
          </div>
        </div>

        <!-- 3. Pipeline Architecture Steps -->
        <div class="card" style="margin-bottom: 24px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">End-to-End Pipeline Execution Sequence</h3>
              <p class="card-subtitle">Algorithmic stages from raw GIS ingests to MILP prescriptive dispatch</p>
            </div>
            ${createChip('derived')}
          </div>
          <div class="card-body">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;">
              ${steps.map(s => `
                <div style="background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px 16px;">
                  <div style="font-weight: 600; font-size: 13.5px; color: var(--text); margin-bottom: 6px; display: flex; align-items: center; justify-content: space-between;">
                    <span>${s.step}</span>
                  </div>
                  <div style="font-size: 12.5px; color: var(--text-2); line-height: 1.5;">${s.desc}</div>
                </div>
              `).join('')}
            </div>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>All modules run sequentially in under 4 minutes on standard CPU via \`python src/run_all.py\`.</span>
          </div>
        </div>

        <!-- 4. Honest Limitations & Scientific Integrity -->
        <div class="card" style="margin-bottom: 24px; border-left: 4px solid var(--accent);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Methodological Limitations & Honesty Disclosures</h3>
              <p class="card-subtitle">Transparent appraisal of boundaries between civic reality and engineering approximations</p>
            </div>
            ${createChip('assumption')}
          </div>
          <div class="card-body">
            <div style="display: flex; flex-direction: column; gap: 12px;">
              ${limitations.map(lim => `
                <div style="display: flex; align-items: flex-start; gap: 10px; font-size: 13.5px; line-height: 1.55; color: var(--text-2);">
                  <span style="color: var(--accent); font-weight: 700; font-size: 16px; line-height: 1.2;">•</span>
                  <span>${lim}</span>
                </div>
              `).join('')}
            </div>
          </div>
          <div class="card-caption">
            <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>Simulation ensures stress testing of rare drought regimes that historical metering records cannot capture.</span>
          </div>
        </div>

        <!-- 5. Replication Guide -->
        <div class="card" style="margin-bottom: 24px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">Replication & Local Verification</h3>
              <p class="card-subtitle">Running the end-to-end pipeline from source data</p>
            </div>
            ${createChip('derived')}
          </div>
          <div class="card-body">
            <pre style="background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px; font-family: monospace; font-size: 12.5px; overflow-x: auto; color: var(--text); margin-bottom: 12px;">
# 1. Activate Python 3.12 environment
.\\venv312\\Scripts\\activate

# 2. Execute full ingestion, modeling & MILP cache pipeline
python src/run_all.py

# 3. Launch editorial FastAPI server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000</pre>
            <p style="font-size: 13px; color: var(--text-2); margin: 0;">
              Unit tests and endpoint validation are verified via <code style="font-family: monospace;">python src/u5_test_api.py</code>.
            </p>
          </div>
        </div>

      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="card" style="padding: 24px; color: var(--red);">Failed to load methods & provenance: ${err.message}</div>`;
  }
}


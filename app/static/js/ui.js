// UI Component Generators for HydroGrid 2.0

export function createChip(type) {
  const norm = (type || 'real').toLowerCase();
  let label = 'Real data';
  let cls = 'chip-real';
  if (norm.includes('sim')) {
    label = 'Simulated';
    cls = 'chip-sim';
  } else if (norm.includes('deriv')) {
    label = 'Derived';
    cls = 'chip-derived';
  } else if (norm.includes('assump')) {
    label = 'Assumption';
    cls = 'chip-assumption';
  }
  return `<span class="chip ${cls}">${label}</span>`;
}

export function createCard({ title, subtitle = '', provenance = 'real', bodyHtml = '', captionText = '' }) {
  const chipHtml = provenance ? createChip(provenance) : '';
  const captionHtml = captionText ? `
    <div class="card-caption">
      <svg class="info-icon" style="width: 14px; height: 14px; min-width: 14px; flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
      <span>${captionText}</span>
    </div>
  ` : '';

  return `
    <div class="card">
      <div class="card-header">
        <div class="card-title-group">
          <div>
            <h3 class="card-title">${title}</h3>
            ${subtitle ? `<p class="card-subtitle">${subtitle}</p>` : ''}
          </div>
        </div>
        ${chipHtml}
      </div>
      <div class="card-body">
        ${bodyHtml}
      </div>
      ${captionHtml}
    </div>
  `;
}

export function createKpiCard({ label, value, unit = '', sub = '' }) {
  return `
    <div class="kpi-card">
      <div class="kpi-label">${label}</div>
      <div class="kpi-val">${value}${unit ? `<small>${unit}</small>` : ''}</div>
      ${sub ? `<div class="kpi-sub">${sub}</div>` : ''}
    </div>
  `;
}

export function renderInlineBar(value, max = 100) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return `
    <div class="cell-bar-container">
      <span style="min-width: 32px; font-variant-numeric: tabular-nums;">${value.toFixed(1)}%</span>
      <div class="cell-bar">
        <div class="cell-bar-fill" style="width: ${pct}%;"></div>
      </div>
    </div>
  `;
}

export function showToast(message, duration = 3000) {
  let toast = document.getElementById('app-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'app-toast';
    document.body.appendChild(toast);
  }
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; background: var(--text);
    color: var(--bg); padding: 10px 18px; border-radius: var(--radius-md);
    font-size: 13px; font-weight: 500; z-index: 1000000; box-shadow: var(--shadow-3);
    transition: opacity 200ms ease, transform 200ms ease; opacity: 0; pointer-events: none;
    transform: translateY(8px);
  `;
  toast.innerText = message;
  // Trigger paint
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
  }, duration);
}

// Plain-English Definitions for Jargon
const DEFINITIONS = {
  'mld': 'Million Litres per Day (1 MLD = 1,000,000 litres).',
  'pr-auc': 'Precision-Recall Area Under Curve: evaluates detection of rare failure cascades where raw accuracy is misleading.',
  'roc-auc': 'Receiver Operating Characteristic Area Under Curve: overall ranking power across decision thresholds.',
  'conformal bound': 'Statistical upper bound guaranteeing 90% real-world supply coverage without normality assumptions.',
  'drift alarm': 'Wasserstein distance alarm flagging when weather or demand shifts away from training distributions.',
  'cascade risk': 'Probability that severe supply deficit here propagates across trunk pipes to neighboring wards.'
};

export function createTooltip(termKey, customLabel = null) {
  const key = termKey.toLowerCase().trim();
  const def = DEFINITIONS[key] || 'Domain technical definition';
  const label = customLabel || termKey;
  return `
    <span class="tooltip-wrap">
      <span>${label}</span>
      <span class="info-tip-btn" aria-label="Explanation of ${label}" tabindex="0">ⓘ
        <span class="tooltip-bubble" role="tooltip">${def}</span>
      </span>
    </span>
  `;
}

export function downloadCsv(filename, rows) {
  if (!rows || !rows.length) {
    showToast('No data available to export');
    return;
  }
  const headers = Object.keys(rows[0]);
  const csvContent = [
    headers.join(','),
    ...rows.map(row => headers.map(h => {
      let val = row[h];
      if (val === null || val === undefined) val = '';
      val = String(val).replace(/"/g, '""');
      return val.includes(',') || val.includes('\n') ? `"${val}"` : val;
    }).join(','))
  ].join('\r\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`Exported ${filename}`);
}


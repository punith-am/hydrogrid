// Command Palette (Ctrl+K / /) for HydroGrid
import { fetchApi } from './api.js';

const SYSTEM_COMMANDS = [
  { type: 'view', title: 'Executive Overview', desc: 'Macro intelligence & operations briefing', route: '#/overview', key: '1' },
  { type: 'view', title: 'City Map', desc: 'Geospatial delimitation, STPs & trunk mains', route: '#/map', key: '2' },
  { type: 'view', title: 'Demand Forecast', desc: 'Adaptive Conformal 90% confidence bands', route: '#/forecast', key: '3' },
  { type: 'view', title: 'Cascade Risk', desc: 'Graph Attention Network early warning', route: '#/risk', key: '4' },
  { type: 'view', title: 'Resource Optimizer', desc: 'HiGHS MILP prescriptive reuse dispatch', route: '#/optimizer', key: '5' },
  { type: 'view', title: 'Counterfactual Recourse', desc: 'Actionable DiCE remediation plans', route: '#/recourse', key: '6' },
  { type: 'view', title: 'Model Health', desc: 'Wasserstein drift & continual learning', route: '#/health', key: '7' },
  { type: 'view', title: 'Methods & Provenance', desc: 'Civic dataset inventory & honesty statement', route: '#/methods', key: '8' },
  { type: 'action', title: 'Toggle Theme', desc: 'Switch between light and dark editorial theme', action: 'theme' },
  { type: 'action', title: 'Start Guided Tour', desc: '9-step narrated evaluator walkthrough', action: 'tour' }
];

let paletteModal = null;
let selectedIdx = 0;
let currentItems = [];
let searchDebounce = null;

export function initCommandPalette(appState) {
  // Global Shortcut
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName))) {
      e.preventDefault();
      openPalette();
    }
  });
}

function openPalette() {
  if (!paletteModal) {
    createPaletteUI();
  }
  paletteModal.style.display = 'flex';
  const input = document.getElementById('palette-input');
  input.value = '';
  input.focus();
  renderItems(SYSTEM_COMMANDS);
}

function closePalette() {
  if (paletteModal) {
    paletteModal.style.display = 'none';
  }
}

function createPaletteUI() {
  paletteModal = document.createElement('div');
  paletteModal.id = 'command-palette-modal';
  paletteModal.style.cssText = `
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(2px);
    z-index: 200000;
    display: none;
    align-items: flex-start;
    justify-content: center;
    padding-top: 14vh;
  `;

  paletteModal.innerHTML = `
    <div style="width: min(580px, calc(100vw - 32px)); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: 0 16px 40px rgba(0,0,0,0.28); overflow: hidden; animation: popIn 140ms ease;">
      <!-- Search Input Bar -->
      <div style="display: flex; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--border-subtle); gap: 10px;">
        <svg style="width: 18px; height: 18px; color: var(--text-3);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input id="palette-input" type="text" placeholder="Jump to view or search ward (e.g. Bellanduru, Optimizer)..." style="flex: 1; border: none; background: none; outline: none; font-size: 14px; color: var(--text); font-family: var(--font-sans);" autocomplete="off">
        <span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-3); background: var(--surface-2); padding: 2px 6px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">ESC</span>
      </div>

      <!-- Results List -->
      <div id="palette-results" style="max-height: 340px; overflow-y: auto; padding: 8px;"></div>

      <!-- Footer Info -->
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: var(--surface-2); border-top: 1px solid var(--border-subtle); font-size: 11.5px; color: var(--text-3);">
        <span>↑↓ to navigate • ↵ to select</span>
        <span>HydroGrid Command Center</span>
      </div>
    </div>
  `;

  document.body.appendChild(paletteModal);

  // Click outside to close
  paletteModal.addEventListener('click', (e) => {
    if (e.target === paletteModal) closePalette();
  });

  const input = document.getElementById('palette-input');

  // Keyboard navigation
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePalette();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIdx = (selectedIdx + 1) % currentItems.length;
      updateActiveVisual();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIdx = (selectedIdx - 1 + currentItems.length) % currentItems.length;
      updateActiveVisual();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (currentItems[selectedIdx]) {
        executeItem(currentItems[selectedIdx]);
      }
    }
  });

  // Input filter
  input.addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    clearTimeout(searchDebounce);

    if (q.length === 0) {
      renderItems(SYSTEM_COMMANDS);
      return;
    }

    const filteredSystem = SYSTEM_COMMANDS.filter(cmd => 
      cmd.title.toLowerCase().includes(q) || cmd.desc.toLowerCase().includes(q)
    );

    renderItems(filteredSystem);

    searchDebounce = setTimeout(async () => {
      try {
        const wards = await fetchApi(`/api/search?q=${encodeURIComponent(q)}`);
        const wardItems = wards.map(w => ({
          type: 'ward',
          title: `#${w.ward_id + 1} ${w.ward_name}`,
          desc: `${w.zone} Zone • ${w.population.toLocaleString()} pop • ${w.base_mld.toFixed(1)} MLD`,
          ward_id: w.ward_id
        }));
        renderItems([...filteredSystem, ...wardItems]);
      } catch (err) {
        console.error(err);
      }
    }, 150);
  });
}

function renderItems(items) {
  currentItems = items;
  selectedIdx = 0;
  const container = document.getElementById('palette-results');
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-3); font-size: 13px;">No commands or wards found</div>`;
    return;
  }

  container.innerHTML = items.map((it, idx) => `
    <div class="palette-item ${idx === 0 ? 'active' : ''}" data-idx="${idx}" style="padding: 10px 12px; border-radius: var(--radius-sm); cursor: pointer; display: flex; align-items: center; justify-content: space-between; transition: background 120ms ease;">
      <div>
        <div style="font-weight: 500; font-size: 13.5px; color: var(--text);">${it.title}</div>
        <div style="font-size: 11.5px; color: var(--text-2);">${it.desc}</div>
      </div>
      ${it.key ? `<span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-3); background: var(--surface-2); padding: 1px 5px; border-radius: 3px; border: 1px solid var(--border-subtle);">${it.key}</span>` : ''}
    </div>
  `).join('');

  container.querySelectorAll('.palette-item').forEach(el => {
    el.addEventListener('mouseenter', () => {
      selectedIdx = parseInt(el.getAttribute('data-idx'), 10);
      updateActiveVisual();
    });
    el.addEventListener('click', () => {
      executeItem(currentItems[selectedIdx]);
    });
  });

  updateActiveVisual();
}

function updateActiveVisual() {
  const container = document.getElementById('palette-results');
  if (!container) return;
  const items = container.querySelectorAll('.palette-item');
  items.forEach((it, idx) => {
    if (idx === selectedIdx) {
      it.style.background = 'var(--surface-2)';
      it.style.borderLeft = '3px solid var(--accent)';
    } else {
      it.style.background = 'transparent';
      it.style.borderLeft = '3px solid transparent';
    }
  });
}

function executeItem(item) {
  closePalette();
  if (item.type === 'view') {
    window.location.hash = item.route;
  } else if (item.type === 'ward') {
    window.location.hash = `#/forecast?ward=${item.ward_id}&h=1`;
  } else if (item.type === 'action') {
    if (item.action === 'theme') {
      const toggleBtn = document.getElementById('theme-toggle-btn');
      if (toggleBtn) toggleBtn.click();
    } else if (item.action === 'tour') {
      const tourBtn = document.getElementById('btn-start-tour');
      if (tourBtn) tourBtn.click();
    }
  }
}


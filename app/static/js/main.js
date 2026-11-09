// Main Application Controller & Router for HydroGrid
import { fetchApi } from './api.js';
import { showToast } from './ui.js';
import { renderOverview } from './views/overview.js';
import { renderMethods } from './views/methods.js';
import { initCommandPalette } from './palette.js';
import { initTour, startTour } from './tour.js';

// Global Application State
export const AppState = {
  currentRoute: 'overview',
  date: '2024-06-15',
  selectedWardId: 168,
  horizon: 1,
  theme: 'light',
  routeParams: {}
};

// Route View Registry
export const ROUTES = {
  overview: {
    title: 'Executive Briefing & Macro Intelligence',
    subtag: 'Macro Overview',
    render: (c) => renderOverview(c)
  },
  map: {
    title: 'Civic Infrastructure & Spatial Layers',
    subtag: 'Geospatial Grid',
    render: async (c) => {
      try {
        const mod = await import('./views/map.js');
        await mod.renderMap(c, AppState);
      } catch (err) {
        console.error('Error rendering map:', err);
        renderPlaceholder(c, 'Civic Infrastructure & Spatial Layers', 'Interactive Leaflet canvas, 225 ward geometries, STPs, and trunk mains.');
      }
    }
  },
  forecast: {
    title: 'Demand Forecasting & Conformal Bands',
    subtag: 'Uncertainty Bounds',
    render: async (c) => {
      try {
        const mod = await import('./views/forecast.js');
        await mod.renderForecast(c, AppState);
      } catch (err) {
        console.error('Error rendering forecast:', err);
        renderPlaceholder(c, 'Demand Forecasting & Conformal Bands', 'HistGradientBoosting vs STGCN with 90% Adaptive Conformal Inference coverage.');
      }
    }
  },
  risk: {
    title: 'GAT Cascading Failure Early Warning',
    subtag: 'Cascade Risk',
    render: async (c) => {
      try {
        const mod = await import('./views/risk.js');
        await mod.renderRisk(c, AppState);
      } catch (err) {
        console.error('Error rendering risk:', err);
        renderPlaceholder(c, 'GAT Cascading Failure Early Warning', '2-layer Graph Attention Network with Focal Loss.');
      }
    }
  },
  optimizer: {
    title: 'MILP Prescriptive Reuse Dispatch',
    subtag: 'Resource Optimizer',
    render: async (c) => {
      try {
        const mod = await import('./views/optimizer.js');
        await mod.renderOptimizer(c, AppState);
      } catch (err) {
        console.error('Error rendering optimizer:', err);
        renderPlaceholder(c, 'MILP Prescriptive Reuse Dispatch', 'Multi-period HiGHS MILP dispatch across 39 operational STPs.');
      }
    }
  },
  recourse: {
    title: 'Actionable Counterfactual Recourse',
    subtag: 'DiCE Recourse',
    render: async (c) => {
      try {
        const mod = await import('./views/recourse.js');
        await mod.renderRecourse(c, AppState);
      } catch (err) {
        console.error('Error rendering recourse:', err);
        renderPlaceholder(c, 'Actionable Counterfactual Recourse', 'Counterfactual interventions under conformal safety constraints.');
      }
    }
  },
  health: {
    title: 'Model Health & Drift Detection',
    subtag: 'Drift & Retraining',
    render: async (c) => {
      try {
        const mod = await import('./views/health.js');
        await mod.renderHealth(c, AppState);
      } catch (err) {
        console.error('Error rendering health:', err);
        renderPlaceholder(c, 'Model Health & Drift Detection', '1D Wasserstein distance monitoring and continual learning benchmarking.');
      }
    }
  },
  methods: {
    title: 'Civic Provenance, Methodology & Honesty',
    subtag: 'Scientific Audit',
    render: (c) => renderMethods(c)
  }
};

const ROUTE_KEYS = ['overview', 'map', 'forecast', 'risk', 'optimizer', 'recourse', 'health', 'methods'];

function renderPlaceholder(container, title, description) {
  container.innerHTML = `
    <div style="max-width: 720px; margin: 40px auto; text-align: center;">
      <div class="card" style="padding: 40px 32px;">
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--accent); font-weight: 600; margin-bottom: 8px;">
          Modular View Ready
        </div>
        <h2 style="font-family: var(--font-serif); font-size: 22px; color: var(--text); margin-bottom: 12px;">${title}</h2>
        <p style="font-size: 14px; color: var(--text-2); line-height: 1.55; margin-bottom: 24px;">
          ${description}
        </p>
        <div style="display: inline-flex; gap: 10px;">
          <a href="#/overview" class="btn btn-primary" style="font-size: 13px;">View Executive Overview</a>
          <a href="#/methods" class="btn btn-secondary" style="font-size: 13px;">Inspect Provenance</a>
        </div>
      </div>
    </div>
  `;
}

// Router & Hash Parsing
function parseHash() {
  const hash = window.location.hash.slice(1) || '/overview';
  const [routePart, queryPart] = hash.split('?');
  const route = (routePart.replace(/^\//, '') || 'overview').toLowerCase();
  
  const params = {};
  if (queryPart) {
    new URLSearchParams(queryPart).forEach((val, key) => {
      params[key] = val;
    });
  }
  return { route: ROUTES[route] ? route : 'overview', params };
}

export async function navigate() {
  const { route, params } = parseHash();
  AppState.currentRoute = route;
  AppState.routeParams = params;
  if (params.ward) AppState.selectedWardId = parseInt(params.ward, 10);
  if (params.h) AppState.horizon = parseInt(params.h, 10);
  if (params.date) AppState.date = params.date;

  // Update Navigation Active State
  document.querySelectorAll('.nav-item').forEach(el => {
    const r = el.getAttribute('data-route');
    if (r === route) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });

  // Update Header
  const routeMeta = ROUTES[route];
  const titleEl = document.getElementById('header-view-title');
  const subtagEl = document.getElementById('header-view-subtag');
  if (titleEl) titleEl.innerText = routeMeta.title;
  if (subtagEl) subtagEl.innerText = routeMeta.subtag;
  document.title = `${routeMeta.title} | HydroGrid`;

  // Update Presentation Bar Label if active
  const presentLabel = document.getElementById('present-view-label');
  if (presentLabel) {
    const idx = ROUTE_KEYS.indexOf(route) + 1;
    presentLabel.innerText = `${routeMeta.title} (${idx}/${ROUTE_KEYS.length})`;
  }

  // Render View
  const container = document.getElementById('view-content');
  if (container) {
    container.innerHTML = '';
    await routeMeta.render(container);
  }
}

// ----------------- Theme Mode Dropdown (White / Dark / System) -----------------
const THEME_ICONS = {
  light: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="5"></circle>
    <line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
    <line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
  </svg>`,
  dark: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
  </svg>`,
  system: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
    <line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line>
  </svg>`
};

const THEME_LABELS = {
  light: 'White',
  dark: 'Dark',
  system: 'System'
};

function initTheme() {
  const saved = localStorage.getItem('hydrogrid-theme') || 'light';
  applyThemeMode(saved, false);

  const themeBtn = document.getElementById('theme-menu-btn');
  const themeDropdown = document.getElementById('theme-dropdown');

  if (themeBtn && themeDropdown) {
    themeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      document.getElementById('help-dropdown')?.classList.remove('show', 'open');
      themeDropdown.classList.toggle('show');
      themeDropdown.classList.toggle('open');
    });

    themeDropdown.querySelectorAll('.theme-dropdown-item').forEach(item => {
      item.addEventListener('click', () => {
        const mode = item.getAttribute('data-theme-val');
        if (mode) {
          applyThemeMode(mode, true);
          themeDropdown.classList.remove('show', 'open');
        }
      });
    });

    document.addEventListener('click', (e) => {
      if (!themeDropdown.contains(e.target) && e.target !== themeBtn) {
        themeDropdown.classList.remove('show', 'open');
      }
    });
  }

  // Listen to OS theme changes if on system
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    const currentMode = localStorage.getItem('hydrogrid-theme') || 'light';
    if (currentMode === 'system') {
      applyThemeMode('system', true);
    }
  });
}

function applyThemeMode(mode, triggerRender = true) {
  localStorage.setItem('hydrogrid-theme', mode);
  
  let resolvedTheme = mode;
  if (mode === 'system') {
    resolvedTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  AppState.theme = resolvedTheme;
  document.documentElement.setAttribute('data-theme', resolvedTheme);
  document.documentElement.setAttribute('data-color-scheme', mode);

  // Update button icon & label
  const iconEl = document.getElementById('theme-current-icon');
  const labelEl = document.getElementById('theme-current-label');
  if (iconEl && THEME_ICONS[mode]) {
    iconEl.innerHTML = THEME_ICONS[mode];
  }
  if (labelEl && THEME_LABELS[mode]) {
    labelEl.innerText = THEME_LABELS[mode];
  }

  // Update active indicator in dropdown
  document.querySelectorAll('.theme-dropdown-item').forEach(el => {
    if (el.getAttribute('data-theme-val') === mode) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });

  if (triggerRender) {
    navigate();
  }
}

function cycleTheme() {
  const current = localStorage.getItem('hydrogrid-theme') || 'light';
  const order = ['light', 'dark', 'system'];
  const next = order[(order.indexOf(current) + 1) % order.length];
  applyThemeMode(next, true);
  showToast(`Theme: ${THEME_LABELS[next]}`);
}

// ----------------- Sidebar Collapse -----------------
function initSidebarCollapse() {
  const collapseBtn = document.getElementById('sidebar-collapse-btn');
  const appRoot = document.getElementById('app-root');
  
  const saved = localStorage.getItem('hydrogrid_sidebar_collapsed');
  if (saved === 'true') {
    appRoot?.classList.add('sidebar-collapsed');
  }

  if (collapseBtn) {
    collapseBtn.addEventListener('click', () => {
      const isCollapsed = appRoot?.classList.toggle('sidebar-collapsed');
      localStorage.setItem('hydrogrid_sidebar_collapsed', isCollapsed ? 'true' : 'false');
    });
  }

  // Mobile menu toggle
  const mobileBtn = document.getElementById('mobile-menu-btn');
  const sidebar = document.getElementById('app-sidebar');
  if (mobileBtn && sidebar) {
    mobileBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }
}

// ----------------- Help Menu & Modals -----------------
function initHelpAndModals() {
  const helpBtn = document.getElementById('help-menu-btn');
  const helpDropdown = document.getElementById('help-dropdown');
  const shortcutsModal = document.getElementById('shortcuts-modal');
  const aboutModal = document.getElementById('about-modal');

  // Toggle Help Dropdown
  if (helpBtn && helpDropdown) {
    helpBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      document.getElementById('theme-dropdown')?.classList.remove('show', 'open');
      helpDropdown.classList.toggle('show');
      helpDropdown.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (!helpDropdown.contains(e.target) && e.target !== helpBtn) {
        helpDropdown.classList.remove('show', 'open');
      }
    });
  }

  // Help menu actions
  const itemTour = document.getElementById('menu-item-tour');
  if (itemTour) {
    itemTour.addEventListener('click', () => {
      helpDropdown?.classList.remove('show', 'open');
      startTour(AppState);
    });
  }

  const itemShortcuts = document.getElementById('menu-item-shortcuts');
  if (itemShortcuts) {
    itemShortcuts.addEventListener('click', () => {
      helpDropdown?.classList.remove('show', 'open');
      openModal(shortcutsModal);
    });
  }

  const itemAbout = document.getElementById('menu-item-about');
  if (itemAbout) {
    itemAbout.addEventListener('click', () => {
      helpDropdown?.classList.remove('show', 'open');
      openModal(aboutModal);
    });
  }

  // Modal close buttons
  document.getElementById('shortcuts-close-btn')?.addEventListener('click', () => closeModal(shortcutsModal));
  document.getElementById('about-close-btn')?.addEventListener('click', () => closeModal(aboutModal));

  [shortcutsModal, aboutModal].forEach(modal => {
    modal?.addEventListener('click', (e) => {
      if (e.target === modal) closeModal(modal);
    });
  });
}

function openModal(modal) {
  if (modal) modal.style.display = 'flex';
}

function closeModal(modal) {
  if (modal) modal.style.display = 'none';
}

// ----------------- Presentation Mode -----------------
function initPresentMode() {
  const startBtn = document.getElementById('btn-start-present');
  const exitBtn = document.getElementById('present-btn-exit');
  const prevBtn = document.getElementById('present-btn-prev');
  const nextBtn = document.getElementById('present-btn-next');

  function enterPresent() {
    document.body.classList.add('present-mode');
    const label = document.getElementById('present-view-label');
    if (label) {
      const idx = ROUTE_KEYS.indexOf(AppState.currentRoute) + 1;
      const meta = ROUTES[AppState.currentRoute] || ROUTES.overview;
      label.innerText = `${meta.title} (${idx}/${ROUTE_KEYS.length})`;
    }
    showToast('Presentation mode active. Press Esc to exit.');
  }

  function exitPresent() {
    document.body.classList.remove('present-mode');
  }

  function nextView() {
    const idx = ROUTE_KEYS.indexOf(AppState.currentRoute);
    const nextIdx = (idx + 1) % ROUTE_KEYS.length;
    window.location.hash = `#/${ROUTE_KEYS[nextIdx]}`;
  }

  function prevView() {
    const idx = ROUTE_KEYS.indexOf(AppState.currentRoute);
    const prevIdx = (idx - 1 + ROUTE_KEYS.length) % ROUTE_KEYS.length;
    window.location.hash = `#/${ROUTE_KEYS[prevIdx]}`;
  }

  if (startBtn) startBtn.addEventListener('click', enterPresent);
  if (exitBtn) exitBtn.addEventListener('click', exitPresent);
  if (prevBtn) prevBtn.addEventListener('click', prevView);
  if (nextBtn) nextBtn.addEventListener('click', nextView);

  window.togglePresentMode = () => {
    if (document.body.classList.contains('present-mode')) {
      exitPresent();
    } else {
      enterPresent();
    }
  };
}

// ----------------- Date Selector -----------------
function initDateControls() {
  const dateInput = document.getElementById('header-date-input');
  const prevBtn = document.getElementById('btn-date-prev');
  const nextBtn = document.getElementById('btn-date-next');

  if (dateInput) {
    dateInput.value = AppState.date;
    dateInput.addEventListener('change', (e) => {
      AppState.date = e.target.value;
      navigate();
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      const d = new Date(AppState.date);
      d.setDate(d.getDate() - 1);
      const iso = d.toISOString().split('T')[0];
      if (iso >= '2024-01-01') {
        AppState.date = iso;
        if (dateInput) dateInput.value = iso;
        navigate();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      const d = new Date(AppState.date);
      d.setDate(d.getDate() + 1);
      const iso = d.toISOString().split('T')[0];
      if (iso <= '2024-12-31') {
        AppState.date = iso;
        if (dateInput) dateInput.value = iso;
        navigate();
      }
    });
  }
}

// ----------------- Ward Combobox & Global Keyboard Shortcuts -----------------
function initSearchAndShortcuts() {
  const searchInput = document.getElementById('header-ward-search');
  const searchResults = document.getElementById('header-search-results');
  let searchTimeout = null;

  if (searchInput && searchResults) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const q = e.target.value.trim();
      if (q.length === 0) {
        searchResults.style.display = 'none';
        return;
      }
      searchTimeout = setTimeout(async () => {
        try {
          const results = await fetchApi(`/api/search?q=${encodeURIComponent(q)}`);
          if (results.length === 0) {
            searchResults.innerHTML = `<div style="padding: 10px 14px; font-size: 12.5px; color: var(--text-3);">No matching wards</div>`;
          } else {
            searchResults.innerHTML = results.map(w => `
              <div class="search-result-item" data-ward="${w.ward_id}" style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
                <div>
                  <strong style="color: var(--text); font-size: 13px;">#${w.ward_id + 1} ${w.ward_name}</strong>
                  <div style="font-size: 11.5px; color: var(--text-2);">${w.zone} Zone • ${w.population.toLocaleString()} pop</div>
                </div>
                <span style="font-family: var(--font-mono); font-size: 11.5px; color: var(--accent);">${w.base_mld.toFixed(1)} MLD</span>
              </div>
            `).join('');
          }
          searchResults.style.display = 'block';

          searchResults.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
              const wid = item.getAttribute('data-ward');
              AppState.selectedWardId = parseInt(wid, 10);
              searchResults.style.display = 'none';
              searchInput.value = '';
              window.location.hash = `#/forecast?ward=${wid}&h=1`;
            });
          });
        } catch (err) {
          console.error('Search error:', err);
        }
      }, 200);
    });

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.style.display = 'none';
      }
    });
  }

  // Two-key chord state ('G' followed by letter)
  let gPressed = false;
  let gTimeout = null;

  document.addEventListener('keydown', (e) => {
    const isTyping = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName);

    if (e.key === 'Escape') {
      if (document.activeElement) document.activeElement.blur();
      if (searchResults) searchResults.style.display = 'none';
      closeModal(document.getElementById('shortcuts-modal'));
      closeModal(document.getElementById('about-modal'));
      document.getElementById('help-dropdown')?.classList.remove('show', 'open');
      document.getElementById('theme-dropdown')?.classList.remove('show', 'open');
      if (document.body.classList.contains('present-mode')) {
        document.body.classList.remove('present-mode');
      }
      return;
    }

    if (isTyping) return;

    // '?' opens shortcuts modal
    if (e.key === '?') {
      e.preventDefault();
      const modal = document.getElementById('shortcuts-modal');
      if (modal.style.display === 'flex') closeModal(modal);
      else openModal(modal);
      return;
    }

    // '/' or Ctrl+K focuses ward search
    if (e.key === '/' || (e.ctrlKey && e.key === 'k')) {
      e.preventDefault();
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
      return;
    }

    // 'T' cycles theme
    if (e.key === 't' || e.key === 'T') {
      if (!gPressed) {
        e.preventDefault();
        cycleTheme();
        return;
      }
    }

    // 'D' focuses date selector
    if (e.key === 'd' || e.key === 'D') {
      if (!gPressed) {
        e.preventDefault();
        const dateInput = document.getElementById('header-date-input');
        if (dateInput) {
          dateInput.focus();
          if (typeof dateInput.showPicker === 'function') dateInput.showPicker();
        }
        return;
      }
    }

    // 'P' toggles presentation mode
    if ((e.key === 'p' || e.key === 'P') && !gPressed) {
      e.preventDefault();
      window.togglePresentMode();
      return;
    }

    // Chord navigation: 'G' then route key
    if (e.key === 'g' || e.key === 'G') {
      gPressed = true;
      clearTimeout(gTimeout);
      gTimeout = setTimeout(() => { gPressed = false; }, 1200);
      return;
    }

    if (gPressed) {
      gPressed = false;
      clearTimeout(gTimeout);
      const chordMap = {
        o: 'overview',
        m: 'map',
        f: 'forecast',
        r: 'risk',
        p: 'optimizer',
        c: 'recourse',
        h: 'health',
        t: 'methods'
      };
      const target = chordMap[e.key.toLowerCase()];
      if (target) {
        e.preventDefault();
        window.location.hash = `#/${target}`;
        return;
      }
    }

    // Fallback 1-8 navigation
    if (e.key >= '1' && e.key <= '8') {
      const idx = parseInt(e.key, 10) - 1;
      if (ROUTE_KEYS[idx]) {
        window.location.hash = `#/${ROUTE_KEYS[idx]}`;
      }
    }
  });

  // Copy Link Button with robust fallback and visual feedback
  const copyBtn = document.getElementById('btn-copy-link');
  const copyIconSpan = document.getElementById('copy-btn-icon');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      const shareUrl = window.location.href;
      let copied = false;

      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(shareUrl);
          copied = true;
        } catch (e) {
          // Fallback below
        }
      }

      if (!copied) {
        try {
          const ta = document.createElement('textarea');
          ta.value = shareUrl;
          ta.style.position = 'fixed';
          ta.style.left = '-9999px';
          ta.style.top = '-9999px';
          ta.setAttribute('readonly', '');
          document.body.appendChild(ta);
          ta.select();
          copied = document.execCommand('copy');
          document.body.removeChild(ta);
        } catch (err) {
          console.error('Fallback copy error:', err);
        }
      }

      // Visual feedback: green checkmark on button
      if (copyIconSpan) {
        const originalSvg = copyIconSpan.innerHTML;
        copyIconSpan.innerHTML = `
          <svg style="width: 14px; height: 14px; color: var(--green);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        `;
        setTimeout(() => {
          copyIconSpan.innerHTML = originalSvg;
        }, 2000);
      }

      showToast('Link copied to clipboard!');
    });
  }
}

// ----------------- Initial Boot -----------------
window.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initSidebarCollapse();
  initHelpAndModals();
  initPresentMode();
  initDateControls();
  initSearchAndShortcuts();
  initCommandPalette(AppState);

  // Health check to ensure backend is accessible
  try {
    await fetchApi('/api/health');
    const banner = document.getElementById('offline-banner');
    if (banner) banner.style.display = 'none';
  } catch (err) {
    console.warn('Backend /api/health check failed:', err);
    const banner = document.getElementById('offline-banner');
    if (banner) banner.style.display = 'block';
  }

  // Listen to hash changes
  window.addEventListener('hashchange', navigate);
  await navigate();

  // Initialize guided tour
  initTour(AppState);
});

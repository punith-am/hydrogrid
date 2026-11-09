// Map View for HydroGrid 2.0
import { fetchApi } from '../api.js';
import { createChip } from '../ui.js';
import {
  initLeafletMap,
  createWardLayer,
  createTrunkMainsLayer,
  createStpsLayer,
  createBorewellsLayer,
  buildLegendControl
} from '../map.js';

let currentMapInstance = null;
let currentWardLayer = null;
let pipesLayer = null;
let stpsLayer = null;
let borewellsLayer = null;
let playInterval = null;

const LAYERS = {
  demand: { label: 'Forecast Demand', unit: 'MLD', isRisk: false },
  shortfall: { label: 'Supply Shortfall', unit: 'MLD', isRisk: false },
  risk: { label: 'Cascade Risk', unit: '%', isRisk: true },
  stress: { label: 'Groundwater Stress', unit: 'Index', isRisk: false },
  population: { label: 'Population', unit: 'Habitants', isRisk: false }
};

export async function renderMap(container, appState) {
  // Clear any active animation
  if (playInterval) {
    clearInterval(playInterval);
    playInterval = null;
  }

  container.innerHTML = `
    <div class="map-view-wrapper">
      <!-- Toolbar: Layers, Toggles, Playback -->
      <div class="map-toolbar" data-tour="map-controls">
        <div class="map-layer-selector" id="map-layer-selector">
          <span style="font-size: 11px; font-feature-settings: 'c2sc', 'smcp'; text-transform: uppercase; color: var(--text-3); font-weight: 600; margin-right: 4px;">Layer</span>
          <button class="layer-btn active" data-layer="demand">Forecast Demand</button>
          <button class="layer-btn" data-layer="shortfall">Supply Shortfall</button>
          <button class="layer-btn" data-layer="risk">Cascade Risk</button>
          <button class="layer-btn" data-layer="stress">Groundwater Stress</button>
          <button class="layer-btn" data-layer="population">Population</button>
        </div>

        <div class="map-toggles">
          <label class="map-toggle-label">
            <input type="checkbox" id="toggle-pipes" checked>
            <span>Trunk Mains (>300mm)</span>
          </label>
          <label class="map-toggle-label">
            <input type="checkbox" id="toggle-stps" checked>
            <span>STPs (39 Plants)</span>
          </label>
          <label class="map-toggle-label">
            <input type="checkbox" id="toggle-borewells">
            <span>Borewells</span>
          </label>
        </div>
      </div>

      <!-- Map Subtitle & Provenance Disclosure -->
      <div style="display: flex; align-items: center; justify-content: space-between; font-size: 12.5px; color: var(--text-2); padding: 0 4px;">
        <div>
          <strong style="color: var(--text);">Civic Geography:</strong> Ward boundaries, transmission mains, and treatment plants are authentic municipal GIS; daily demand values are <span style="color: var(--amber); font-weight: 500;">SIMULATED</span>.
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <button id="btn-play-map" class="btn btn-ghost" style="padding: 3px 10px; font-size: 12px; gap: 4px;">
            <svg id="play-icon" style="width: 12px; height: 12px;" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            <span id="play-label">Play 2024</span>
          </button>
          <span id="map-date-display" style="font-family: var(--font-mono); font-weight: 500; color: var(--accent-ink);">${appState.date}</span>
        </div>
      </div>

      <!-- Map Canvas & Sliding Detail Drawer -->
      <div class="map-container-rel">
        <div id="map-canvas"></div>

        <!-- Floating Ward Detail Drawer -->
        <div id="map-ward-drawer" class="map-drawer">
          <div class="map-drawer-header">
            <div>
              <div id="drawer-ward-title" class="drawer-title">Ward Name</div>
              <div id="drawer-ward-zone" class="drawer-sub">Zone Information</div>
            </div>
            <button id="drawer-close-btn" class="drawer-close" aria-label="Close drawer">×</button>
          </div>

          <div class="drawer-metric-grid">
            <div class="drawer-metric">
              <div class="drawer-metric-label">Population</div>
              <div id="drawer-pop-val" class="drawer-metric-val">-</div>
            </div>
            <div class="drawer-metric">
              <div class="drawer-metric-label">Base Demand</div>
              <div id="drawer-base-val" class="drawer-metric-val">- MLD</div>
            </div>
            <div class="drawer-metric">
              <div class="drawer-metric-label">Cauvery Cover</div>
              <div id="drawer-cauvery-val" class="drawer-metric-val">-%</div>
            </div>
            <div class="drawer-metric">
              <div class="drawer-metric-label">Indexed Wells</div>
              <div id="drawer-wells-val" class="drawer-metric-val">-</div>
            </div>
          </div>

          <div style="background: var(--surface-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 12px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span id="drawer-layer-label" style="font-size: 11px; text-transform: uppercase; color: var(--text-2); font-weight: 600;">Forecast Demand</span>
              <span id="drawer-layer-val" style="font-family: var(--font-mono); font-size: 15px; font-weight: 600; color: var(--accent-ink);">-</span>
            </div>
            <div id="drawer-layer-sub" style="font-size: 11px; color: var(--text-3);">Target date projection</div>
          </div>

          <div class="drawer-actions">
            <button id="btn-drawer-forecast" class="btn btn-primary" style="flex: 1; justify-content: center; font-size: 12px;">
              Open Forecast →
            </button>
            <button id="btn-drawer-recourse" class="btn btn-ghost" style="flex: 1; justify-content: center; font-size: 12px;">
              Open Recourse →
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  // Initialize Map
  const isDark = appState.theme === 'dark';
  const mapObj = initLeafletMap('map-canvas', isDark);
  if (!mapObj) return;
  const { map } = mapObj;
  currentMapInstance = map;

  let activeLayer = 'demand';
  let wardsGeoData = null;
  let datesList = [];

  // Drawer event listeners
  const drawer = document.getElementById('map-ward-drawer');
  document.getElementById('drawer-close-btn').addEventListener('click', () => {
    drawer.style.display = 'none';
  });

  // Layer selection buttons
  const layerButtons = document.querySelectorAll('.layer-btn');
  layerButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      layerButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const chosen = btn.getAttribute('data-layer');
      updateMapLayer(chosen, appState.date);
    });
  });

  // Toggle Checkbox handlers
  document.getElementById('toggle-pipes').addEventListener('change', (e) => {
    if (pipesLayer) {
      if (e.target.checked) pipesLayer.addTo(map);
      else map.removeLayer(pipesLayer);
    }
  });

  document.getElementById('toggle-stps').addEventListener('change', (e) => {
    if (stpsLayer) {
      if (e.target.checked) stpsLayer.addTo(map);
      else map.removeLayer(stpsLayer);
    }
  });

  document.getElementById('toggle-borewells').addEventListener('change', async (e) => {
    if (e.target.checked) {
      if (!borewellsLayer) {
        try {
          const borewellsGeo = await fetchApi('/api/geo/borewells');
          borewellsLayer = createBorewellsLayer(borewellsGeo);
        } catch (err) {
          console.error('Failed to load borewells:', err);
        }
      }
      if (borewellsLayer) borewellsLayer.addTo(map);
    } else if (borewellsLayer) {
      map.removeLayer(borewellsLayer);
    }
  });

  // Playback loop (600ms/step)
  const playBtn = document.getElementById('btn-play-map');
  const playLabel = document.getElementById('play-label');
  const dateDisplay = document.getElementById('map-date-display');

  if (playBtn) {
    playBtn.addEventListener('click', () => {
      if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
        if (playLabel) playLabel.innerText = 'Play 2024';
      } else {
        if (playLabel) playLabel.innerText = 'Pause';
        let idx = datesList.indexOf(appState.date);
        if (idx < 0) idx = 0;

        playInterval = setInterval(() => {
          idx = (idx + 1) % datesList.length;
          appState.date = datesList[idx];
          if (dateDisplay) dateDisplay.innerText = appState.date;
          const headerDate = document.getElementById('header-date-input');
          if (headerDate) headerDate.value = appState.date;
          updateMapLayer(activeLayer, appState.date);
        }, 600);
      }
    });
  }

  // Update Layer Function
  async function updateMapLayer(layerName, date) {
    activeLayer = layerName;
    if (!wardsGeoData) return;

    try {
      const mapData = await fetchApi(`/api/map?date=${date}&layer=${layerName}`);
      const valuesMap = mapData.values || {};
      const meta = LAYERS[layerName] || LAYERS.demand;

      if (currentWardLayer) {
        map.removeLayer(currentWardLayer);
      }

      const { layer, minVal, maxVal, palette } = createWardLayer(wardsGeoData, valuesMap, {
        isRisk: meta.isRisk,
        onWardClick: (props, val) => {
          appState.selectedWardId = props.ward_id;
          document.getElementById('drawer-ward-title').innerText = `#${props.ward_id + 1} ${props.ward_name}`;
          document.getElementById('drawer-ward-zone').innerText = `${props.zone} Zone`;
          document.getElementById('drawer-pop-val').innerText = (props.population || 0).toLocaleString();
          document.getElementById('drawer-base-val').innerText = `${(props.base_mld || 0).toFixed(1)} MLD`;
          document.getElementById('drawer-cauvery-val').innerText = `${Math.round((props.cauvery_cover || 0) * 100)}%`;
          document.getElementById('drawer-wells-val').innerText = (props.borewell_count || 0).toLocaleString();
          document.getElementById('drawer-layer-label').innerText = meta.label;
          document.getElementById('drawer-layer-val').innerText = `${typeof val === 'number' ? (meta.isRisk ? (val * 100).toFixed(1) : val.toFixed(2)) : val} ${meta.unit}`;
          
          document.getElementById('btn-drawer-forecast').onclick = () => {
            window.location.hash = `#/forecast?ward=${props.ward_id}&h=1`;
          };
          document.getElementById('btn-drawer-recourse').onclick = () => {
            window.location.hash = `#/recourse?ward=${props.ward_id}`;
          };

          drawer.style.display = 'block';
        }
      });

      currentWardLayer = layer.addTo(map);
      buildLegendControl(map, {
        title: meta.label,
        unit: meta.unit,
        min: meta.isRisk ? `${(minVal * 100).toFixed(1)}%` : minVal.toFixed(1),
        max: meta.isRisk ? `${(maxVal * 100).toFixed(1)}%` : maxVal.toFixed(1),
        palette: palette
      });
    } catch (err) {
      console.error(`Failed to update map layer ${layerName}:`, err);
    }
  }

  // Load Dates & Base GeoJSONs
  try {
    const [datesRes, wardsGeo] = await Promise.all([
      fetchApi('/api/dates'),
      fetchApi('/api/geo/wards')
    ]);

    datesList = datesRes.dates || [];
    wardsGeoData = wardsGeo;

    // Load initial layer
    await updateMapLayer(activeLayer, appState.date);

    // If a ward was pre-selected in state, center or highlight
    if (appState.selectedWardId !== undefined) {
      const feat = wardsGeoData.features.find(f => f.properties.ward_id === appState.selectedWardId);
      if (feat && feat.geometry) {
        // Pre-selection handled
      }
    }
  } catch (err) {
    console.error('Failed to load base map data:', err);
  }

  // Load secondary infrastructure layers independently
  try {
    const pipesGeo = await fetchApi('/api/geo/pipes');
    pipesLayer = createTrunkMainsLayer(pipesGeo);
    if (document.getElementById('toggle-pipes')?.checked) {
      pipesLayer.addTo(map);
    }
  } catch (err) {
    console.error('Failed to load trunk mains layer:', err);
  }

  try {
    const stpsGeo = await fetchApi('/api/geo/stps');
    stpsLayer = createStpsLayer(stpsGeo);
    if (document.getElementById('toggle-stps')?.checked) {
      stpsLayer.addTo(map);
    }
  } catch (err) {
    console.error('Failed to load STPs layer:', err);
  }
}


// Leaflet Geospatial Map Helper for HydroGrid 2.0

export const PALETTES = {
  terracotta: ['#FAF5EE', '#F5DFCE', '#EEC7AC', '#E3A987', '#D58661', '#C15F3C', '#8E381A'],
  riskRed: ['#FAF5EE', '#F8D8D3', '#F0AFA4', '#E48171', '#D44F3C', '#B3261E', '#70100A']
};

export function makeBaseLayer() {
  return L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
    className: 'dark-tiles'
  });
}

export function initLeafletMap(containerId, isDark = false) {
  const container = document.getElementById(containerId);
  if (!container) return null;

  // Initialize Leaflet Map centered on Bengaluru
  const map = L.map(containerId, {
    center: [12.9716, 77.5946],
    zoom: 11,
    minZoom: 10,
    maxZoom: 15,
    preferCanvas: true,
    zoomControl: true,
    attributionControl: true
  });

  const tileLayer = makeBaseLayer().addTo(map);

  return { map, tileLayer };
}

export function getColor(val, min, max, palette = PALETTES.terracotta) {
  if (val === null || val === undefined || isNaN(val)) return '#E0DDD5';
  if (max <= min) return palette[3];
  const norm = Math.max(0, Math.min(1, (val - min) / (max - min)));
  const idx = Math.min(palette.length - 1, Math.floor(norm * palette.length));
  return palette[idx];
}

export function buildLegendControl(map, { title, unit, min, max, palette = PALETTES.terracotta }) {
  // Remove existing legend if present
  if (map._hydroLegend) {
    map.removeControl(map._hydroLegend);
    map._hydroLegend = null;
  }

  const legend = L.control({ position: 'bottomleft' });
  legend.onAdd = function () {
    const div = L.DomUtil.create('div', 'leaflet-legend-box');
    div.innerHTML = `
      <div class="legend-title">${title} (${unit})</div>
      <div class="legend-scale-bar">
        ${palette.map(c => `<div class="legend-scale-step" style="background: ${c};"></div>`).join('')}
      </div>
      <div class="legend-labels">
        <span>${typeof min === 'number' ? min.toLocaleString() : min}</span>
        <span>${typeof max === 'number' ? max.toLocaleString() : max}</span>
      </div>
    `;
    return div;
  };
  legend.addTo(map);
  map._hydroLegend = legend;
}

export function createWardLayer(geoData, valuesMap, options = {}) {
  const { isRisk = false, onWardClick, onWardHover, onWardOut } = options;
  const palette = isRisk ? PALETTES.riskRed : PALETTES.terracotta;

  // Calculate min & max
  const vals = Object.values(valuesMap).filter(v => v !== null && !isNaN(v));
  const minVal = vals.length > 0 ? Math.min(...vals) : 0;
  const maxVal = vals.length > 0 ? Math.max(...vals) : 1;

  const layer = L.geoJSON(geoData, {
    style: function (feature) {
      const wid = feature.properties.ward_id;
      const val = valuesMap[wid];
      const fillColor = getColor(val, minVal, maxVal, palette);
      return {
        fillColor: fillColor,
        weight: 1,
        opacity: 0.8,
        color: 'var(--border, #E8E6DC)',
        fillOpacity: 0.82
      };
    },
    onEachFeature: function (feature, l) {
      const p = feature.properties;
      const wid = p.ward_id;
      const val = valuesMap[wid];

      const valStr = typeof val === 'number' ? (isRisk ? `${(val * 100).toFixed(1)}%` : val.toLocaleString()) : '';
      l.bindTooltip(`<div style="font-family: var(--font-sans); font-size: 12px; font-weight: 500;"><strong>#${p.ward_id + 1} ${p.ward_name}</strong>${valStr ? `<div style="font-size: 11px; color: var(--accent); margin-top: 2px;">${isRisk ? 'Cascade Risk: ' : 'Value: '}${valStr}</div>` : ''}</div>`, {
        sticky: true,
        className: 'leaflet-legend-box'
      });

      l.on({
        mouseover: function (e) {
          const target = e.target;
          target.setStyle({
            weight: 2.5,
            color: '#C15F3C',
            fillOpacity: 0.95
          });
          if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
            target.bringToFront();
          }
          if (onWardHover) onWardHover(p, val, e);
        },
        mouseout: function (e) {
          layer.resetStyle(e.target);
          if (onWardOut) onWardOut(e);
        },
        click: function (e) {
          if (onWardClick) onWardClick(p, val, e);
        }
      });
    }
  });

  return { layer, minVal, maxVal, palette };
}

export function createTrunkMainsLayer(pipeGeoData) {
  return L.geoJSON(pipeGeoData, {
    style: {
      color: '#2F7F79',
      weight: 2,
      opacity: 0.85
    },
    onEachFeature: function (feature, layer) {
      const p = feature.properties;
      const dia = p.dia_mm ? `${p.dia_mm}mm` : '>300mm';
      layer.bindTooltip(`Trunk Main: ${dia}`, { sticky: true, className: 'leaflet-legend-box' });
    }
  });
}

export function createStpsLayer(stpGeoData) {
  return L.geoJSON(stpGeoData, {
    pointToLayer: function (feature, latlng) {
      const p = feature.properties;
      const cap = p.capacity_mld || 10;
      const radius = Math.max(5, Math.min(14, Math.sqrt(cap) * 1.8));
      return L.circleMarker(latlng, {
        radius: radius,
        fillColor: '#3B6FB6',
        color: '#FFFFFF',
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.9
      });
    },
    onEachFeature: function (feature, layer) {
      const p = feature.properties;
      const html = `
        <div style="font-family: var(--font-sans); padding: 4px;">
          <strong style="color: var(--text);">${p.name || 'STP Plant'}</strong>
          <div style="font-size: 11.5px; color: var(--text-2); margin-top: 3px;">Capacity: ${p.capacity_mld} MLD</div>
          <div style="font-size: 11.5px; color: var(--accent-ink);">Reuse Cap: ${p.reuse_cap_mld} MLD</div>
          <div style="font-size: 10.5px; color: var(--text-3); margin-top: 2px;">Tech: ${p.technology || 'Biological'}</div>
        </div>
      `;
      layer.bindPopup(html);
    }
  });
}

export function createBorewellsLayer(borewellsGeoData) {
  return L.geoJSON(borewellsGeoData, {
    pointToLayer: function (feature, latlng) {
      return L.circleMarker(latlng, {
        radius: 2,
        fillColor: '#B9770E',
        color: '#B9770E',
        weight: 0.5,
        opacity: 0.6,
        fillOpacity: 0.5
      });
    }
  });
}


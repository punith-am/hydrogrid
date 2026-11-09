// Plotly Layout Factory derived from CSS Tokens

export function getThemeTokens() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    isDark,
    bg: isDark ? '#1C1B1A' : '#FFFFFF',
    plotBg: isDark ? '#1C1B1A' : '#FFFFFF',
    text: isDark ? '#EDECE8' : '#1F1E1D',
    text2: isDark ? '#9C9A94' : '#5E5D59',
    text3: isDark ? '#7A7872' : '#8C8A82',
    grid: isDark ? '#2E2D2A' : '#F0EEE6',
    border: isDark ? '#2E2D2A' : '#E8E6DC',
    accent: isDark ? '#D97757' : '#C15F3C',
    accentSoft: isDark ? 'rgba(217, 119, 87, 0.2)' : 'rgba(193, 95, 60, 0.15)',
    blue: isDark ? '#4FA2E0' : '#235F8E',
    green: isDark ? '#48A76B' : '#2B6E44',
    font: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  };
}

export function createBaseLayout(title = '', xTitle = '', yTitle = '') {
  const t = getThemeTokens();
  return {
    title: {
      text: title,
      font: { family: 'Charter, serif', size: 16, color: t.text },
      x: 0.02,
      y: 0.95
    },
    paper_bgcolor: t.bg,
    plot_bgcolor: t.plotBg,
    font: { family: t.font, size: 12, color: t.text2 },
    margin: { t: title ? 44 : 20, r: 24, b: 40, l: 50 },
    xaxis: {
      title: { text: xTitle, font: { size: 11, color: t.text3 } },
      gridcolor: t.grid,
      zerolinecolor: t.grid,
      tickcolor: t.grid,
      linecolor: t.border
    },
    yaxis: {
      title: { text: yTitle, font: { size: 11, color: t.text3 } },
      gridcolor: t.grid,
      zerolinecolor: t.grid,
      tickcolor: t.grid,
      linecolor: t.border
    },
    legend: {
      orientation: 'h',
      y: -0.18,
      x: 0,
      font: { size: 11, color: t.text2 }
    },
    hovermode: 'x unified',
    autosize: true
  };
}

export function renderChart(elementId, data, customLayout = {}) {
  const base = createBaseLayout(customLayout.title?.text || '', customLayout.xaxis?.title?.text || '', customLayout.yaxis?.title?.text || '');
  const mergedLayout = { ...base, ...customLayout };
  const config = { responsive: true, displayModeBar: false };
  if (window.Plotly) {
    window.Plotly.newPlot(elementId, data, mergedLayout, config);
  }
}

export function downloadChartPng(elementId, filename = 'chart') {
  const el = document.getElementById(elementId);
  if (!el || !window.Plotly) {
    console.warn(`Chart container ${elementId} not found or Plotly not loaded`);
    return;
  }
  const cleanName = filename.replace(/\.png$/i, '');
  window.Plotly.downloadImage(el, {
    format: 'png',
    filename: cleanName,
    width: 1000,
    height: 560
  });
}


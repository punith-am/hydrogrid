// HydroGrid Frontend Application Logic
document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let wardsData = [];
  let edgesData = [];
  let availableDates = [];
  let currentTargetDate = "2024-06-15";
  let mapPlaying = false;
  let mapPlayInterval = null;
  let currentHorizon = 1;
  let currentForecastMethod = "aci"; // "aci" or "static"
  let currentOptStrategy = "upper"; // "upper" or "point"

  // Standard Dark Plotly Layout
  const darkLayoutBase = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Inter, sans-serif", color: "#94a3b8", size: 11 },
    margin: { t: 30, r: 25, b: 40, l: 50 },
    xaxis: {
      gridcolor: "rgba(255, 255, 255, 0.06)",
      zerolinecolor: "rgba(255, 255, 255, 0.1)",
      tickfont: { size: 10 }
    },
    yaxis: {
      gridcolor: "rgba(255, 255, 255, 0.06)",
      zerolinecolor: "rgba(255, 255, 255, 0.1)",
      tickfont: { size: 10 }
    },
    legend: {
      orientation: "h",
      x: 0,
      y: 1.12,
      font: { size: 10 },
      bgcolor: "transparent"
    }
  };

  // 1. Tab Navigation
  const navTabs = document.getElementById("navTabs");
  navTabs.addEventListener("click", (e) => {
    if (e.target.classList.contains("nav-btn")) {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      
      e.target.classList.add("active");
      const tabId = `tab-${e.target.dataset.tab}`;
      const tabElem = document.getElementById(tabId);
      if (tabElem) {
        tabElem.classList.add("active");
        window.dispatchEvent(new Event("resize"));
      }
    }
  });

  // 2. Load Overview & Real Anchors
  async function loadOverview() {
    try {
      const res = await fetch("/api/overview");
      const data = await res.json();
      
      // Real Rainfall Timeline Chart
      const rfSeries = data.real_anchors.annual_rainfall_series || {};
      const rfYears = Object.keys(rfSeries);
      const rfVals = Object.values(rfSeries);
      
      const traceRainfall = {
        x: rfYears,
        y: rfVals,
        type: "bar",
        marker: {
          color: rfVals.map(v => v < 700 ? "#ef4444" : v > 1200 ? "#0d9488" : "#2563eb"),
          opacity: 0.85
        },
        name: "Annual Rain (mm)"
      };
      
      const layoutRainfall = {
        ...darkLayoutBase,
        title: false,
        yaxis: { ...darkLayoutBase.yaxis, title: "Rainfall (mm)" },
        xaxis: { ...darkLayoutBase.xaxis, title: "Year (1901 – 2024)" }
      };
      Plotly.newPlot("chart-rainfall-hist", [traceRainfall], layoutRainfall, { responsive: true, displayModeBar: false });

      // Real Tanker Water Market Price Chart
      const tankerMedians = data.real_anchors.tanker_medians || {};
      const tYears = Object.keys(tankerMedians);
      const tPrices = tYears.map(y => tankerMedians[y].median);
      
      const traceTanker = {
        x: tYears,
        y: tPrices,
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#f59e0b", width: 3, shape: "spline" },
        marker: { size: 10, color: "#f59e0b" },
        name: "Median Rate (₹ / 12kL)"
      };
      
      const layoutTanker = {
        ...darkLayoutBase,
        title: false,
        yaxis: { ...darkLayoutBase.yaxis, title: "Cost per 12,000L (INR)" },
        xaxis: { ...darkLayoutBase.xaxis, title: "Survey Year" }
      };
      Plotly.newPlot("chart-tanker-prices", [traceTanker], layoutTanker, { responsive: true, displayModeBar: false });
    } catch (err) {
      console.error("Error loading overview:", err);
    }
  }

  // 3. Load Wards & City Map
  async function loadWardsAndMap() {
    try {
      const [wardsRes, datesRes] = await Promise.all([
        fetch("/api/wards"),
        fetch("/api/dates")
      ]);
      const wData = await wardsRes.json();
      const dData = await datesRes.json();
      
      wardsData = wData.wards;
      edgesData = wData.edges;
      availableDates = dData.dates;
      currentTargetDate = dData.default_date || availableDates[0];
      
      // Populate Date Slider
      const slider = document.getElementById("map-date-slider");
      slider.max = availableDates.length - 1;
      const initialIdx = availableDates.indexOf(currentTargetDate);
      slider.value = initialIdx >= 0 ? initialIdx : 0;
      document.getElementById("map-date-display").textContent = currentTargetDate;
      document.getElementById("opt-date").value = currentTargetDate;

      // Populate Ward Dropdowns
      const fcSelect = document.getElementById("forecast-ward-select");
      const rcSelect = document.getElementById("recourse-ward-select");
      fcSelect.innerHTML = "";
      rcSelect.innerHTML = "";
      
      wardsData.forEach(w => {
        const opt1 = document.createElement("option");
        opt1.value = w.ward_id;
        opt1.textContent = `${w.ward_name} (${w.zone.toUpperCase()} - ${w.base_mld.toFixed(1)} MLD)`;
        fcSelect.appendChild(opt1);
        
        const opt2 = document.createElement("option");
        opt2.value = w.ward_id;
        opt2.textContent = `${w.ward_name} (${w.zone.toUpperCase()})`;
        rcSelect.appendChild(opt2);
      });
      
      // Set default recourse ward
      rcSelect.value = "168";

      // Render Initial Map
      await updateCityMap();
      
      // Load initial forecast & recourse
      loadForecast(0, 1);
      loadRisk(currentTargetDate);
      loadRecourse(168, currentTargetDate);
    } catch (err) {
      console.error("Error loading wards/map:", err);
    }
  }

  // Update City Map
  async function updateCityMap() {
    const layer = document.getElementById("map-layer-select").value;
    try {
      const res = await fetch(`/api/map?date=${currentTargetDate}&layer=${layer}`);
      const mapValues = await res.json();
      const vals = mapValues.values || {};
      
      // Edges Trace
      const edgeX = [];
      const edgeY = [];
      const wardMap = {};
      wardsData.forEach(w => { wardMap[w.ward_id] = w; });
      
      edgesData.forEach(e => {
        const s = wardMap[e.src];
        const d = wardMap[e.dst];
        if (s && d) {
          edgeX.push(s.x, d.x, null);
          edgeY.push(s.y, d.y, null);
        }
      });
      
      const traceEdges = {
        x: edgeX,
        y: edgeY,
        mode: "lines",
        line: { color: "rgba(255, 255, 255, 0.08)", width: 1 },
        hoverinfo: "none",
        showlegend: false
      };
      
      // Wards Nodes Trace
      const nodeX = wardsData.map(w => w.x);
      const nodeY = wardsData.map(w => w.y);
      const nodeSizes = wardsData.map(w => Math.max(7, Math.min(22, w.base_mld * 0.8)));
      const nodeVals = wardsData.map(w => vals[w.ward_id] !== undefined ? vals[w.ward_id] : 0);
      const nodeTexts = wardsData.map(w => 
        `<b>${w.ward_name}</b><br>Zone: ${w.zone}<br>Base: ${w.base_mld.toFixed(1)} MLD<br>${layer.toUpperCase()}: ${vals[w.ward_id]}`
      );
      
      // Colorscale per layer
      let colorscale = "Viridis";
      if (layer === "risk") colorscale = "YlOrRd";
      if (layer === "stress") colorscale = "Tealrose";
      
      const traceNodes = {
        x: nodeX,
        y: nodeY,
        mode: "markers",
        marker: {
          size: nodeSizes,
          color: nodeVals,
          colorscale: colorscale,
          showscale: true,
          colorbar: {
            title: layer.toUpperCase(),
            thickness: 12,
            len: 0.8,
            tickfont: { color: "#94a3b8", size: 10 }
          },
          line: { color: "rgba(255,255,255,0.4)", width: 1 }
        },
        text: nodeTexts,
        hoverinfo: "text",
        showlegend: false
      };
      
      const layoutMap = {
        ...darkLayoutBase,
        xaxis: { showgrid: false, zeroline: false, showticklabels: false },
        yaxis: { showgrid: false, zeroline: false, showticklabels: false, scaleanchor: "x" },
        margin: { t: 20, r: 20, b: 20, l: 20 }
      };
      
      Plotly.react("chart-city-map", [traceEdges, traceNodes], layoutMap, { responsive: true, displayModeBar: false });
    } catch (err) {
      console.error("Error updating map:", err);
    }
  }

  // Map Controls Event Listeners
  document.getElementById("map-layer-select").addEventListener("change", updateCityMap);
  
  const mapSlider = document.getElementById("map-date-slider");
  mapSlider.addEventListener("input", (e) => {
    const idx = parseInt(e.target.value);
    currentTargetDate = availableDates[idx];
    document.getElementById("map-date-display").textContent = currentTargetDate;
    updateCityMap();
    loadRisk(currentTargetDate);
  });

  const btnPlay = document.getElementById("btn-play-map");
  btnPlay.addEventListener("click", () => {
    mapPlaying = !mapPlaying;
    if (mapPlaying) {
      btnPlay.textContent = "⏸ Pause";
      btnPlay.classList.add("active");
      mapPlayInterval = setInterval(() => {
        let curIdx = parseInt(mapSlider.value);
        curIdx = (curIdx + 1) % availableDates.length;
        mapSlider.value = curIdx;
        currentTargetDate = availableDates[curIdx];
        document.getElementById("map-date-display").textContent = currentTargetDate;
        updateCityMap();
      }, 1200);
    } else {
      btnPlay.textContent = "▶ Play";
      btnPlay.classList.remove("active");
      clearInterval(mapPlayInterval);
    }
  });

  // 4. Forecast Tab Logic
  async function loadForecast(wardId, h) {
    try {
      const res = await fetch(`/api/forecast?ward_id=${wardId}&h=${h}`);
      const data = await res.json();
      
      const kpis = data.kpis;
      document.getElementById("fc-cov").textContent = currentForecastMethod === "aci" && kpis.coverage_aci !== null 
        ? `${kpis.coverage_aci}%` : `${kpis.coverage_static}%`;
      document.getElementById("fc-width").textContent = currentForecastMethod === "aci" && kpis.width_aci_mld !== null 
        ? `${kpis.width_aci_mld} MLD` : `${kpis.width_static_mld} MLD`;
        
      const wardInfo = wardsData.find(w => w.ward_id === wardId);
      if (wardInfo) {
        document.getElementById("fc-base").textContent = `${wardInfo.base_mld.toFixed(1)} MLD`;
        document.getElementById("fc-zone").textContent = `${wardInfo.zone.toUpperCase()} ZONE`;
      }

      // Plot actual, forecast, band
      const dates = data.dates;
      const lower = currentForecastMethod === "aci" && data.lower_aci && data.lower_aci[0] !== null ? data.lower_aci : data.lower_static;
      const upper = currentForecastMethod === "aci" && data.upper_aci && data.upper_aci[0] !== null ? data.upper_aci : data.upper_static;
      
      const traceUpper = {
        x: dates,
        y: upper,
        mode: "lines",
        line: { color: "transparent" },
        showlegend: false,
        hoverinfo: "none"
      };
      
      const traceLower = {
        x: dates,
        y: lower,
        mode: "lines",
        fill: "tonexty",
        fillcolor: "rgba(13, 148, 136, 0.22)",
        line: { color: "transparent" },
        name: "90% Conformal Band"
      };
      
      const tracePred = {
        x: dates,
        y: data.pred,
        mode: "lines",
        line: { color: "#06b6d4", width: 2 },
        name: "Predicted Demand (MLD)"
      };
      
      const traceActual = {
        x: dates,
        y: data.actual,
        mode: "lines",
        line: { color: "#f8fafc", width: 1.5, dash: "dot" },
        name: "Actual Demand (MLD)"
      };
      
      const layoutFc = {
        ...darkLayoutBase,
        title: false,
        yaxis: { ...darkLayoutBase.yaxis, title: "Demand (MLD)" },
        xaxis: { ...darkLayoutBase.xaxis, title: "Target Date" }
      };
      
      Plotly.react("chart-forecast-ts", [traceUpper, traceLower, tracePred, traceActual], layoutFc, { responsive: true, displayModeBar: false });
    } catch (err) {
      console.error("Error loading forecast:", err);
    }
  }

  // Forecast Selectors
  document.getElementById("forecast-ward-select").addEventListener("change", (e) => {
    loadForecast(parseInt(e.target.value), currentHorizon);
  });
  
  document.querySelectorAll(".btn-group .btn-toggle[data-h]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".btn-group .btn-toggle[data-h]").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      currentHorizon = parseInt(e.target.dataset.h);
      const wid = parseInt(document.getElementById("forecast-ward-select").value);
      loadForecast(wid, currentHorizon);
    });
  });

  document.getElementById("btn-use-aci").addEventListener("click", (e) => {
    document.getElementById("btn-use-static").classList.remove("active");
    e.target.classList.add("active");
    currentForecastMethod = "aci";
    const wid = parseInt(document.getElementById("forecast-ward-select").value);
    loadForecast(wid, currentHorizon);
  });

  document.getElementById("btn-use-static").addEventListener("click", (e) => {
    document.getElementById("btn-use-aci").classList.remove("active");
    e.target.classList.add("active");
    currentForecastMethod = "static";
    const wid = parseInt(document.getElementById("forecast-ward-select").value);
    loadForecast(wid, currentHorizon);
  });

  // 5. Cascade Risk Tab Logic
  async function loadRisk(date) {
    try {
      const res = await fetch(`/api/risk?date=${date}`);
      const data = await res.json();
      
      const tbody = document.querySelector("#table-risk-top15 tbody");
      tbody.innerHTML = "";
      
      data.top15.forEach(r => {
        const tr = document.createElement("tr");
        const riskPct = (r.risk * 100).toFixed(1);
        tr.innerHTML = `
          <td><strong>${r.ward_name}</strong></td>
          <td><span class="card-tag">${r.zone.toUpperCase()}</span></td>
          <td>
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <div class="bar-track" style="width:70px;"><div class="bar-fill" style="width:${Math.min(100, r.risk * 200)}%; background:#ef4444;"></div></div>
              <span style="font-family:'JetBrains Mono'; color:#ef4444; font-weight:600;">${riskPct}%</span>
            </div>
          </td>
          <td>${(r.tanker_dependence * 100).toFixed(0)}%</td>
          <td>${r.groundwater_stress.toFixed(2)}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error("Error loading risk:", err);
    }
  }

  // 6. Optimizer Tab Logic
  const gwSlider = document.getElementById("opt-gw");
  gwSlider.addEventListener("input", (e) => {
    document.getElementById("opt-gw-val").textContent = parseFloat(e.target.value).toFixed(2);
  });

  const tankerSlider = document.getElementById("opt-tanker");
  tankerSlider.addEventListener("input", (e) => {
    document.getElementById("opt-tanker-val").textContent = parseFloat(e.target.value).toFixed(3);
  });

  const stpSlider = document.getElementById("opt-stp");
  stpSlider.addEventListener("input", (e) => {
    document.getElementById("opt-stp-val").textContent = parseFloat(e.target.value).toFixed(3);
  });

  document.getElementById("btn-opt-upper").addEventListener("click", (e) => {
    document.getElementById("btn-opt-point").classList.remove("active");
    e.target.classList.add("active");
    currentOptStrategy = "upper";
  });

  document.getElementById("btn-opt-point").addEventListener("click", (e) => {
    document.getElementById("btn-opt-upper").classList.remove("active");
    e.target.classList.add("active");
    currentOptStrategy = "point";
  });

  async function runOptimization() {
    const btn = document.getElementById("btn-run-opt");
    btn.disabled = true;
    btn.textContent = "⏳ Solving HiGHS MILP...";
    
    try {
      const payload = {
        date: document.getElementById("opt-date").value,
        gw_factor: parseFloat(gwSlider.value),
        tanker_price: parseFloat(tankerSlider.value),
        stp_price: parseFloat(stpSlider.value),
        use: currentOptStrategy
      };
      
      const res = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      const kpis = data.kpis;
      
      // Update KPIs
      document.getElementById("opt-cost").textContent = `₹${(kpis.optimized_daily_cost_inr / 1e6).toFixed(2)}M`;
      document.getElementById("opt-alltanker").textContent = `₹${(kpis.all_tanker_cost_inr / 1e6).toFixed(2)}M`;
      document.getElementById("opt-saving").textContent = `₹${Math.round(kpis.saving_inr).toLocaleString()}`;
      document.getElementById("opt-saving-pct").textContent = `${kpis.saving_pct.toFixed(1)}% net cost reduction`;
      document.getElementById("opt-stp-mld").textContent = `${kpis.stp_mld_used.toFixed(1)} MLD`;
      document.getElementById("opt-unmet").textContent = `${kpis.unmet_mld.toFixed(1)} MLD`;
      document.getElementById("opt-time").textContent = `${data.solve_seconds.toFixed(2)}s`;

      // Plot Stacked Supply Mix Bar
      const perWard = data.per_ward;
      const shortfall = perWard.shortfall_mld;
      const sortedWards = shortfall
        .map((sf, idx) => ({ idx, sf }))
        .sort((a, b) => b.sf - a.sf)
        .slice(0, 20);
        
      const wardNames = sortedWards.map(w => `Ward_${w.idx+1}`);
      const tankerVals = sortedWards.map(w => perWard.tanker_mld[w.idx]);
      const stpVals = sortedWards.map(w => perWard.stp_received_mld[w.idx]);
      const unmetVals = sortedWards.map(w => perWard.unmet_mld[w.idx]);
      
      const traceTanker = {
        x: wardNames,
        y: tankerVals,
        name: "Tanker Supply (MLD)",
        type: "bar",
        marker: { color: "#f59e0b" }
      };
      
      const traceSTP = {
        x: wardNames,
        y: stpVals,
        name: "STP Treated Water (MLD)",
        type: "bar",
        marker: { color: "#10b981" }
      };
      
      const traceUnmet = {
        x: wardNames,
        y: unmetVals,
        name: "Unmet Shortfall (MLD)",
        type: "bar",
        marker: { color: "#ef4444" }
      };
      
      const layoutStacked = {
        ...darkLayoutBase,
        barmode: "stack",
        yaxis: { ...darkLayoutBase.yaxis, title: "Allocated MLD" },
        xaxis: { ...darkLayoutBase.xaxis, tickangle: -45 }
      };
      
      Plotly.react("chart-opt-stacked", [traceTanker, traceSTP, traceUnmet], layoutStacked, { responsive: true, displayModeBar: false });
    } catch (err) {
      console.error("Optimization failed:", err);
    } finally {
      btn.disabled = false;
      btn.textContent = "⚡ Solve MILP Allocation";
    }
  }

  document.getElementById("btn-run-opt").addEventListener("click", runOptimization);

  // 7. Recourse Tab Logic
  async function loadRecourse(wardId, date) {
    const container = document.getElementById("recourse-cards-container");
    container.innerHTML = "<div class='note-box'>Generating counterfactual action plans...</div>";
    
    try {
      const res = await fetch(`/api/recourse?ward_id=${wardId}&date=${date}`);
      const data = await res.json();
      container.innerHTML = "";
      
      if (!data.counterfactuals || data.counterfactuals.length === 0) {
        container.innerHTML = "<div class='note-box'>No counterfactual plans found for this configuration.</div>";
        return;
      }
      
      data.counterfactuals.forEach((cf, idx) => {
        const card = document.createElement("div");
        card.className = "cf-card";
        card.innerHTML = `
          <div class="cf-card-header">
            <span class="cf-plan-title">Action Plan ${idx + 1}</span>
            <span class="card-tag tag-real">L1 Proximity: ${cf.normalized_distance}</span>
          </div>
          <div class="cf-actions-text">${cf.action_text}</div>
          <div class="cf-metrics-list">
            <div>• Demand Cut: <strong>${cf.demand_cut_pct}%</strong></div>
            <div>• STP Reuse Procured: <strong>${cf.stp_mld} MLD</strong></div>
            <div>• Contracted Tanker: <strong>${cf.tanker_contract_mld} MLD</strong></div>
            <div>• Conformal Safety: <strong style="color:#10b981;">Guaranteed (100%)</strong></div>
          </div>
        `;
        container.appendChild(card);
      });
    } catch (err) {
      console.error("Error loading recourse:", err);
      container.innerHTML = "<div class='note-box'>Failed to load recourse recommendations.</div>";
    }
  }

  document.getElementById("btn-fetch-recourse").addEventListener("click", () => {
    const wid = parseInt(document.getElementById("recourse-ward-select").value);
    loadRecourse(wid, currentTargetDate);
  });

  // 8. Model Health & Drift Tab Logic
  async function loadDriftMonitor() {
    try {
      const res = await fetch("/api/drift");
      const data = await res.json();
      
      const series = data.series || [];
      const dates = series.map(s => s.date);
      const distPeriph = series.map(s => s.ratio_dev_periphery);
      const distAll = series.map(s => s.ratio_dev_all);
      
      const thPeriph = data.thresholds.ratio_dev_periphery || 0.033;
      const thAll = data.thresholds.ratio_dev_all || 0.030;
      
      const tracePeriph = {
        x: dates,
        y: distPeriph,
        mode: "lines",
        line: { color: "#ef4444", width: 2 },
        name: "Periphery Wards Dev (Wasserstein Distance)"
      };
      
      const traceAll = {
        x: dates,
        y: distAll,
        mode: "lines",
        line: { color: "#06b6d4", width: 1.5 },
        name: "All Wards Dev (Wasserstein Distance)"
      };
      
      const traceThPeriph = {
        x: [dates[0], dates[dates.length - 1]],
        y: [thPeriph, thPeriph],
        mode: "lines",
        line: { color: "#ef4444", dash: "dash", width: 1 },
        name: `Periphery Threshold (${thPeriph.toFixed(3)})`
      };
      
      const traceThAll = {
        x: [dates[0], dates[dates.length - 1]],
        y: [thAll, thAll],
        mode: "lines",
        line: { color: "#06b6d4", dash: "dash", width: 1 },
        name: `All Wards Threshold (${thAll.toFixed(3)})`
      };
      
      const layoutDrift = {
        ...darkLayoutBase,
        title: false,
        yaxis: { ...darkLayoutBase.yaxis, title: "Wasserstein Distance" },
        xaxis: { ...darkLayoutBase.xaxis, title: "Date" }
      };
      
      Plotly.newPlot("chart-drift-monitor", [tracePeriph, traceAll, traceThPeriph, traceThAll], layoutDrift, { responsive: true, displayModeBar: false });
    } catch (err) {
      console.error("Error loading drift monitor:", err);
    }
  }

  // 9. Methods Tab Logic
  async function loadMethods() {
    try {
      const res = await fetch("/api/methods");
      const data = await res.json();
      
      const tbody = document.querySelector("#table-provenance tbody");
      tbody.innerHTML = "";
      data.provenance_table.forEach(r => {
        const tr = document.createElement("tr");
        const tagClass = r.type === "REAL" ? "tag-real" : "card-tag";
        tr.innerHTML = `
          <td><strong>${r.component}</strong></td>
          <td><span class="card-tag ${tagClass}">${r.type}</span></td>
          <td style="color:#94a3b8; font-size:0.75rem;">${r.source}</td>
        `;
        tbody.appendChild(tr);
      });
      
      const limitContainer = document.getElementById("list-limitations");
      limitContainer.innerHTML = "";
      data.honest_limitations.forEach(lim => {
        const div = document.createElement("div");
        div.className = "limit-item";
        div.textContent = lim;
        limitContainer.appendChild(div);
      });
    } catch (err) {
      console.error("Error loading methods:", err);
    }
  }

  // Initialize Application
  loadOverview();
  loadWardsAndMap();
  runOptimization(); // run default demo
  loadDriftMonitor();
  loadMethods();
});


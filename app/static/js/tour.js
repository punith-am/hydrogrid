// HydroGrid Guided Tour (Beginner-Friendly Spotlight Walkthrough)

export const TOUR_STEPS = [
  {
    step: 1,
    route: 'overview',
    target: '.brand',
    title: 'Welcome to HydroGrid',
    text: 'Bengaluru experiences an unmetered structural water gap of 772 MLD (million litres per day). HydroGrid forecasts localized supply shortages and optimizes treated wastewater reuse to close the gap.'
  },
  {
    step: 2,
    route: 'overview',
    target: '[data-tour="nav-menu"]',
    title: 'Sidebar Navigation',
    text: 'Access the 8 core sections of the platform: macro city overview, interactive GIS map, demand forecasts, cascading failure alerts, resource optimization, actionable recourse, and civic data methods.'
  },
  {
    step: 3,
    route: 'overview',
    target: '[data-tour="kpi-grid"]',
    title: 'Citywide Water Balance (KPIs)',
    text: 'Key macro metrics: 2,632 MLD daily baseline demand across 225 wards, 1,860 MLD piped surface water from the Cauvery River, 52% reliance on 7,433 borewells, and 548 MLD in treatment plant capacity.'
  },
  {
    step: 4,
    route: 'overview',
    target: '[data-tour="briefing-card"]',
    title: 'Daily Operations Briefing',
    text: 'A plain-language operational summary for the selected date. The 90% conformal safety bound means actual water demand is statistically guaranteed to stay within this buffer 90% of the time.'
  },
  {
    step: 5,
    route: 'map',
    target: '[data-tour="map-controls"]',
    title: 'Interactive City GIS Map',
    text: 'Explore 225 official ward boundaries with 5 data layers: Demand, Shortfall, Risk, Stress, and Population. Toggle pipeline trunk mains (>300mm), 39 operational treatment plants, and scrub the 2024 calendar with the Play button.'
  },
  {
    step: 6,
    route: 'forecast',
    target: '[data-tour="forecast-chart"]',
    title: 'Demand Forecasting & Safety Bands',
    text: 'Machine learning predicts daily ward demand 1 to 3 days ahead. The shaded envelope shows our 90% safety interval; actual demand falls inside this band even when heatwaves surge consumption.'
  },
  {
    step: 7,
    route: 'risk',
    target: '[data-tour="risk-table"]',
    title: 'Cascading Early Warning',
    text: 'When groundwater in one ward runs dry, private water tankers reroute from neighboring wards, causing secondary shortages. Our Graph Attention Network flags high-risk wards 24 to 48 hours before failures cascade.'
  },
  {
    step: 8,
    route: 'optimizer',
    target: '[data-tour="optimizer-controls"]',
    title: 'Prescriptive Reuse Optimization',
    text: 'Instead of relying entirely on expensive private water tankers, our optimizer routes non-potable secondary treated water from 39 treatment plants to deficit wards, saving up to ₹1.43M daily.'
  },
  {
    step: 9,
    route: 'health',
    target: '[data-tour="drift-chart"]',
    title: 'Model Health & Drift Detection',
    text: 'Monitors the divergence between recent weather patterns and historical training records. If an unusual summer heatwave shifts demand (drift alarm), the system executes a 165ms warm-start update.'
  },
  {
    step: 10,
    route: 'overview',
    target: '[data-tour="data-sources-link"]',
    title: 'Data Sources & Transparency',
    text: 'Transparency commitment: ward polygons, census population, 7,433 borewells, 39 STPs, and pipeline mains are authentic civic data; daily consumption numbers and failure onsets are mathematically simulated for stress testing.'
  },
  {
    step: 11,
    route: 'overview',
    target: '[data-tour="top-toolbar"]',
    title: 'Context Toolbar',
    text: 'Use the top toolbar anytime to search any of the 225 wards (/), change the date context, switch between Light/Dark/System themes, or open the Help menu (?) to replay this tour.'
  }
];

let currentStep = 0;
let isTourActive = false;
let activeHighlightedEl = null;

export function initTour(appState) {
  // Ensure spotlight overlay and card are hidden by default
  const svg = document.getElementById('tour-spotlight-svg');
  if (svg) svg.style.display = 'none';
  const card = document.getElementById('tour-card');
  if (card) card.style.display = 'none';

  // Check if tour should run automatically on first visit or if requested via URL
  const urlParams = new URLSearchParams(window.location.search);
  const hash = window.location.hash;
  const tourRequested = urlParams.get('tour') === '1' || hash.includes('tour=1');
  const alreadyDone = localStorage.getItem('hydrogrid_tour_done') === 'true';

  if (tourRequested || !alreadyDone) {
    // Delay slightly to let initial view render smoothly
    setTimeout(() => {
      startTour();
    }, 600);
  }

  // Keyboard navigation for tour
  document.addEventListener('keydown', (e) => {
    if (!isTourActive) return;
    if (e.key === 'Escape') {
      endTour();
    } else if (e.key === 'ArrowRight' || e.key === 'Enter') {
      e.preventDefault();
      nextTourStep();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      prevTourStep();
    }
  });

  // Reposition on window resize or scroll
  window.addEventListener('resize', handleReposition);
  window.addEventListener('scroll', handleReposition, true);

  // Setup Tour Card Event Listeners
  const closeBtn = document.getElementById('tour-btn-close');
  const nextBtn = document.getElementById('tour-btn-next');
  const prevBtn = document.getElementById('tour-btn-prev');
  const dontShow = document.getElementById('tour-dont-show-checkbox');

  if (closeBtn) closeBtn.onclick = endTour;
  if (nextBtn) nextBtn.onclick = nextTourStep;
  if (prevBtn) prevBtn.onclick = prevTourStep;
  if (dontShow) {
    dontShow.checked = true;
    dontShow.onchange = (e) => {
      if (e.target.checked) {
        localStorage.setItem('hydrogrid_tour_done', 'true');
      } else {
        localStorage.removeItem('hydrogrid_tour_done');
      }
    };
  }
}

export function startTour() {
  currentStep = 0;
  isTourActive = true;
  const svg = document.getElementById('tour-spotlight-svg');
  if (svg) svg.style.display = 'block';
  renderCurrentStep();
}

export function endTour() {
  isTourActive = false;
  // Always remember completion so reload never appears shaded
  localStorage.setItem('hydrogrid_tour_done', 'true');
  const card = document.getElementById('tour-card');
  const svg = document.getElementById('tour-spotlight-svg');
  if (card) card.style.display = 'none';
  if (svg) svg.style.display = 'none';

  if (activeHighlightedEl) {
    activeHighlightedEl.classList.remove('tour-target-highlight');
    activeHighlightedEl = null;
  }
}

function nextTourStep() {
  if (currentStep < TOUR_STEPS.length - 1) {
    currentStep++;
    renderCurrentStep();
  } else {
    localStorage.setItem('hydrogrid_tour_done', 'true');
    endTour();
  }
}

function prevTourStep() {
  if (currentStep > 0) {
    currentStep--;
    renderCurrentStep();
  }
}

async function renderCurrentStep() {
  if (!isTourActive) return;
  const step = TOUR_STEPS[currentStep];

  // Navigate to route if not already there
  const targetHash = `#/${step.route}`;
  const currentHash = window.location.hash.split('?')[0];

  if (currentHash !== targetHash && targetHash !== '#/') {
    window.location.hash = targetHash;
    // Wait for route and view to render
    await new Promise(r => setTimeout(r, 220));
  }

  // Locate target element
  let targetEl = null;
  if (step.target) {
    targetEl = document.querySelector(step.target);
  }

  // Remove previous highlight
  if (activeHighlightedEl) {
    activeHighlightedEl.classList.remove('tour-target-highlight');
    activeHighlightedEl = null;
  }

  // If target element is missing, skip or center
  updateSpotlight(targetEl);
  updateTourCard(step, targetEl);
}

function updateSpotlight(targetEl) {
  const cutout = document.getElementById('spotlight-cutout');
  const svg = document.getElementById('tour-spotlight-svg');
  if (!cutout || !svg) return;

  if (!targetEl) {
    // Hide spotlight cutout (full darken)
    cutout.setAttribute('x', '0');
    cutout.setAttribute('y', '0');
    cutout.setAttribute('width', '0');
    cutout.setAttribute('height', '0');
    return;
  }

  targetEl.classList.add('tour-target-highlight');
  activeHighlightedEl = targetEl;

  // Scroll element into view if offscreen
  const rect = targetEl.getBoundingClientRect();
  const pad = 8;
  const x = Math.max(0, rect.left - pad);
  const y = Math.max(0, rect.top - pad);
  const width = rect.width + (pad * 2);
  const height = rect.height + (pad * 2);

  // Smooth spotlight cutout transition
  cutout.style.transition = 'x 250ms ease, y 250ms ease, width 250ms ease, height 250ms ease';
  cutout.setAttribute('x', x);
  cutout.setAttribute('y', y);
  cutout.setAttribute('width', width);
  cutout.setAttribute('height', height);
}

function updateTourCard(step, targetEl) {
  const card = document.getElementById('tour-card');
  if (!card) return;

  // Update content
  document.getElementById('tour-step-badge').innerText = `${step.step} of ${TOUR_STEPS.length}`;
  document.getElementById('tour-card-title').innerText = step.title;
  document.getElementById('tour-card-body').innerText = step.text;

  const nextBtn = document.getElementById('tour-btn-next');
  const prevBtn = document.getElementById('tour-btn-prev');
  if (nextBtn) {
    nextBtn.innerText = currentStep === TOUR_STEPS.length - 1 ? 'Finish Tour ✓' : 'Next Step →';
  }
  if (prevBtn) {
    prevBtn.style.visibility = currentStep === 0 ? 'hidden' : 'visible';
  }

  card.style.display = 'block';

  // Position card near target or center
  if (!targetEl) {
    card.style.top = '50%';
    card.style.left = '50%';
    card.style.transform = 'translate(-50%, -50%)';
    return;
  }

  card.style.transform = 'none';
  const rect = targetEl.getBoundingClientRect();
  const cardWidth = Math.min(380, window.innerWidth - 32);
  const cardHeight = card.offsetHeight || 190;
  const margin = 14;

  let top = rect.bottom + margin;
  let left = rect.left;

  // Check if bottom overflows viewport
  if (top + cardHeight > window.innerHeight - 20) {
    // Try positioning above
    top = rect.top - cardHeight - margin;
  }

  // If still out of view, clamp
  if (top < 16) {
    top = Math.max(16, window.innerHeight - cardHeight - 24);
  }

  // Check right overflow
  if (left + cardWidth > window.innerWidth - 16) {
    left = window.innerWidth - cardWidth - 16;
  }
  if (left < 16) left = 16;

  card.style.top = `${top}px`;
  card.style.left = `${left}px`;
}

function handleReposition() {
  if (!isTourActive) return;
  const step = TOUR_STEPS[currentStep];
  const targetEl = step.target ? document.querySelector(step.target) : null;
  updateSpotlight(targetEl);
  updateTourCard(step, targetEl);
}

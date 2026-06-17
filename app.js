/* ═══════════════════════════════════════════════════════════
   GRIDLOCK AI — Dashboard Application
   ═══════════════════════════════════════════════════════════ */

// ─── Global State ───
let appData = {};
let maps = {};
let charts = {};
const rendered = { overview: false, hotspots: false, predictions: false, patrol: false, enforcement: false };

// ─── Chart.js Defaults (Dark Theme) ───
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17,24,39,0.95)';
Chart.defaults.plugins.tooltip.titleFont = { family: "'Inter', sans-serif", weight: '600' };
Chart.defaults.plugins.tooltip.bodyFont = { family: "'Inter', sans-serif" };
Chart.defaults.plugins.tooltip.borderColor = 'rgba(0,229,255,0.2)';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.elements.arc.borderWidth = 0;

// ─── Constants ───
const TILE_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const TILE_ATTR = '&copy; <a href="https://carto.com/">CARTO</a>';
const MAP_CENTER = [12.97, 77.59];
const MAP_ZOOM = 12;

const COLORS = {
  cyan: '#00e5ff',
  amber: '#ffab00',
  red: '#ff1744',
  green: '#00e676',
  purple: '#b388ff',
  cyanFade: 'rgba(0,229,255,0.15)',
  amberFade: 'rgba(255,171,0,0.15)',
  redFade: 'rgba(255,23,68,0.15)',
  greenFade: 'rgba(0,230,118,0.15)',
};

// ─── Helpers ───
function fmt(n) { return n != null ? Number(n).toLocaleString() : '—'; }

function fmtHour(h) {
  if (h == null) return '—';
  const hour = typeof h === 'string' ? parseInt(h, 10) : h;
  if (isNaN(hour)) return h;
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const h12 = hour % 12 || 12;
  return `${h12}:00 ${ampm}`;
}

function fmtPct(n) { return n != null ? `${n >= 0 ? '+' : ''}${Number(n).toFixed(1)}%` : '—'; }

function cisClass(score) {
  if (score >= 80) return 'cis-critical';
  if (score >= 60) return 'cis-high';
  if (score >= 40) return 'cis-medium';
  return 'cis-low';
}

function cisColor(score) {
  if (score >= 80) return COLORS.red;
  if (score >= 60) return COLORS.amber;
  if (score >= 40) return COLORS.cyan;
  return COLORS.green;
}

function priorityClass(p) {
  const pl = (p || '').toLowerCase();
  if (pl.includes('high') || pl.includes('critical')) return 'priority-high';
  if (pl.includes('medium') || pl.includes('moderate')) return 'priority-medium';
  return 'priority-low';
}

/** Animate a KPI element counting up from 0 to target */
function countUp(el, target, suffix = '') {
  if (typeof target !== 'number' || isNaN(target)) { el.textContent = target || '—'; return; }
  const duration = 1200;
  const start = performance.now();
  const isInt = Number.isInteger(target);
  el.classList.add('counting');
  function tick(now) {
    const t = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3); // ease-out cubic
    const val = ease * target;
    el.textContent = (isInt ? Math.round(val).toLocaleString() : val.toFixed(1)) + suffix;
    if (t < 1) requestAnimationFrame(tick);
    else el.classList.remove('counting');
  }
  requestAnimationFrame(tick);
}

function createMap(id) {
  const map = L.map(id, { zoomControl: true, attributionControl: true }).setView(MAP_CENTER, MAP_ZOOM);
  L.tileLayer(TILE_URL, { attribution: TILE_ATTR, maxZoom: 19 }).addTo(map);
  return map;
}

// ─── Data Loading ───
async function loadAllData() {
  const files = ['summary', 'heatmap', 'hotspots', 'time_series', 'patrol_routes', 'enforcement', 'bias', 'model_weights'];
  const results = await Promise.all(files.map(f => fetch(`data/${f}.json`).then(r => r.json()).catch(() => null)));
  files.forEach((f, i) => appData[f] = results[i]);
}

// ─── Tab Navigation ───
function setupTabs() {
  const btns = document.querySelectorAll('.tab-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      const panel = document.getElementById(`tab-${tab}`);
      if (panel) panel.classList.add('active');
      activateTab(tab);
    });
  });
}

// ───── RENDER: EQUITY & BIAS ─────
function renderBias() {
  if (!appData.bias) return;
  if (rendered.bias) return; 
  rendered.bias = true;

  const bData = appData.bias;

  // KPIs
  document.getElementById('bias-easy-ratio').textContent = bData.city_easy_target_ratio.toFixed(2);
  document.getElementById('bias-quota-spike').textContent = (bData.quota_spike_pct > 0 ? '+' : '') + bData.quota_spike_pct.toFixed(1) + '%';
  document.getElementById('bias-worst-station').textContent = bData.most_biased_station;

  // Scatter Plot (Bias vs Volume)
  const scatterData = bData.station_metrics.map(s => ({
    x: s.total_tickets,
    y: s.bias_score,
    station: s.station
  }));

  const ctxScatter = document.getElementById('chart-bias-scatter').getContext('2d');
  charts.biasScatter = new Chart(ctxScatter, {
    type: 'scatter',
    data: {
      datasets: [{
        label: 'Stations',
        data: scatterData,
        backgroundColor: 'rgba(0, 229, 255, 0.6)',
        borderColor: '#00e5ff',
        borderWidth: 1,
        pointRadius: 6,
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const d = ctx.raw;
              return `${d.station}: Tickets=${d.x}, Bias=${d.y}`;
            }
          }
        },
        legend: { display: false }
      },
      scales: {
        x: { title: { display: true, text: 'Total Tickets Issued', color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { title: { display: true, text: 'Bias Score (Deviation %)', color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });

  // Temporal Area Chart
  const tempLabels = bData.temporal_distribution.map(d => d.day);
  const tempCounts = bData.temporal_distribution.map(d => d.count);
  
  const ctxTemp = document.getElementById('chart-bias-temporal').getContext('2d');
  charts.biasTemporal = new Chart(ctxTemp, {
    type: 'line',
    data: {
      labels: tempLabels,
      datasets: [{
        label: 'Violations by Day of Month',
        data: tempCounts,
        borderColor: '#ffab00',
        backgroundColor: 'rgba(255, 171, 0, 0.2)',
        fill: true,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        annotation: {
          annotations: {
            box1: {
              type: 'box',
              xMin: 25,
              xMax: 31,
              backgroundColor: 'rgba(255, 23, 68, 0.1)',
              borderColor: 'rgba(255, 23, 68, 0.5)',
              borderWidth: 1,
              label: {
                content: 'Quota Period',
                display: true,
                position: 'top'
              }
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true }
      }
    }
  });

  // Populate Table
  const tbody = document.getElementById('bias-table-body');
  bData.station_metrics.slice(0, 15).forEach((s, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${i + 1}</td>
      <td><strong>${s.station}</strong></td>
      <td><span style="color: ${s.bias_score > 30 ? '#ff1744' : '#ffab00'}">${s.bias_score.toFixed(1)}</span></td>
      <td>${s.total_tickets.toLocaleString()}</td>
      <td>${s.easy_target_ratio.toFixed(2)}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ───── RENDER: ENFORCEMENT ─────
function renderEnforcement() {
  if (!appData.enforcement) return;
  if (rendered.enforcement) return;
  rendered.enforcement = true;

  const eData = appData.enforcement;
  // KPIs
  document.getElementById('enf-total-violations').textContent = eData.summary.total_zones.toLocaleString();
  document.getElementById('enf-improving').textContent = eData.summary.improving.toLocaleString();
  document.getElementById('enf-worsening').textContent = eData.summary.worsening.toLocaleString();
  document.getElementById('enf-avg-change').textContent = eData.summary.avg_change_pct.toFixed(1) + '%';

  // Map
  maps.enforcement = L.map('enforcement-map').setView([12.97, 77.59], 12);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CARTO'
  }).addTo(maps.enforcement);

  eData.zones.forEach(z => {
    let color = '#94a3b8'; // stable
    if (z.trend === 'improving') color = '#00e676';
    if (z.trend === 'worsening') color = '#ff1744';

    const absChange = Math.abs(z.change_pct);
    const radius = Math.max(6, Math.min(20, absChange / 5));

    const circle = L.circleMarker([z.lat, z.lng], {
      radius: radius,
      fillColor: color,
      color: color,
      weight: 1,
      opacity: 1,
      fillOpacity: 0.6
    }).addTo(maps.enforcement);

    circle.bindPopup(`
      <div class="popup-title">${z.label}</div>
      <div class="popup-row"><span class="popup-label">Station:</span> <span class="popup-val">${z.police_station}</span></div>
      <div class="popup-row"><span class="popup-label">Before:</span> <span class="popup-val">${z.before}</span></div>
      <div class="popup-row"><span class="popup-label">After:</span> <span class="popup-val">${z.after}</span></div>
      <hr style="border-color:rgba(255,255,255,0.1); margin:8px 0;">
      <div class="popup-row" style="color:${color};font-weight:700;">
        <span>Change:</span> <span>${z.change_pct > 0 ? '+' : ''}${z.change_pct.toFixed(1)}%</span>
      </div>
    `);
  });

  // Populate Tables
  const impBody = document.getElementById('improvers-body');
  impBody.innerHTML = '';
  eData.summary.top_improvers.forEach(z => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${z.label.split(',')[0]}</strong></td>
      <td>${z.before} → ${z.after}</td>
      <td><span class="change-badge change-positive">${z.change_pct.toFixed(1)}%</span></td>
    `;
    impBody.appendChild(tr);
  });

  const decBody = document.getElementById('concern-body');
  decBody.innerHTML = '';
  eData.summary.top_decliners.forEach(z => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${z.label.split(',')[0]}</strong></td>
      <td>${z.before} → ${z.after}</td>
      <td><span class="change-badge change-negative">+${z.change_pct.toFixed(1)}%</span></td>
    `;
    decBody.appendChild(tr);
  });
}

// ───── REAL-TIME SIMULATOR ─────
function initSimulator() {
  if (!appData.model_weights) return;
  const model = appData.model_weights;
  
  const simStation = document.getElementById('sim-station');
  const simDay = document.getElementById('sim-day');
  const simHour = document.getElementById('sim-hour');
  const simHourVal = document.getElementById('sim-hour-val');
  const simQuota = document.getElementById('sim-quota');

  // Populate stations dropdown
  model.stations.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    simStation.appendChild(opt);
  });
  
  if (model.stations.length > 0) {
    // Select Madiwala by default if exists, else first
    const madiwala = model.stations.find(s => s.toLowerCase().includes('madiwala'));
    simStation.value = madiwala || model.stations[0];
  }

  // Format hour AM/PM
  function formatHour(h) {
    const ampm = h >= 12 ? 'PM' : 'AM';
    let hr = h % 12;
    if (hr === 0) hr = 12;
    return `${hr}:00 ${ampm}`;
  }

  // Run Inference Engine
  function runPrediction() {
    const station = simStation.value;
    const day = simDay.value;
    const hour = parseInt(simHour.value);
    const isQuota = simQuota.checked;

    simHourVal.textContent = formatHour(hour);

    // Fast Client-Side Inference using Rigorous Interaction Matrix [Station][Day][Hour]
    const stationMatrix = model.interaction_matrix[station] || {};
    const dayArray = stationMatrix[day] || new Array(24).fill(0);
    const basePrediction = dayArray[hour] || 0;
    
    const quotaMult = isQuota ? model.quota_multiplier : 1;

    // The prediction!
    const predictedViolations = basePrediction * quotaMult;
    
    // Update UI Output
    const countEl = document.getElementById('sim-out-count');
    const displayCount = Math.max(0, Math.round(predictedViolations));
    countEl.textContent = displayCount;

    // Determine Severity
    // Assuming max expected violations for any station is around ~30/hr for the scale
    const maxExpected = 15; 
    let severityPct = (predictedViolations / maxExpected) * 100;
    if (severityPct > 100) severityPct = 100;

    const sevEl = document.getElementById('sim-out-severity');
    const barEl = document.getElementById('sim-out-bar');
    
    barEl.style.width = `${severityPct}%`;

    if (severityPct < 25) {
      sevEl.textContent = 'LOW';
      sevEl.style.color = 'var(--accent-green)';
      barEl.style.background = 'var(--accent-green)';
      countEl.style.color = 'var(--accent-green)';
    } else if (severityPct < 50) {
      sevEl.textContent = 'MODERATE';
      sevEl.style.color = 'var(--accent-cyan)';
      barEl.style.background = 'var(--accent-cyan)';
      countEl.style.color = 'var(--accent-cyan)';
    } else if (severityPct < 75) {
      sevEl.textContent = 'HIGH';
      sevEl.style.color = 'var(--accent-amber)';
      barEl.style.background = 'var(--accent-amber)';
      countEl.style.color = 'var(--accent-amber)';
    } else {
      sevEl.textContent = 'CRITICAL';
      sevEl.style.color = 'var(--accent-red)';
      barEl.style.background = 'var(--accent-red)';
      countEl.style.color = 'var(--accent-red)';
    }
  }

  // Bind Events
  simStation.addEventListener('change', runPrediction);
  simDay.addEventListener('change', runPrediction);
  simHour.addEventListener('input', runPrediction);
  simQuota.addEventListener('change', runPrediction);

  // Initial Run
  runPrediction();
}

function activateTab(tab) {
  // Lazy render
  switch (tab) {
    case 'overview': renderOverview(); break;
    case 'hotspots': renderHotspots(); break;
    case 'predictions': renderPredictions(); break;
    case 'patrol': renderPatrol(); break;
    case 'enforcement': renderEnforcement(); break;
    case 'bias': renderBias(); break;
  }
  // Invalidate maps after DOM is visible
  setTimeout(() => {
    Object.values(maps).forEach(m => { try { m.invalidateSize(); } catch (_) {} });
  }, 150);
}

// ════════════════════════════════════════════════════════════
// TAB 1: OVERVIEW
// ════════════════════════════════════════════════════════════
function renderOverview() {
  if (rendered.overview) return;
  rendered.overview = true;

  const s = appData.summary || {};

  // Date badge
  const dateText = s.date_range || (s.start_date && s.end_date ? `${s.start_date} – ${s.end_date}` : 'Nov 2023 – Apr 2024');
  document.getElementById('date-range-text').textContent = dateText;

  // KPIs
  countUp(document.getElementById('kpi-total-violations'), s.total_violations);
  countUp(document.getElementById('kpi-critical-hotspots'), s.critical_hotspots);
  document.getElementById('kpi-peak-hour').textContent = fmtHour(s.peak_hour);
  countUp(document.getElementById('kpi-avg-daily'), s.avg_daily);

  // ── Heatmap ──
  try {
    const map = createMap('overview-map');
    maps.overview = map;
    const hm = appData.heatmap;
    if (hm) {
      let points = [];
      if (Array.isArray(hm)) {
        points = hm.map(p => Array.isArray(p) ? p : [p.lat, p.lng, p.intensity || p.weight || 1]);
      } else if (hm.points) {
        points = hm.points.map(p => Array.isArray(p) ? p : [p.lat, p.lng, p.intensity || p.weight || 1]);
      }
      if (points.length) {
        L.heatLayer(points, {
          radius: 20, blur: 25, maxZoom: 17,
          gradient: { 0.2: '#0a0f1a', 0.4: '#00e5ff', 0.6: '#ffab00', 0.8: '#ff6d00', 1.0: '#ff1744' }
        }).addTo(map);
      }
    }
  } catch (e) { console.warn('Overview map error:', e); }

  // ── Violation Type Doughnut ──
  try {
    const bd = s.violation_breakdown || s.violation_types || {};
    let entries = Array.isArray(bd) ? bd : Object.entries(bd).map(([k, v]) => ({ label: k, value: v }));
    entries.sort((a, b) => (b.value || b.count || 0) - (a.value || a.count || 0));
    let top = entries.slice(0, 6);
    const otherVal = entries.slice(6).reduce((acc, e) => acc + (e.value || e.count || 0), 0);
    if (otherVal > 0) top.push({ label: 'Other', value: otherVal });

    const doughnutColors = [COLORS.cyan, COLORS.amber, COLORS.red, COLORS.green, COLORS.purple, '#ff6d00', '#78909c'];
    charts.violationTypes = new Chart(document.getElementById('chart-violation-types'), {
      type: 'doughnut',
      data: {
        labels: top.map(e => e.label || e.type || e.name),
        datasets: [{
          data: top.map(e => e.value || e.count || 0),
          backgroundColor: doughnutColors.slice(0, top.length),
          borderWidth: 0,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: { position: 'right', labels: { font: { size: 11 }, padding: 10, boxWidth: 10 } }
        }
      }
    });
  } catch (e) { console.warn('Doughnut chart error:', e); }

  // ── Top Stations Bar ──
  try {
    const ts = s.top_stations || s.top_police_stations || [];
    let stationData = Array.isArray(ts) ? ts : Object.entries(ts).map(([k, v]) => ({ name: k, count: v }));
    stationData.sort((a, b) => (b.count || b.violations || b.value || 0) - (a.count || a.violations || a.value || 0));
    stationData = stationData.slice(0, 10);

    charts.topStations = new Chart(document.getElementById('chart-top-stations'), {
      type: 'bar',
      data: {
        labels: stationData.map(s => (s.name || s.station || '').replace(/ PS$/i, '')),
        datasets: [{
          data: stationData.map(s => s.count || s.violations || s.value || 0),
          backgroundColor: 'rgba(0,229,255,0.3)',
          borderColor: COLORS.cyan,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.7
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { font: { size: 10 } } },
          y: { grid: { display: false }, ticks: { font: { size: 10 } } }
        }
      }
    });
  } catch (e) { console.warn('Top stations chart error:', e); }

  // ── Daily Trend ──
  try {
    const ts = appData.time_series || {};
    const daily = ts.daily || [];
    if (daily.length) {
      const labels = daily.map(d => d.date || d.day || d.label || '');
      const values = daily.map(d => d.count || d.violations || d.value || 0);

      charts.dailyTrend = new Chart(document.getElementById('chart-daily-trend'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Violations',
            data: values,
            borderColor: COLORS.cyan,
            backgroundColor: createGradient('chart-daily-trend', COLORS.cyan),
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            pointHitRadius: 8,
            borderWidth: 2
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { maxTicksLimit: 12, font: { size: 10 } } },
            y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { font: { size: 10 } } }
          },
          interaction: { mode: 'index', intersect: false }
        }
      });
    }
  } catch (e) { console.warn('Daily trend chart error:', e); }
}

function createGradient(canvasId, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return color;
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight || 280);
  gradient.addColorStop(0, color.replace(')', ',0.25)').replace('rgb', 'rgba'));
  gradient.addColorStop(1, color.replace(')', ',0.01)').replace('rgb', 'rgba'));
  return gradient;
}

// ════════════════════════════════════════════════════════════
// TAB 2: HOTSPOT ANALYSIS
// ════════════════════════════════════════════════════════════
function renderHotspots() {
  if (rendered.hotspots) return;
  rendered.hotspots = true;

  const hotspots = appData.hotspots || [];
  const data = Array.isArray(hotspots) ? hotspots : (hotspots.hotspots || hotspots.zones || []);

  // ── Map ──
  try {
    const map = createMap('hotspot-map');
    maps.hotspots = map;

    data.forEach(h => {
      const lat = h.lat || h.latitude;
      const lng = h.lng || h.lon || h.longitude;
      if (lat == null || lng == null) return;
      const cis = h.cis || h.cis_score || h.score || 0;
      const radius = Math.max(8, Math.min(30, (cis / 100) * 30));
      const color = cisColor(cis);

      const circle = L.circleMarker([lat, lng], {
        radius, fillColor: color, fillOpacity: 0.6,
        color: color, weight: 1, opacity: 0.8
      }).addTo(map);

      const peakHours = h.peak_hours || h.peak_hour || '—';
      const topViol = (h.top_violations || h.top_violation_types || []).slice(0, 3).join(', ') || '—';
      circle.bindPopup(`
        <div class="popup-title">${h.label || h.name || h.location || 'Zone'}</div>
        <div class="popup-row"><span class="popup-label">CIS Score</span><span class="popup-val">${cis}</span></div>
        <div class="popup-row"><span class="popup-label">Violations</span><span class="popup-val">${fmt(h.violations || h.total_violations || h.count || 0)}</span></div>
        <div class="popup-row"><span class="popup-label">Peak Hours</span><span class="popup-val">${Array.isArray(peakHours) ? peakHours.join(', ') : peakHours}</span></div>
        <div class="popup-row"><span class="popup-label">Top Types</span><span class="popup-val">${topViol}</span></div>
        <div class="popup-row"><span class="popup-label">Junction</span><span class="popup-val">${h.junction || h.junction_type || '—'}</span></div>
      `);
    });

    // Legend
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = function () {
      const div = L.DomUtil.create('div', 'map-legend');
      div.innerHTML = `
        <div class="legend-title">CIS Severity</div>
        <div><i style="background:${COLORS.red}"></i> Critical (≥80)</div>
        <div><i style="background:${COLORS.amber}"></i> High (≥60)</div>
        <div><i style="background:${COLORS.cyan}"></i> Medium (≥40)</div>
        <div><i style="background:${COLORS.green}"></i> Low (&lt;40)</div>
      `;
      return div;
    };
    legend.addTo(map);

    // Fit bounds
    const coords = data.filter(h => h.lat || h.latitude).map(h => [h.lat || h.latitude, h.lng || h.lon || h.longitude]);
    if (coords.length) map.fitBounds(coords, { padding: [30, 30] });
  } catch (e) { console.warn('Hotspot map error:', e); }

  // ── Table ──
  try {
    const tbody = document.getElementById('hotspot-table-body');
    const sorted = [...data].sort((a, b) => (b.cis || b.cis_score || b.score || 0) - (a.cis || a.cis_score || a.score || 0));
    sorted.slice(0, 30).forEach((h, i) => {
      const cis = h.cis || h.cis_score || h.score || 0;
      const peak = h.peak_hours || h.peak_hour || '—';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td style="color:var(--text-primary);font-weight:500">${h.label || h.name || h.location || '—'}</td>
        <td><span class="cis-badge ${cisClass(cis)}">${cis}</span></td>
        <td>${fmt(h.violations || h.total_violations || h.count || 0)}</td>
        <td>${Array.isArray(peak) ? peak.join(', ') : peak}</td>
        <td>${h.junction || h.junction_type || '—'}</td>
        <td>${h.station || h.police_station || '—'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) { console.warn('Hotspot table error:', e); }
}

// ════════════════════════════════════════════════════════════
// TAB 3: PREDICTIONS
// ════════════════════════════════════════════════════════════
function renderPredictions() {
  if (rendered.predictions) return;
  rendered.predictions = true;

  const ts = appData.time_series || {};
  const weekly = ts.weekly || [];
  const forecast = ts.forecast || [];
  const hourly = ts.hourly || [];
  const dow = ts.day_of_week || [];
  const monthly = ts.monthly || [];

  // ── KPIs ──
  try {
    // Forecast trend
    const lastActual = weekly.length ? (weekly[weekly.length - 1].count || weekly[weekly.length - 1].violations || weekly[weekly.length - 1].value || 0) : 0;
    const firstForecast = forecast.length ? (forecast[0].predicted || forecast[0].count || forecast[0].value || 0) : 0;
    const change = lastActual > 0 ? ((firstForecast - lastActual) / lastActual * 100) : 0;
    const trendIcon = change >= 0 ? '📈' : '📉';
    document.getElementById('pred-trend-icon').textContent = trendIcon;
    document.getElementById('pred-trend-value').textContent = fmtPct(change);
    document.getElementById('pred-trend-value').style.color = change >= 0 ? COLORS.red : COLORS.green;

    // Predicted next week total
    const nextWeekTotal = forecast.slice(0, 7).reduce((s, d) => s + (d.predicted || d.count || d.value || 0), 0);
    const totalForecast = nextWeekTotal || (forecast.length ? (forecast[0].predicted || forecast[0].count || forecast[0].value || 0) : 0);
    countUp(document.getElementById('pred-next-week'), Math.round(totalForecast));

    // Peak day
    const dowData = Array.isArray(dow) ? dow : Object.entries(dow).map(([k, v]) => ({ day: k, count: typeof v === 'number' ? v : v.count || v.value || 0 }));
    if (dowData.length) {
      const peak = dowData.reduce((max, d) => ((d.count || d.violations || d.value || 0) > (max.count || max.violations || max.value || 0) ? d : max), dowData[0]);
      document.getElementById('pred-peak-day').textContent = peak.day || peak.label || peak.name || '—';
    }
  } catch (e) { console.warn('Prediction KPIs error:', e); }

  // ── Weekly + Forecast Chart ──
  try {
    const weeklyLabels = weekly.map(d => d.week || d.date || d.label || '');
    const weeklyValues = weekly.map(d => d.count || d.violations || d.value || 0);
    const forecastLabels = forecast.map(d => d.week || d.date || d.label || '');
    const forecastValues = forecast.map(d => d.predicted || d.count || d.value || 0);
    const lowerBand = forecast.map(d => d.lower || d.lower_bound || (d.predicted || d.count || 0) * 0.85);
    const upperBand = forecast.map(d => d.upper || d.upper_bound || (d.predicted || d.count || 0) * 1.15);

    const allLabels = [...weeklyLabels, ...forecastLabels];
    const actualDataset = [...weeklyValues, ...new Array(forecastLabels.length).fill(null)];
    const forecastDataset = [...new Array(weeklyLabels.length - 1).fill(null), weeklyValues[weeklyValues.length - 1] || null, ...forecastValues];
    const lowerDataset = [...new Array(weeklyLabels.length - 1).fill(null), weeklyValues[weeklyValues.length - 1] || null, ...lowerBand];
    const upperDataset = [...new Array(weeklyLabels.length - 1).fill(null), weeklyValues[weeklyValues.length - 1] || null, ...upperBand];

    charts.weeklyForecast = new Chart(document.getElementById('chart-weekly-forecast'), {
      type: 'line',
      data: {
        labels: allLabels,
        datasets: [
          {
            label: 'Actual',
            data: actualDataset,
            borderColor: COLORS.cyan,
            backgroundColor: 'transparent',
            tension: 0.3, pointRadius: 2, borderWidth: 2
          },
          {
            label: 'Forecast',
            data: forecastDataset,
            borderColor: COLORS.amber,
            borderDash: [6, 4],
            backgroundColor: 'transparent',
            tension: 0.3, pointRadius: 2, borderWidth: 2
          },
          {
            label: 'Upper Bound',
            data: upperDataset,
            borderColor: 'transparent',
            backgroundColor: 'rgba(255,171,0,0.08)',
            fill: '+1',
            tension: 0.3, pointRadius: 0, borderWidth: 0
          },
          {
            label: 'Lower Bound',
            data: lowerDataset,
            borderColor: 'transparent',
            backgroundColor: 'rgba(255,171,0,0.08)',
            fill: '-1',
            tension: 0.3, pointRadius: 0, borderWidth: 0
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { labels: { filter: item => item.text === 'Actual' || item.text === 'Forecast' } }
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 10, font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { font: { size: 10 } } }
        },
        interaction: { mode: 'index', intersect: false }
      }
    });
  } catch (e) { console.warn('Weekly forecast chart error:', e); }

  // ── Hourly Pattern ──
  try {
    const hourlyData = Array.isArray(hourly) ? hourly : Object.entries(hourly).map(([k, v]) => ({ hour: k, count: typeof v === 'number' ? v : v.count || 0 }));
    const hours = hourlyData.map(d => fmtHour(d.hour));
    const vals = hourlyData.map(d => d.count || d.violations || d.value || 0);
    const maxVal = Math.max(...vals, 1);
    const barColors = vals.map(v => {
      const ratio = v / maxVal;
      if (ratio > 0.75) return COLORS.red;
      if (ratio > 0.5) return COLORS.amber;
      if (ratio > 0.25) return COLORS.cyan;
      return COLORS.green;
    });

    charts.hourly = new Chart(document.getElementById('chart-hourly'), {
      type: 'bar',
      data: {
        labels: hours,
        datasets: [{
          label: 'Violations',
          data: vals,
          backgroundColor: barColors.map(c => c + '55'),
          borderColor: barColors,
          borderWidth: 1,
          borderRadius: 3,
          barPercentage: 0.8
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 12, font: { size: 9 } } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { font: { size: 10 } } }
        }
      }
    });
  } catch (e) { console.warn('Hourly chart error:', e); }

  // ── Day of Week ──
  try {
    const dowData = Array.isArray(dow) ? dow : Object.entries(dow).map(([k, v]) => ({ day: k, count: typeof v === 'number' ? v : v.count || v.value || 0 }));
    charts.dayOfWeek = new Chart(document.getElementById('chart-day-of-week'), {
      type: 'bar',
      data: {
        labels: dowData.map(d => d.day || d.label || d.name || ''),
        datasets: [{
          label: 'Violations',
          data: dowData.map(d => d.count || d.violations || d.value || 0),
          backgroundColor: 'rgba(0,229,255,0.3)',
          borderColor: COLORS.cyan,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { font: { size: 10 } } },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } }
        }
      }
    });
  } catch (e) { console.warn('Day of week chart error:', e); }

  // ── Monthly Trend ──
  try {
    const monthData = Array.isArray(monthly) ? monthly : Object.entries(monthly).map(([k, v]) => ({ month: k, count: typeof v === 'number' ? v : v.count || v.value || 0 }));
    const monthLabels = monthData.map(d => d.month || d.label || d.name || '');
    const monthVals = monthData.map(d => d.count || d.violations || d.value || 0);

    charts.monthly = new Chart(document.getElementById('chart-monthly'), {
      type: 'bar',
      data: {
        labels: monthLabels,
        datasets: [
          {
            label: 'Violations',
            data: monthVals,
            backgroundColor: 'rgba(179,136,255,0.3)',
            borderColor: COLORS.purple,
            borderWidth: 1,
            borderRadius: 4,
            barPercentage: 0.6,
            order: 2
          },
          {
            label: 'Trend',
            data: monthVals,
            type: 'line',
            borderColor: COLORS.amber,
            backgroundColor: 'transparent',
            tension: 0.4,
            pointRadius: 3,
            pointBackgroundColor: COLORS.amber,
            borderWidth: 2,
            order: 1
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { font: { size: 10 } } }
        }
      }
    });
  } catch (e) { console.warn('Monthly chart error:', e); }
}

// ════════════════════════════════════════════════════════════
// TAB 4: PATROL ROUTES
// ════════════════════════════════════════════════════════════
function renderPatrol() {
  if (rendered.patrol) return;
  rendered.patrol = true;

  const pr = appData.patrol_routes || {};
  const routes = pr.routes || (Array.isArray(pr) ? pr : []);

  const defaultRouteColors = [COLORS.cyan, COLORS.amber, COLORS.red, COLORS.green, COLORS.purple, '#ff6d00', '#78909c', '#e040fb'];

  // ── Map ──
  try {
    const map = createMap('patrol-map');
    maps.patrol = map;
    const allCoords = [];

    routes.forEach((route, ri) => {
      const waypoints = route.waypoints || route.stops || route.points || [];
      const color = route.color || defaultRouteColors[ri % defaultRouteColors.length];
      const coords = waypoints.map(w => [w.lat || w.latitude, w.lng || w.lon || w.longitude]).filter(c => c[0] != null && c[1] != null);
      if (!coords.length) return;
      allCoords.push(...coords);

      // Polyline
      L.polyline(coords, { color, weight: 3, opacity: 0.8, dashArray: null }).addTo(map);

      // Return-to-start dashed line
      if (coords.length > 1) {
        L.polyline([coords[coords.length - 1], coords[0]], { color, weight: 2, opacity: 0.4, dashArray: '8,8' }).addTo(map);
      }

      // Waypoint markers
      waypoints.forEach((w, wi) => {
        const lat = w.lat || w.latitude;
        const lng = w.lng || w.lon || w.longitude;
        if (lat == null || lng == null) return;

        const marker = L.circleMarker([lat, lng], {
          radius: 10, fillColor: color, fillOpacity: 0.9,
          color: '#fff', weight: 2, opacity: 0.9
        }).addTo(map);

        // Number label
        const icon = L.divIcon({
          className: '',
          html: `<div style="width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#0a0f1a;background:${color};border-radius:50%;border:2px solid #fff;box-shadow:0 0 8px ${color}80;">${wi + 1}</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10]
        });
        L.marker([lat, lng], { icon }).addTo(map);

        marker.bindPopup(`
          <div class="popup-title">${w.label || w.name || w.location || `Stop ${wi + 1}`}</div>
          <div class="popup-row"><span class="popup-label">CIS Score</span><span class="popup-val">${w.cis || w.cis_score || '—'}</span></div>
          <div class="popup-row"><span class="popup-label">Violations</span><span class="popup-val">${fmt(w.violations || w.total_violations || 0)}</span></div>
        `);
      });
    });

    if (allCoords.length) map.fitBounds(allCoords, { padding: [40, 40] });
  } catch (e) { console.warn('Patrol map error:', e); }

  // ── Route Cards ──
  try {
    const container = document.getElementById('route-cards-container');
    routes.forEach((route, ri) => {
      const waypoints = route.waypoints || route.stops || route.points || [];
      const color = route.color || defaultRouteColors[ri % defaultRouteColors.length];
      const priority = route.priority || 'medium';
      const card = document.createElement('div');
      card.className = 'route-card';
      card.style.animationDelay = `${ri * 0.1}s`;
      card.style.borderTop = `3px solid ${color}`;

      card.innerHTML = `
        <div class="route-card-header">
          <div class="route-card-name">${route.name || route.zone || `Route ${ri + 1}`}</div>
          <span class="route-card-priority ${priorityClass(priority)}">${priority}</span>
        </div>
        <div class="route-card-stats">
          <span>📍 <strong>${waypoints.length}</strong> stops</span>
          <span>📏 <strong>${route.total_km || route.distance_km || route.distance || '—'}</strong> km</span>
        </div>
        <ul class="waypoint-list">
          ${waypoints.map((w, wi) => {
            const cis = w.cis || w.cis_score || 0;
            return `<li class="waypoint-item">
              <span class="waypoint-num" style="background:${color}">${wi + 1}</span>
              <span class="waypoint-label">${w.label || w.name || w.location || `Stop ${wi + 1}`}</span>
              <span class="waypoint-cis cis-badge ${cisClass(cis)}">${cis}</span>
            </li>`;
          }).join('')}
        </ul>
      `;
      container.appendChild(card);
    });
  } catch (e) { console.warn('Route cards error:', e); }
}

// ════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════
async function init() {
  try {
    await loadAllData();
    setupTabs();
    initSimulator();
    renderOverview();
  } catch (e) {
    console.error('Initialization error:', e);
  } finally {
    // Hide loader
    setTimeout(() => {
      const overlay = document.getElementById('loading-overlay');
      if (overlay) overlay.classList.add('hidden');
    }, 400);
  }
}

// Boot
document.addEventListener('DOMContentLoaded', init);

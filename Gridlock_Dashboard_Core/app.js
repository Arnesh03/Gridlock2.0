Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';

let appData = {};
let heatmapMap = null;
let cisMap = null;
let charts = {};

document.addEventListener('DOMContentLoaded', init);

async function init() {
  await loadData();
  setupTabs();
  renderOverview();
  document.getElementById('loading').classList.add('hidden');
}

async function loadData() {
  try {
    const [summaryRes, hotspotsRes, heatmapRes] = await Promise.all([
      fetch('data/summary.json'),
      fetch('data/hotspots.json'),
      fetch('data/heatmap.json')
    ]);
    appData.summary = await summaryRes.json();
    appData.hotspots = await hotspotsRes.json();
    appData.heatmap = await heatmapRes.json();
  } catch (err) {
    console.error("Failed to load data", err);
    alert("Could not load data. Did you run the python script?");
  }
}

function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      
      const target = e.target.getAttribute('data-target');
      e.target.classList.add('active');
      document.getElementById(target).classList.add('active');
      
      if (target === 'overview') {
        if (heatmapMap) heatmapMap.invalidateSize();
      } else if (target === 'hotspots') {
        if (!cisMap) renderHotspots();
        else cisMap.invalidateSize();
      }
    });
  });
}

function renderOverview() {
  // KPIs
  document.getElementById('kpi-total').textContent = appData.summary.total_violations.toLocaleString();
  document.getElementById('kpi-critical').textContent = appData.summary.critical_hotspots.toLocaleString();
  document.getElementById('kpi-daily').textContent = appData.summary.avg_daily.toLocaleString();

  // Map
  heatmapMap = L.map('heatmap-map').setView([12.97, 77.59], 12);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CARTO'
  }).addTo(heatmapMap);

  const points = appData.heatmap.map(p => [p[0], p[1], p[2]]);
  L.heatLayer(points, {
    radius: 18, blur: 25, maxZoom: 15,
    gradient: {0.2: '#0b0f19', 0.4: '#00e5ff', 0.6: '#ffab00', 0.8: '#ff6d00', 1.0: '#ff1744'}
  }).addTo(heatmapMap);

  // Chart
  const vData = appData.summary.violation_breakdown;
  const ctx = document.getElementById('violationChart').getContext('2d');
  charts.violation = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(vData),
      datasets: [{
        data: Object.values(vData),
        backgroundColor: ['#00e5ff', '#00bfa5', '#ffab00', '#ff6d00', '#ff1744', '#b388ff'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'right', labels: { color: '#f1f5f9' } }
      }
    }
  });
}

function getCisColor(cis) {
  if (cis >= 80) return '#ff1744';
  if (cis >= 60) return '#ffab00';
  if (cis >= 40) return '#00e5ff';
  return '#00e676';
}

function renderHotspots() {
  cisMap = L.map('cis-map').setView([12.97, 77.59], 12);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CARTO'
  }).addTo(cisMap);

  const tbody = document.querySelector('#hotspot-table tbody');
  
  appData.hotspots.forEach((h, i) => {
    // Map Marker
    const color = getCisColor(h.cis);
    const radius = Math.max(6, (h.cis / 100) * 20);
    
    const circle = L.circleMarker([h.lat, h.lng], {
      radius: radius,
      fillColor: color,
      color: color,
      weight: 1,
      opacity: 1,
      fillOpacity: 0.6
    }).addTo(cisMap);
    
    const vText = Object.entries(h.violation_types).map(([k,v]) => `${k} (${v})`).join('<br>');
    circle.bindPopup(`
      <div style="font-size:13px;">
        <strong style="color:${color};font-size:16px;">CIS: ${h.cis}</strong><br>
        <b>Loc:</b> ${h.label}<br>
        <b>Junc:</b> ${h.junction}<br>
        <b>Violations:</b> ${h.total_violations}<br>
        <hr style="border-color:#333;margin:5px 0;">
        ${vText}
      </div>
    `);

    // Table row
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${i+1}</td>
      <td><span class="badge-score" style="background:${color}">${h.cis}</span></td>
      <td>${h.total_violations}</td>
      <td>${h.label}</td>
    `;
    tr.addEventListener('click', () => {
      cisMap.setView([h.lat, h.lng], 16);
      circle.openPopup();
    });
    tbody.appendChild(tr);
  });
}

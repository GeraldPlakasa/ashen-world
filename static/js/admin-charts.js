/**
 * Admin Dashboard Charts
 * Uses Chart.js for visualizations
 */

// Chart.js default configuration
Chart.defaults.color = '#9ca3af';
Chart.defaults.borderColor = 'rgba(255,255,255,0.1)';
Chart.defaults.font.family = 'inherit';

// Color palettes
const COLORS = {
  primary: '#6366f1',
  success: '#22c55e',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
  muted: '#6b7280',
  palette: ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#84cc16']
};

// Store chart instances for updates
const charts = {};

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    document.getElementById('tab-' + btn.dataset.tab).style.display = 'block';
  });
});

// Fetch analytics data and render charts
async function loadAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();
    if (!data.ok) return;
    
    renderAllCharts(data);
    updateKPIs(data);
    updateTables(data);
  } catch (err) {
    console.error('Failed to load analytics:', err);
  }
}

function updateKPIs(data) {
  const c = data.current;
  document.getElementById('kpi-year').textContent = c.year || '-';
  document.getElementById('kpi-day').textContent = c.day || '-';
  document.getElementById('kpi-population').textContent = c.population || 0;
  document.getElementById('kpi-dead').textContent = c.dead_count || 0;
  document.getElementById('kpi-treasury').textContent = c.treasury || 0;
  document.getElementById('kpi-users').textContent = c.total_users || 0;
  
  // Quick stats
  const yearly = data.yearly_stats || [];
  const totalBirths = yearly.reduce((s, y) => s + (y.total_births || 0), 0);
  const totalDeaths = yearly.reduce((s, y) => s + (y.total_deaths || 0), 0);
  const totalImmigrants = yearly.reduce((s, y) => s + (y.total_immigrants || 0), 0);
  
  document.getElementById('stat-births').textContent = totalBirths;
  document.getElementById('stat-deaths').textContent = totalDeaths;
  document.getElementById('stat-immigrants').textContent = totalImmigrants;
  document.getElementById('stat-quests').textContent = data.quests?.total || 0;
  document.getElementById('stat-events').textContent = data.events?.total || 0;
  document.getElementById('stat-years').textContent = yearly.length;
}

function updateTables(data) {
  // Recent quests
  const questsBody = document.getElementById('recent-quests');
  questsBody.innerHTML = '';
  (data.quests?.history || []).reverse().forEach(q => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${q.year || '-'}</td>
      <td>${q.quest_type || '-'}</td>
      <td><span class="status-badge ${q.success ? 'alive' : 'dead'}">${q.success ? 'Success' : 'Failed'}</span></td>
      <td>${q.gold_reward || 0}</td>
    `;
    questsBody.appendChild(tr);
  });
  
  // Recent events
  const eventsBody = document.getElementById('recent-events');
  eventsBody.innerHTML = '';
  (data.events?.history || []).reverse().forEach(e => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${e.year || '-'}</td>
      <td>${e.event_type || '-'}</td>
      <td>${e.affected_count || '-'}</td>
    `;
    eventsBody.appendChild(tr);
  });
}

function renderAllCharts(data) {
  renderPopulationTreasuryChart(data);
  renderDemographicsChart(data);
  renderGenderChart(data);
  renderAgeChart(data);
  renderJobsChart(data);
  renderOriginsChart(data);
  renderSkillsChart(data);
  renderTraitsChart(data);
  renderAchievementsChart(data);
  renderQuestTypesChart(data);
  renderQuestSuccessChart(data);
  renderEventTypesChart(data);
}

function renderPopulationTreasuryChart(data) {
  const ctx = document.getElementById('chart-population-treasury');
  if (!ctx) return;
  
  const yearly = data.yearly_stats || [];
  const labels = yearly.map(y => 'Y' + y.year);
  
  // Calculate end-of-year population (start + births + immigrants - deaths)
  // This is an approximation since we don't have exact end population
  const popData = yearly.map(y => {
    const births = y.total_births || 0;
    const deaths = y.total_deaths || 0;
    const immigrants = y.total_immigrants || 0;
    // We'll use treasury_start as a proxy for activity
    return births + immigrants - deaths + 50; // Base 50
  });
  
  const treasuryData = yearly.map(y => y.treasury_end || y.treasury_start || 0);
  
  if (charts['population-treasury']) charts['population-treasury'].destroy();
  
  charts['population-treasury'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Net Population Change',
          data: yearly.map(y => (y.total_births || 0) + (y.total_immigrants || 0) - (y.total_deaths || 0)),
          borderColor: COLORS.primary,
          backgroundColor: 'rgba(99, 102, 241, 0.1)',
          fill: true,
          tension: 0.3,
          yAxisID: 'y'
        },
        {
          label: 'Treasury',
          data: treasuryData,
          borderColor: COLORS.success,
          backgroundColor: 'transparent',
          borderDash: [5, 5],
          tension: 0.3,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: { legend: { position: 'top' } },
      scales: {
        y: { position: 'left', title: { display: true, text: 'Pop Change' } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Treasury' } }
      }
    }
  });
}

function renderDemographicsChart(data) {
  const ctx = document.getElementById('chart-demographics');
  if (!ctx) return;
  
  const yearly = data.yearly_stats || [];
  const labels = yearly.map(y => 'Y' + y.year);
  
  if (charts['demographics']) charts['demographics'].destroy();
  
  charts['demographics'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        { label: 'Births', data: yearly.map(y => y.total_births || 0), backgroundColor: COLORS.success },
        { label: 'Deaths', data: yearly.map(y => y.total_deaths || 0), backgroundColor: COLORS.danger },
        { label: 'Immigrants', data: yearly.map(y => y.total_immigrants || 0), backgroundColor: COLORS.info }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { x: { stacked: false }, y: { beginAtZero: true } }
    }
  });
}

function renderGenderChart(data) {
  const ctx = document.getElementById('chart-gender');
  if (!ctx) return;
  
  const gender = data.distributions?.gender || {};
  
  if (charts['gender']) charts['gender'].destroy();
  
  charts['gender'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(gender),
      datasets: [{ data: Object.values(gender), backgroundColor: [COLORS.info, COLORS.warning] }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderAgeChart(data) {
  const ctx = document.getElementById('chart-age');
  if (!ctx) return;
  
  const age = data.distributions?.age_groups || {};
  
  if (charts['age']) charts['age'].destroy();
  
  charts['age'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(age),
      datasets: [{ data: Object.values(age), backgroundColor: COLORS.palette }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderJobsChart(data) {
  const ctx = document.getElementById('chart-jobs');
  if (!ctx) return;
  
  const jobs = data.distributions?.jobs || {};
  const sorted = Object.entries(jobs).sort((a, b) => b[1] - a[1]);
  
  if (charts['jobs']) charts['jobs'].destroy();
  
  charts['jobs'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(j => j[0]),
      datasets: [{ label: 'Count', data: sorted.map(j => j[1]), backgroundColor: COLORS.primary }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } }
    }
  });
}

function renderOriginsChart(data) {
  const ctx = document.getElementById('chart-origins');
  if (!ctx) return;
  
  const origins = data.distributions?.origins || {};
  
  if (charts['origins']) charts['origins'].destroy();
  
  charts['origins'] = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: Object.keys(origins).map(o => o.charAt(0).toUpperCase() + o.slice(1)),
      datasets: [{ data: Object.values(origins), backgroundColor: COLORS.palette }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'right' } }
    }
  });
}

function renderSkillsChart(data) {
  const ctx = document.getElementById('chart-skills');
  if (!ctx) return;
  
  const skills = data.distributions?.skills || {};
  const sorted = Object.entries(skills).sort((a, b) => b[1] - a[1]).slice(0, 15);
  
  if (charts['skills']) charts['skills'].destroy();
  
  charts['skills'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(s => s[0]),
      datasets: [{ label: 'Villagers', data: sorted.map(s => s[1]), backgroundColor: COLORS.info }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } }
    }
  });
}

function renderTraitsChart(data) {
  const ctx = document.getElementById('chart-traits');
  if (!ctx) return;
  
  const traits = data.distributions?.top_traits || {};
  const sorted = Object.entries(traits).sort((a, b) => b[1] - a[1]);
  
  if (charts['traits']) charts['traits'].destroy();
  
  charts['traits'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(t => t[0]),
      datasets: [{ label: 'Villagers', data: sorted.map(t => t[1]), backgroundColor: COLORS.warning }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } }
    }
  });
}

function renderAchievementsChart(data) {
  const ctx = document.getElementById('chart-achievements');
  if (!ctx) return;
  
  const achs = data.distributions?.achievements || {};
  const achDefs = data.achievement_definitions || {};
  const sorted = Object.entries(achs).sort((a, b) => b[1] - a[1]);
  
  if (charts['achievements']) charts['achievements'].destroy();
  
  charts['achievements'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(a => achDefs[a[0]]?.name || a[0]),
      datasets: [{ label: 'Earned', data: sorted.map(a => a[1]), backgroundColor: COLORS.success }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } }
    }
  });
}

function renderQuestTypesChart(data) {
  const ctx = document.getElementById('chart-quest-types');
  if (!ctx) return;
  
  const types = data.quests?.by_type || {};
  
  if (charts['quest-types']) charts['quest-types'].destroy();
  
  charts['quest-types'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(types),
      datasets: [{ data: Object.values(types), backgroundColor: COLORS.palette }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderQuestSuccessChart(data) {
  const ctx = document.getElementById('chart-quest-success');
  if (!ctx) return;
  
  const rate = data.quests?.success_rate || {};
  
  if (charts['quest-success']) charts['quest-success'].destroy();
  
  charts['quest-success'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Success', 'Failed'],
      datasets: [{ data: [rate.success || 0, rate.failed || 0], backgroundColor: [COLORS.success, COLORS.danger] }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderEventTypesChart(data) {
  const ctx = document.getElementById('chart-event-types');
  if (!ctx) return;
  
  const types = data.events?.by_type || {};
  
  if (charts['event-types']) charts['event-types'].destroy();
  
  if (Object.keys(types).length === 0) {
    // No events yet
    charts['event-types'] = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['No events yet'],
        datasets: [{ data: [1], backgroundColor: [COLORS.muted] }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
    return;
  }
  
  charts['event-types'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(types),
      datasets: [{ data: Object.values(types), backgroundColor: COLORS.palette }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

// Load analytics on page load
document.addEventListener('DOMContentLoaded', loadAnalytics);

// Refresh analytics every 30 seconds if auto-sim is running
setInterval(() => {
  const status = document.getElementById('auto-status');
  if (status && status.textContent === 'Running') {
    loadAnalytics();
  }
}, 30000);

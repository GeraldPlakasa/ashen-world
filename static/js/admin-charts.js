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

// Chart.js plugin: show percentage labels on doughnut/pie charts
const percentagePlugin = {
  id: 'percentageLabels',
  afterDatasetsDraw(chart) {
    if (chart.config.type !== 'doughnut' && chart.config.type !== 'pie') return;
    const { ctx } = chart;
    const dataset = chart.data.datasets[0];
    if (!dataset) return;
    const total = dataset.data.reduce((s, v) => s + v, 0);
    if (total === 0) return;
    const meta = chart.getDatasetMeta(0);
    meta.data.forEach((arc, i) => {
      const val = dataset.data[i];
      const pct = ((val / total) * 100).toFixed(1);
      if (parseFloat(pct) < 3) return; // skip tiny slices
      const { x, y } = arc.tooltipPosition();
      ctx.save();
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 11px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(pct + '%', x, y);
      ctx.restore();
    });
  }
};
Chart.register(percentagePlugin);

// Year range filter (default 20)
let yearRangeLimit = 20;

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
  document.getElementById('kpi-day').textContent = (c.day != null && c.day !== undefined) ? c.day : '-';
  document.getElementById('kpi-population').textContent = c.population || 0;
  document.getElementById('kpi-dead').textContent = c.dead_count || 0;
  document.getElementById('kpi-treasury').textContent = c.treasury || 0;
  document.getElementById('kpi-users').textContent = c.total_users || 0;

  const r = c.resources || {};
  const setRes = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = (typeof val === 'number') ? val : 0;
  };
  setRes('stockpile-food', r.food);
  setRes('stockpile-wood', r.wood);
  setRes('stockpile-stone', r.stone);
  setRes('stockpile-iron', r.iron);
}

function updateTables(data) {
  // Recent quests
  const questsBody = document.getElementById('recent-quests');
  questsBody.innerHTML = '';
  (data.quests?.history || []).reverse().forEach(q => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${q.year || '-'}</td>
      <td>${q.king_name || '-'}</td>
      <td>${q.type || q.quest_type || '-'}</td>
      <td><span class="status-badge ${q.success ? 'alive' : 'dead'}">${q.success ? 'Success' : 'Failed'}</span></td>
      <td>${q.gold || q.gold_reward || 0}</td>
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
      <td>${e.king_name || e.king || '-'}</td>
      <td>${e.type || e.event_type || '-'}</td>
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
  renderPopulationTimelineChart(data);
  renderJobsChart(data);
  renderOriginsChart(data);
  renderSkillsChart(data);
  renderTraitsChart(data);
  renderAchievementsChart(data);
  renderQuestTypesChart(data);
  renderQuestSuccessChart(data);
  renderEventTypesChart(data);
  renderResourcesYearlyChart(data);
  renderProducerHeadcountChart();
  renderDailyProductionChart();
  renderHealthCurrentChart();
  renderHealthImmunityChart();
  renderJustice(data);
}

// ---------------------------------------------------------------------------
//  Justice tab — KPIs, yearly stacked chart, recent verdicts feed
// ---------------------------------------------------------------------------

function renderJustice(data) {
  const j = data && data.justice;
  if (!j) return;

  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = (val == null) ? 0 : val;
  };
  const ty = j.this_year || {};
  const at = j.all_time  || {};
  setText('kpi-justice-crimes-year', ty.crimes);
  setText('kpi-justice-crimes-all',  at.crimes);
  setText('kpi-justice-trials-year', ty.trials);
  setText('kpi-justice-trials-all',  at.trials);
  // KPI shows gold (the spendable number a king cares about),
  // but the chart below stacks fine COUNTS alongside exile/execution counts.
  setText('kpi-justice-fines-year',  ty.fines_gold);
  setText('kpi-justice-fines-all',   at.fines_gold);
  setText('kpi-justice-fines-count-year', ty.fines_count);
  setText('kpi-justice-fines-count-all',  at.fines_count);
  setText('kpi-justice-exiles-year', ty.exiles);
  setText('kpi-justice-exiles-all',  at.exiles);
  setText('kpi-justice-execs-year',  ty.executions);
  setText('kpi-justice-execs-all',   at.executions);

  renderJusticeYearlyChart(j.history || []);
  renderJusticeFeed(j.recent || []);
}

function renderJusticeYearlyChart(history) {
  const canvas = document.getElementById('chart-justice-yearly');
  if (!canvas) return;
  // Filter to the same year range as the rest of the dashboard.
  const sorted = filterYearlyData(history.slice().reverse());
  const labels = sorted.map(h => 'Yr ' + h.year);
  // Stack VERDICT COUNTS only — fines/exiles/executions live on the same
  // count scale. Gold (fines_gold) is reported via the KPI, not here.
  const fines   = sorted.map(h => h.fines_count || 0);
  const exiles  = sorted.map(h => h.exiles || 0);
  const execs   = sorted.map(h => h.executions || 0);
  const crimes  = sorted.map(h => h.crimes || 0);

  if (window._justiceChart) window._justiceChart.destroy();
  window._justiceChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Fines',      data: fines,  backgroundColor: 'rgba(234,179,8,0.65)',  stack: 'verdicts' },
        { label: 'Exiles',     data: exiles, backgroundColor: 'rgba(245,158,11,0.65)', stack: 'verdicts' },
        { label: 'Executions', data: execs,  backgroundColor: 'rgba(239,68,68,0.75)',  stack: 'verdicts' },
        {
          label: 'Crimes Witnessed',
          data: crimes,
          type: 'line',
          borderColor: '#a3a3a3',
          backgroundColor: 'rgba(163,163,163,0.15)',
          tension: 0.25,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: true, ticks: { color: '#999' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: {
          stacked: true,
          ticks: { color: '#999', precision: 0 },
          grid: { color: 'rgba(255,255,255,0.05)' },
          title: { display: true, text: 'Verdicts', color: '#999' },
          beginAtZero: true,
        },
        y1: {
          position: 'right',
          ticks: { color: '#999', precision: 0 },
          grid: { display: false },
          title: { display: true, text: 'Crimes Witnessed', color: '#999' },
          beginAtZero: true,
        },
      },
      plugins: { legend: { labels: { color: '#ccc' } } },
    },
  });
}

function renderJusticeFeed(recent) {
  const feed = document.getElementById('justice-feed');
  if (!feed) return;
  if (!recent.length) {
    feed.innerHTML = '<div style="color: var(--aw-text-muted);">No justice events yet.</div>';
    return;
  }
  feed.innerHTML = recent.map(e => {
    const imp = parseInt(e.importance || 0, 10);
    const tag = imp >= 5 ? '☠'
              : imp >= 4 ? '🏹'
              : imp >= 3 ? '⚖'
              :            '·';
    return `
      <div style="border-bottom: 1px solid rgba(255,255,255,0.05); padding: 8px 4px;">
        <div style="font-size: 13px; color: var(--aw-text);">${tag} <strong>${e.headline || ''}</strong></div>
        <div style="font-size: 12px; color: var(--aw-text-muted); margin-top: 2px;">Year ${e.year || '?'}, Day ${e.day || '?'} — ${e.body || ''}</div>
      </div>`;
  }).join('');
}

function filterYearlyData(yearly) {
  // Data comes as DESC (newest first) from API
  // We want to filter to last N years, then return in chronological order (oldest first)
  if (!yearly || yearly.length === 0) return [];
  
  // Take first N items (most recent years) if limit is set
  let filtered = yearRangeLimit === 0 ? yearly : yearly.slice(0, yearRangeLimit);
  
  // Reverse to get chronological order: oldest -> newest (left -> right on chart)
  return filtered.slice().reverse();
}

function renderPopulationTreasuryChart(data) {
  const ctx = document.getElementById('chart-population-treasury');
  if (!ctx) return;
  
  // Filter returns chronological order (oldest first, newest last = left to right)
  const yearly = filterYearlyData(data.yearly_stats || []);
  const labels = yearly.map(y => 'Y' + y.year);
  
  // Store king names for tooltip
  const kingNames = yearly.map(y => y.king_name || 'No King');
  
  const treasuryData = yearly.map(y => y.treasury_end || y.treasury_start || 0);
  
  if (charts['population-treasury']) charts['population-treasury'].destroy();

  // Detect king changes for vertical annotation lines
  const kingChangeAnnotations = {};
  for (let i = 1; i < yearly.length; i++) {
    const prevKing = yearly[i - 1].king_name || '';
    const currKing = yearly[i].king_name || '';
    if (currKing && prevKing !== currKing) {
      kingChangeAnnotations['king-' + i] = {
        type: 'line',
        xMin: i,
        xMax: i,
        borderColor: 'rgba(255, 215, 0, 0.6)',
        borderWidth: 2,
        borderDash: [4, 4],
        label: {
          display: true,
          content: '♔ ' + currKing,
          position: 'start',
          backgroundColor: 'rgba(255, 215, 0, 0.15)',
          color: 'rgba(255, 215, 0, 0.9)',
          font: { size: 10 },
          padding: 3
        }
      };
    }
  }

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
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            title: (items) => {
              if (!items.length) return '';
              const idx = items[0].dataIndex;
              return `${labels[idx]} — King: ${kingNames[idx]}`;
            }
          }
        },
        annotation: {
          annotations: kingChangeAnnotations
        }
      },
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
  
  // Filter returns chronological order (oldest first, newest last = left to right)
  const yearly = filterYearlyData(data.yearly_stats || []);
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

function renderPopulationTimelineChart(data) {
  const ctx = document.getElementById('chart-population-timeline');
  if (!ctx) return;
  
  // yearly_stats comes in DESC order (newest first)
  const yearlyDesc = data.yearly_stats || [];
  if (yearlyDesc.length === 0) {
    if (charts['population-timeline']) charts['population-timeline'].destroy();
    return;
  }
  
  // Use population_end directly from DB (accurate snapshot each year)
  // filterYearlyData already returns chronological order (oldest first = left)
  const chronological = filterYearlyData(yearlyDesc);
  const labels = chronological.map(p => 'Y' + p.year);
  const popData = chronological.map(p => p.population_end || 0);
  
  if (charts['population-timeline']) charts['population-timeline'].destroy();
  
  charts['population-timeline'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Alive Population',
        data: popData,
        borderColor: COLORS.primary,
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: COLORS.primary
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: { 
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Population: ${ctx.raw}`
          }
        }
      },
      scales: {
        y: { 
          beginAtZero: false,
          title: { display: true, text: 'Population' }
        }
      }
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
  // Filter out "Child" from job distribution
  const sorted = Object.entries(jobs).filter(([k]) => k.toLowerCase() !== 'child').sort((a, b) => b[1] - a[1]);
  
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
  // Filter out "immigrant" since immigrants become NPC origin
  const filtered = Object.entries(origins).filter(([k]) => k.toLowerCase() !== 'immigrant');
  
  if (charts['origins']) charts['origins'].destroy();
  
  charts['origins'] = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: filtered.map(([k]) => k.charAt(0).toUpperCase() + k.slice(1)),
      datasets: [{ data: filtered.map(([, v]) => v), backgroundColor: COLORS.palette }]
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
  
  // Merge entries that map to the same achievement name
  // (handles cases like count_1, count_2 variants of the same achievement)
  const merged = {};
  for (const [id, count] of Object.entries(achs)) {
    const name = achDefs[id]?.name || id;
    merged[name] = (merged[name] || 0) + count;
  }
  const sorted = Object.entries(merged).sort((a, b) => b[1] - a[1]);
  
  if (charts['achievements']) charts['achievements'].destroy();
  
  charts['achievements'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(a => a[0]),
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

// Year range filter handler
document.addEventListener('DOMContentLoaded', () => {
  const rangeFilter = document.getElementById('year-range-filter');
  if (rangeFilter) {
    rangeFilter.addEventListener('change', (e) => {
      yearRangeLimit = parseInt(e.target.value) || 0;
      loadAnalytics();
    });
  }
});

// ========================
// Players Tab
// ========================
async function loadPlayerStats() {
  try {
    const res = await fetch('/api/player-stats');
    const data = await res.json();
    if (!data.ok) return;
    renderPlayerCharts(data);
  } catch (err) {
    console.error('Failed to load player stats:', err);
  }
}

function renderPlayerCharts(data) {
  // KPIs
  document.getElementById('player-total-users').textContent = data.users?.total || 0;
  document.getElementById('player-total-chars').textContent = data.player_characters?.total || 0;
  document.getElementById('player-total-views').textContent = data.site_stats?.totals?.page_view || 0;
  document.getElementById('player-chars-alive').textContent = data.player_characters?.alive || 0;

  // Page Views Chart
  const pvCtx = document.getElementById('chart-page-views');
  if (pvCtx) {
    const pvData = (data.site_stats?.page_views || []).reverse();
    if (charts['page-views']) charts['page-views'].destroy();
    charts['page-views'] = new Chart(pvCtx, {
      type: 'bar',
      data: {
        labels: pvData.map(d => d.stat_date.slice(5)),  // MM-DD
        datasets: [{ label: 'Views', data: pvData.map(d => d.count), backgroundColor: COLORS.primary }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }

  // Registrations Chart
  const regCtx = document.getElementById('chart-registrations');
  if (regCtx) {
    const regData = (data.users?.by_date || []);
    if (charts['registrations']) charts['registrations'].destroy();
    charts['registrations'] = new Chart(regCtx, {
      type: 'bar',
      data: {
        labels: regData.map(d => d[0].slice(5)),
        datasets: [{ label: 'Registrations', data: regData.map(d => d[1]), backgroundColor: COLORS.success }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
      }
    });
  }

  // Char Creations Chart
  const ccCtx = document.getElementById('chart-char-creations');
  if (ccCtx) {
    const ccData = (data.site_stats?.char_creations || []).reverse();
    if (charts['char-creations']) charts['char-creations'].destroy();
    charts['char-creations'] = new Chart(ccCtx, {
      type: 'bar',
      data: {
        labels: ccData.map(d => d.stat_date.slice(5)),
        datasets: [{ label: 'Characters Created', data: ccData.map(d => d.count), backgroundColor: COLORS.warning }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
      }
    });
  }

  // Player Character Status (alive vs dead)
  const psCtx = document.getElementById('chart-player-status');
  if (psCtx) {
    const pc = data.player_characters || {};
    if (charts['player-status']) charts['player-status'].destroy();
    charts['player-status'] = new Chart(psCtx, {
      type: 'doughnut',
      data: {
        labels: ['Alive', 'Dead'],
        datasets: [{ data: [pc.alive || 0, pc.dead || 0], backgroundColor: [COLORS.success, COLORS.danger] }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } }
      }
    });
  }

  // Recent users table
  const usersBody = document.getElementById('recent-users');
  if (usersBody) {
    usersBody.innerHTML = '';
    (data.users?.recent || []).forEach(u => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${u.username}</td><td>${u.created_at || '-'}</td>`;
      usersBody.appendChild(tr);
    });
  }
}

// Load player stats when Players tab is clicked
document.querySelectorAll('.tab-btn').forEach(btn => {
  if (btn.dataset.tab === 'players') {
    btn.addEventListener('click', () => loadPlayerStats());
  }
});

// Load analytics on page load
document.addEventListener('DOMContentLoaded', loadAnalytics);

// Refresh analytics every 30 seconds if auto-sim is running
setInterval(() => {
  const status = document.getElementById('auto-status');
  if (status && status.textContent === 'Running') {
    loadAnalytics();
  }
}, 30000);

// ============================================================================
//  RESOURCES TAB
// ============================================================================

const RESOURCE_COLORS = {
  food:  '#e0a96d',
  wood:  '#8b5a3c',
  stone: '#9aa0a6',
  iron:  '#a0522d',
};

function renderResourcesYearlyChart(data) {
  const ctx = document.getElementById('chart-resources-yearly');
  if (!ctx) return;

  const yearly = filterYearlyData(data.yearly_stats || []);
  const labels = yearly.map(r => 'Y' + r.year);
  const kingNames = yearly.map(r => r.king_name || 'No King');
  const food  = yearly.map(r => r.stock_food_end  || 0);
  const wood  = yearly.map(r => r.stock_wood_end  || 0);
  const stone = yearly.map(r => r.stock_stone_end || 0);
  const iron  = yearly.map(r => r.stock_iron_end  || 0);

  // King-change vertical annotations — same pattern as Population chart
  const kingChangeAnnotations = {};
  for (let i = 1; i < yearly.length; i++) {
    const prevKing = yearly[i - 1].king_name || '';
    const currKing = yearly[i].king_name || '';
    if (currKing && prevKing !== currKing) {
      kingChangeAnnotations['king-' + i] = {
        type: 'line',
        xMin: i,
        xMax: i,
        borderColor: 'rgba(255, 215, 0, 0.6)',
        borderWidth: 2,
        borderDash: [4, 4],
        label: {
          display: true,
          content: '♔ ' + currKing,
          position: 'start',
          backgroundColor: 'rgba(255, 215, 0, 0.15)',
          color: 'rgba(255, 215, 0, 0.9)',
          font: { size: 10 },
          padding: 3,
        },
      };
    }
  }

  if (charts.resourcesYearly) charts.resourcesYearly.destroy();
  charts.resourcesYearly = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Food',  data: food,  borderColor: RESOURCE_COLORS.food,  backgroundColor: RESOURCE_COLORS.food  + '33', tension: 0.25, fill: false, pointRadius: 2 },
        { label: 'Wood',  data: wood,  borderColor: RESOURCE_COLORS.wood,  backgroundColor: RESOURCE_COLORS.wood  + '33', tension: 0.25, fill: false, pointRadius: 2 },
        { label: 'Stone', data: stone, borderColor: RESOURCE_COLORS.stone, backgroundColor: RESOURCE_COLORS.stone + '33', tension: 0.25, fill: false, pointRadius: 2 },
        { label: 'Iron',  data: iron,  borderColor: RESOURCE_COLORS.iron,  backgroundColor: RESOURCE_COLORS.iron  + '33', tension: 0.25, fill: false, pointRadius: 2 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true, padding: 14 } },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            title: (items) => {
              if (!items.length) return '';
              const idx = items[0].dataIndex;
              return `${labels[idx]} — King: ${kingNames[idx]}`;
            },
          },
        },
        annotation: {
          annotations: kingChangeAnnotations,
        },
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Units in stockpile' } },
        x: { title: { display: false } },
      },
    },
  });
}

function renderProducerHeadcountChart() {
  const ctx = document.getElementById('chart-producer-headcount');
  if (!ctx) return;

  const rd = window.AW_RESOURCES_DASHBOARD || {};
  const rows = rd.production_rows || [];
  const labels = rows.map(r => r.job);
  const counts = rows.map(r => r.count);

  // Color each bar by its primary resource (parse "per_villager" like "+12 food")
  const bgColors = rows.map(r => {
    const m = (r.per_villager || '').match(/(food|wood|stone|iron)/);
    return m ? RESOURCE_COLORS[m[1]] : COLORS.primary;
  });

  if (charts.producerHeadcount) charts.producerHeadcount.destroy();
  charts.producerHeadcount = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Villagers in this job',
        data: counts,
        backgroundColor: bgColors,
        borderWidth: 0,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              const row = rows[ctx.dataIndex];
              return row ? 'Output / worker: ' + row.per_villager : '';
            },
          },
        },
      },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0 } },
      },
    },
  });
}

function renderDailyProductionChart() {
  const ctx = document.getElementById('chart-daily-production');
  if (!ctx) return;

  const rd = window.AW_RESOURCES_DASHBOARD || {};
  const ed = rd.expected_daily || {};
  const labels = ['Food', 'Wood', 'Stone', 'Iron'];
  const values = [ed.food || 0, ed.wood || 0, ed.stone || 0, ed.iron || 0];
  const colors = [RESOURCE_COLORS.food, RESOURCE_COLORS.wood, RESOURCE_COLORS.stone, RESOURCE_COLORS.iron];

  if (charts.dailyProduction) charts.dailyProduction.destroy();
  charts.dailyProduction = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Units / day (max)',
        data: values,
        backgroundColor: colors,
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Units / day' } },
      },
    },
  });
}

// =========================================================================
//  Health tab charts
// =========================================================================

function renderHealthCurrentChart() {
  const ctx = document.getElementById('chart-health-current');
  if (!ctx) return;

  const hd = window.AW_HEALTH_DASHBOARD || {};
  const meta = hd.disease_meta || {};
  const current = hd.current_by_disease || {};
  const slugs = Object.keys(meta);

  const labels = slugs.map(s => `${meta[s].icon || ''} ${meta[s].name || s}`.trim());
  const data = slugs.map(s => current[s] || 0);
  const colors = slugs.map(s => meta[s].color || '#6366f1');

  const totalSick = data.reduce((a, b) => a + b, 0);
  const healthyCount = Math.max(0, (hd.total_alive || 0) - totalSick);

  if (charts.healthCurrent) charts.healthCurrent.destroy();
  charts.healthCurrent = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: [...labels, 'Healthy'],
      datasets: [{
        data: [...data, healthyCount],
        backgroundColor: [...colors, '#22c55e'],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${ctx.parsed} villagers`,
          },
        },
      },
      cutout: '55%',
    },
  });
}

// Update the Health-tab KPI text/badge from the latest health dashboard,
// without rebuilding any HTML. Called from refreshAllCharts().
function updateHealthKPIs(hd) {
  if (!hd) return;
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.textContent !== String(val)) {
      el.textContent = val;
      el.classList.add('refresh-flash');
      setTimeout(() => el.classList.remove('refresh-flash'), 700);
    }
  };
  set('kpi-health-sick', hd.total_sick);
  const sub = document.getElementById('kpi-health-sick-sub');
  if (sub) sub.textContent = `${hd.sick_pct}% of ${hd.total_alive} alive`;
  set('kpi-health-healers', (hd.healers || []).length);
  set('kpi-health-immune', hd.total_immune);

  const status = document.getElementById('kpi-health-status');
  if (status) {
    status.textContent = hd.outbreak_status;
    // Swap status-badge modifier class
    ['alive', 'damaged', 'dead'].forEach(c => status.classList.remove(c));
    if (hd.outbreak_class) status.classList.add(hd.outbreak_class);
  }
}

// In-page refresh: re-fetch all dashboard data and re-render charts/KPIs
// WITHOUT a browser reload (so the active tab stays selected).
async function refreshAllCharts() {
  const btn = document.getElementById('btn-refresh-charts');
  const label = btn ? btn.querySelector('.refresh-label') : null;
  if (btn) {
    btn.classList.add('is-loading');
    if (label) label.textContent = 'Refreshing…';
  }

  try {
    // 1) Analytics-driven charts (Overview, Population, Quests, Players tabs)
    await loadAnalytics();

    // 2) Resources + Health dashboards (snapshot endpoint)
    const res = await fetch('/admin/snapshot.json', { credentials: 'same-origin' });
    if (res.ok) {
      const data = await res.json();
      if (data && data.ok) {
        if (data.resources) window.AW_RESOURCES_DASHBOARD = data.resources;
        if (data.health) window.AW_HEALTH_DASHBOARD = data.health;
        renderProducerHeadcountChart();
        renderDailyProductionChart();
        renderHealthCurrentChart();
        renderHealthImmunityChart();
        updateHealthKPIs(data.health);
      }
    } else {
      console.warn('Snapshot fetch returned', res.status);
    }
  } catch (err) {
    console.error('Refresh failed:', err);
  } finally {
    if (btn) {
      btn.classList.remove('is-loading');
      if (label) label.textContent = 'Refresh';
    }
  }
}

// Bind the refresh button once DOM is ready.
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('btn-refresh-charts');
  if (btn) btn.addEventListener('click', refreshAllCharts);
});

function renderHealthImmunityChart() {
  const ctx = document.getElementById('chart-health-immunity');
  if (!ctx) return;

  const hd = window.AW_HEALTH_DASHBOARD || {};
  const meta = hd.disease_meta || {};
  const current = hd.current_by_disease || {};
  const immune = hd.immune_by_disease || {};
  const totalAlive = Math.max(1, hd.total_alive || 0);
  const slugs = Object.keys(meta);

  const labels = slugs.map(s => `${meta[s].icon || ''} ${meta[s].name || s}`.trim());
  const immuneData = slugs.map(s => immune[s] || 0);
  const sickData = slugs.map(s => current[s] || 0);
  const susceptibleData = slugs.map((s, i) => Math.max(0, totalAlive - immuneData[i] - sickData[i]));
  const colors = slugs.map(s => meta[s].color || '#6366f1');

  if (charts.healthImmunity) charts.healthImmunity.destroy();
  charts.healthImmunity = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Immune',
          data: immuneData,
          backgroundColor: '#22c55e',
          borderWidth: 0,
          stack: 'pop',
        },
        {
          label: 'Currently Sick',
          data: sickData,
          backgroundColor: colors,
          borderWidth: 0,
          stack: 'pop',
        },
        {
          label: 'Susceptible',
          data: susceptibleData,
          backgroundColor: '#374151',
          borderWidth: 0,
          stack: 'pop',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              const pct = ((ctx.parsed.y / totalAlive) * 100).toFixed(1);
              return `${pct}% of alive`;
            },
          },
        },
      },
      scales: {
        x: { stacked: true },
        y: { stacked: true, beginAtZero: true, max: totalAlive, title: { display: true, text: 'Villagers' } },
      },
    },
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const table = document.getElementById("characters-table");
  // Even if table is missing, we still want auto controls, so don't return early.
  const tbody = table ? table.tBodies[0] : null;
  const sortableHeaders = table
    ? table.querySelectorAll("thead th.sortable")
    : [];
  const searchInput = document.getElementById("table-search");
  const onlyAliveToggle = document.getElementById("only-alive-toggle");

  // --- Global characters cache (for admin pinned view) ---
  let awCharacters = window.AW_CHARACTERS || [];
  let idToChar = new Map();

  // --- Graveyard / archived cache (optional) ---
  // Expect window.AW_GRAVEYARD to be an object: { "12": {id:12,name:"...", gender:"...", ...}, ... }
  let awGraveyard = window.AW_GRAVEYARD || {};
  let idToGrave = new Map();

  // Pinned villager elements (only exist on admin page)
  const pinned = {
    card: document.getElementById("admin-pinned-card"),
    nameEl: document.getElementById("pinned-name"),
    subtitleEl: document.getElementById("pinned-subtitle"),
    metaTopEl: document.getElementById("pinned-meta-top"),
    metaBottomEl: document.getElementById("pinned-meta-bottom"),
    statsRow: document.getElementById("pinned-stats-row"),
    extraRow: document.getElementById("pinned-extra-row"),
    relRow: document.getElementById("pinned-rel-row"),
    jobEl: document.getElementById("pinned-job"),
    ageEl: document.getElementById("pinned-age"),
    levelEl: document.getElementById("pinned-level"),
    hpEl: document.getElementById("pinned-hp"),
    spouseEl: document.getElementById("pinned-spouse"),
    traitsEl: document.getElementById("pinned-traits"),
    lastActionEl: document.getElementById("pinned-last-action"),
    bondsList: document.getElementById("pinned-bonds"),
    conflictsList: document.getElementById("pinned-conflicts"),
    genderEl: document.getElementById("pinned-gender"),
    motherEl: document.getElementById("pinned-mother"),
    fatherEl: document.getElementById("pinned-father"),
    childrenEl: document.getElementById("pinned-children"),
  };

  let selectedRow = null;

  function rebuildIndex() {
    idToChar = new Map((awCharacters || []).map((c) => [Number(c.id), c]));
  }

  function rebuildGraveyardIndex() {
    idToGrave = new Map();
    const src = awGraveyard && typeof awGraveyard === "object" ? awGraveyard : {};
    for (const [k, v] of Object.entries(src)) {
      const id = parseInt(k, 10);
      if (!id || Number.isNaN(id) || id <= 0) continue;
      idToGrave.set(id, v || {});
    }
  }

  rebuildIndex();
  rebuildGraveyardIndex();

  // -------------------------------------------------------------------------
  //  Sorting
  // -------------------------------------------------------------------------

  /**
   * Clear sort state (direction + visual indicators) from all sortable headers.
   */
  function clearSortIndicators() {
    sortableHeaders.forEach((header) => {
      header.dataset.sortDir = "";
      header.classList.remove("sort-asc", "sort-desc");
    });
  }

  /**
   * Sort table rows based on the clicked header and its column index.
   * @param {HTMLTableCellElement} header - The header cell that was clicked.
   * @param {number} columnIndex - Index of the column to sort by.
   */
  function sortTableByColumn(header, columnIndex) {
    if (!tbody) return;

    const isNumeric = header.classList.contains("num");

    // Toggle direction between asc / desc
    const newDirection = header.dataset.sortDir === "asc" ? "desc" : "asc";

    // Reset all headers and set the current one as active
    clearSortIndicators();
    header.dataset.sortDir = newDirection;
    header.classList.add(newDirection === "asc" ? "sort-asc" : "sort-desc");

    // Collect all rows in the tbody
    const rows = Array.from(tbody.querySelectorAll("tr"));

    // Sort rows based on the target column
    rows.sort((rowA, rowB) => {
      const cellA = rowA.children[columnIndex]?.textContent.trim() || "";
      const cellB = rowB.children[columnIndex]?.textContent.trim() || "";

      let comparisonResult;

      if (isNumeric) {
        // Remove commas (e.g. "1,234") and parse as float
        const aNum = parseFloat(cellA.replace(/,/g, "")) || 0;
        const bNum = parseFloat(cellB.replace(/,/g, "")) || 0;
        comparisonResult = aNum - bNum;
      } else {
        // String comparison for text columns
        comparisonResult = cellA.localeCompare(cellB);
      }

      // Reverse result if direction is descending
      return newDirection === "asc" ? comparisonResult : -comparisonResult;
    });

    // Re-append rows in the new order.
    rows.forEach((row) => tbody.appendChild(row));
  }

  // -------------------------------------------------------------------------
  //  Filters (search + alive-only)
  // -------------------------------------------------------------------------

  /**
   * Combined filter for:
   * - search query
   * - "Alive only" toggle
   */
  function applyFilters() {
    if (!tbody) return;

    const query = (searchInput?.value || "").trim().toLowerCase();
    const aliveOnly = !!(onlyAliveToggle && onlyAliveToggle.checked);

    const rows = tbody.querySelectorAll("tr");

    rows.forEach((row) => {
      let visible = true;

      // Text search
      if (query) {
        const rowText = row.textContent.toLowerCase();
        if (!rowText.includes(query)) {
          visible = false;
        }
      }

      // Alive-only filter => hide dead rows
      if (aliveOnly && row.classList.contains("aw-row-dead")) {
        visible = false;
      }

      row.style.display = visible ? "" : "none";
    });
  }

  function setupSearchFilter() {
    if (!searchInput || !tbody) return;

    searchInput.addEventListener("input", () => {
      applyFilters();
    });
  }

  // === Initialize sorting ===
  sortableHeaders.forEach((header, index) => {
    header.addEventListener("click", () => sortTableByColumn(header, index));
  });

  // === Initialize search filter ===
  setupSearchFilter();

  // === Initialize alive-only toggle (if present on this page) ===
  if (onlyAliveToggle && tbody) {
    onlyAliveToggle.addEventListener("change", () => {
      applyFilters();
    });
  }

  // -------------------------------------------------------------------------
  //  Helpers
  // -------------------------------------------------------------------------

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function textOrDash(v) {
    return v === null || v === undefined || v === "" ? "–" : String(v);
  }

  /**
   * Resolve ID into a person object from:
   * 1) active villagers
   * 2) graveyard (archived)
   * 3) fallback unknown
   *
   * status: "alive" | "dead" | "archived" | "unknown"
   */
  function resolvePersonById(idRaw) {
    const id = parseInt(idRaw, 10);
    if (!id || Number.isNaN(id) || id <= 0) return null;

    const active = idToChar.get(id);
    if (active) {
      const alive = active.alive !== false;
      return {
        id,
        name: active.name || `#${id}`,
        gender: active.gender || null,
        status: alive ? "alive" : "dead",
      };
    }

    const gy = idToGrave.get(id);
    if (gy) {
      return {
        id,
        name: gy.name || `#${id}`,
        gender: gy.gender || null,
        status: "archived",
      };
    }

    return { id, name: `#${id}`, gender: null, status: "unknown" };
  }

  /**
   * Backward-compatible: returns a string label.
   * - alive: "Name"
   * - dead: "Name (dead)"
   * - archived: "Name (archived)"
   * - unknown: "#id"
   */
  function resolveNameById(idRaw) {
    const p = resolvePersonById(idRaw);
    if (!p) return null;

    if (p.status === "dead") return `${p.name} (dead)`;
    if (p.status === "archived") return `${p.name} (archived)`;
    return p.name;
  }

  function personHtmlStrong(p, { unknownLabel = "Unknown", noneLabel = "None" } = {}) {
    if (!p) return `<span class="text-muted">${escapeHtml(noneLabel)}</span>`;

    const name = escapeHtml(p.name || `#${p.id}`);

    if (p.status === "dead") {
      return `<strong>${name}</strong> <span class="text-danger">(dead)</span>`;
    }
    if (p.status === "archived") {
      return `<strong>${name}</strong> <span class="text-muted">(archived)</span>`;
    }
    if (p.status === "unknown") {
      return `<strong>${name}</strong> <span class="text-muted">(${escapeHtml(unknownLabel)})</span>`;
    }
    return `<strong>${name}</strong>`;
  }

  function normalizeChildrenIds(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;

    if (typeof raw === "string" && raw.trim()) {
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }
    return [];
  }

  function resetPinnedCard() {
    if (!pinned.card || !pinned.nameEl) return;

    pinned.nameEl.textContent = "No villager selected";
    if (pinned.subtitleEl) {
      pinned.subtitleEl.textContent =
        "Click a row in the table below to inspect their details.";
    }
    if (pinned.metaTopEl) pinned.metaTopEl.textContent = "";
    if (pinned.metaBottomEl) pinned.metaBottomEl.textContent = "";

    if (pinned.statsRow) pinned.statsRow.style.display = "none";
    if (pinned.extraRow) pinned.extraRow.style.display = "none";
    if (pinned.relRow) pinned.relRow.style.display = "none";

    if (pinned.bondsList) pinned.bondsList.innerHTML = "";
    if (pinned.conflictsList) pinned.conflictsList.innerHTML = "";

    if (pinned.spouseEl) pinned.spouseEl.textContent = "-";
    if (pinned.genderEl) pinned.genderEl.textContent = "-";

    if (pinned.motherEl) pinned.motherEl.textContent = "-";
    if (pinned.fatherEl) pinned.fatherEl.textContent = "-";
    if (pinned.childrenEl) pinned.childrenEl.textContent = "-";
  }

  function normalizeRelationships(relRaw) {
    if (!relRaw) return {};
    if (typeof relRaw === "string") {
      try {
        const parsed = JSON.parse(relRaw);
        return parsed && typeof parsed === "object" ? parsed : {};
      } catch {
        return {};
      }
    }
    if (typeof relRaw === "object") return relRaw;
    return {};
  }

  function buildRelationshipSummary(v) {
    const relObj = normalizeRelationships(v.relationships);
    const entries = [];

    Object.entries(relObj).forEach(([otherIdStr, scoreVal]) => {
      const otherId = parseInt(otherIdStr, 10);
      if (!otherId) return;

      const otherInfo = resolvePersonById(otherId);
      if (!otherInfo) return;

      const score = parseInt(scoreVal, 10);
      if (Number.isNaN(score)) return;

      const g1 = v.gender;
      const g2 = otherInfo.gender;

      const g1ok = g1 === "Male" || g1 === "Female";
      const g2ok = g2 === "Male" || g2 === "Female";
      const isMfPair =
        g1ok && g2ok && ((g1 === "Male" && g2 === "Female") || (g1 === "Female" && g2 === "Male"));

      let label = null;
      if (isMfPair && score >= 80) {
        label = "love";
      } else if (score >= 65) {
        label = "bestfriend";
      } else if (score >= 30) {
        label = "friend";
      } else if (score <= -60) {
        label = "enemy";
      } else if (score <= -30) {
        label = "rival";
      } else {
        label = null;
      }

      if (!label) return;

      entries.push({
        id: otherId,
        name: otherInfo.name || `#${otherId}`,
        score,
        label,
        status: otherInfo.status,
      });
    });

    const positives = entries
      .filter((e) => e.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);

    const negatives = entries
      .filter((e) => e.score < 0)
      .sort((a, b) => a.score - b.score)
      .slice(0, 3);

    return { positives, negatives };
  }

  function fillList(listEl, items) {
    if (!listEl) return;
    listEl.innerHTML = "";

    if (!items.length) {
      const li = document.createElement("li");
      li.className = "text-muted";
      li.textContent = "None recorded yet.";
      listEl.appendChild(li);
      return;
    }

    items.forEach((r) => {
      const li = document.createElement("li");

      let suffix = "";
      if (r.status === "dead") suffix = " (dead)";
      else if (r.status === "archived") suffix = " (archived)";

      li.textContent = `${r.name}${suffix} (${r.label}, ${r.score})`;
      listEl.appendChild(li);
    });
  }

  function updatePinnedCard(villager) {
    if (!pinned.card || !pinned.nameEl) return;

    // Title + subtitle
    pinned.nameEl.textContent = villager.name || `#${villager.id}`;
    const origin =
      villager.origin === "player" ? "Player character" : "NPC villager";
    if (pinned.subtitleEl) {
      pinned.subtitleEl.textContent = `${origin} • ID ${villager.id}`;
    }

    // Meta
    const alive = villager.alive !== false;
    if (pinned.metaTopEl) {
      pinned.metaTopEl.textContent = alive ? "Status: Alive" : "Status: Dead";
    }

    const rep = villager.rep ?? 0;
    const coins = villager.coins ?? 0;
    if (pinned.metaBottomEl) {
      pinned.metaBottomEl.textContent = `REP ${rep} • Coins ${coins}`;
    }

    // Stats block
    if (pinned.statsRow) pinned.statsRow.style.display = "";
    if (pinned.extraRow) pinned.extraRow.style.display = "";

    if (pinned.jobEl) pinned.jobEl.textContent = textOrDash(villager.job);
    if (pinned.ageEl) pinned.ageEl.textContent = textOrDash(villager.age);
    if (pinned.genderEl) pinned.genderEl.textContent = textOrDash(villager.gender);

    if (pinned.levelEl) {
      pinned.levelEl.textContent = `Lv ${textOrDash(
        villager.level
      )} (${textOrDash(villager.exp)} EXP)`;
    }

    if (pinned.hpEl) {
      pinned.hpEl.textContent = `HP ${textOrDash(
        villager.hp
      )} / Hunger ${textOrDash(villager.hunger)}`;
    }

    // --- Spouse ---
    if (pinned.spouseEl) {
      const sidRaw = villager.spouseId ?? villager.spouse_id ?? 0;
      const spouseInfo = resolvePersonById(sidRaw);

      if (!spouseInfo) {
        pinned.spouseEl.innerHTML = '<span class="text-muted">None</span>';
      } else {
        pinned.spouseEl.innerHTML = personHtmlStrong(spouseInfo, {
          unknownLabel: "unknown",
          noneLabel: "None",
        });
      }
    }

    // --- Mother / Father ---
    if (pinned.motherEl) {
      const motherInfo = resolvePersonById(villager.motherId);
      pinned.motherEl.innerHTML = motherInfo
        ? personHtmlStrong(motherInfo, { unknownLabel: "unknown" })
        : '<span class="text-muted">Unknown</span>';
    }

    if (pinned.fatherEl) {
      const fatherInfo = resolvePersonById(villager.fatherId);
      pinned.fatherEl.innerHTML = fatherInfo
        ? personHtmlStrong(fatherInfo, { unknownLabel: "unknown" })
        : '<span class="text-muted">Unknown</span>';
    }

    // --- Children list ---
    if (pinned.childrenEl) {
      const childIds = normalizeChildrenIds(villager.childrenIds);

      if (!childIds.length) {
        pinned.childrenEl.innerHTML = '<span class="text-muted">None</span>';
      } else {
        const infos = childIds
          .map((cid) => resolvePersonById(cid))
          .filter(Boolean);

        const labels = infos.map((p) => {
          if (p.status === "dead") return `${p.name} (dead)`;
          if (p.status === "archived") return `${p.name} (archived)`;
          return p.name;
        });

        const MAX_SHOW = 6;
        const shown = labels.slice(0, MAX_SHOW);
        const more = labels.length - shown.length;

        const listHtml = shown
          .map(
            (n) =>
              `<span class="badge rounded-pill bg-light text-dark border me-1 mb-1">${escapeHtml(
                n
              )}</span>`
          )
          .join("");

        pinned.childrenEl.innerHTML = `
          <div class="d-flex flex-wrap align-items-center">
            ${listHtml}
            ${
              more > 0
                ? `<span class="text-muted small ms-1">+${more} more</span>`
                : ""
            }
          </div>`;
      }
    }

    if (pinned.traitsEl) {
      pinned.traitsEl.textContent = textOrDash(villager.traits);
    }
    if (pinned.lastActionEl) {
      pinned.lastActionEl.textContent = textOrDash(villager.last_action);
    }

    // Relationships summary
    const { positives, negatives } = buildRelationshipSummary(villager);
    if (pinned.relRow) pinned.relRow.style.display = "";
    fillList(pinned.bondsList, positives);
    fillList(pinned.conflictsList, negatives);
  }

  // -------------------------------------------------------------------------
  //  Rebuild table body from characters JSON
  // -------------------------------------------------------------------------
  function rebuildTable(characters) {
    if (!tbody || !Array.isArray(characters)) return;

    awCharacters = characters;
    rebuildIndex();

    // Detect if this table expects an "Origin" column (admin page does)
    const hasOriginCol = !!(
      table && table.querySelector('thead th[data-key="origin"]')
    );

    let html = "";

    characters.forEach((c) => {
      const alive = c.alive !== false; // treat missing as alive
      const classes = ["aw-row-clickable"];
      if (!alive) classes.push("aw-row-dead");
      const rowClass = classes.join(" ");
      const nameClass = alive ? "" : "aw-name-dead";

      const statusBadge = alive
        ? '<span class="badge rounded-pill bg-success-subtle text-success border border-success-subtle aw-status-badge">Alive</span>'
        : '<span class="badge rounded-pill bg-danger-subtle text-danger border border-danger-subtle aw-status-badge">Dead</span>';

      const originLabel = c.origin === "player" ? "Player" : "NPC";

      html += `
        <tr class="${rowClass}" data-char-id="${c.id}">
          <td class="${nameClass}">${escapeHtml(c.name)}</td>
          <td>${escapeHtml(c.gender)}</td>
          <td>${escapeHtml(c.job)}</td>
          <td class="text-end">${c.coins ?? 0}</td>
          <td class="text-end">${c.age ?? 0}</td>
          <td class="text-end">${c.int ?? 0}</td>
          <td class="text-end">${c.rep ?? 0}</td>
          <td class="text-end">${c.level ?? 0}</td>
          <td class="text-end">${c.exp ?? 0}</td>
          <td class="text-end">${c.atk ?? 0}</td>
          <td class="text-end">${c.def ?? 0}</td>
          <td class="text-end">${c.hp ?? 0}</td>
          <td class="text-end">${c.hunger ?? 0}</td>
          <td class="aw-traits-cell">${escapeHtml(c.traits || "")}</td>
          <td>${escapeHtml(c.last_action || "")}</td>

          ${hasOriginCol ? `<td>${escapeHtml(originLabel)}</td>` : ""}

          <td>${statusBadge}</td>
        </tr>
      `;
    });

    tbody.innerHTML = html;

    selectedRow = null;
    resetPinnedCard();

    applyFilters();
  }

  // -------------------------------------------------------------------------
  //  Rebuild admin buildings card from JSON
  // -------------------------------------------------------------------------
  function renderAdminBuildings(buildings) {
    const wrapper = document.getElementById("admin-buildings-wrapper");
    if (!wrapper) return; // not on this page

    if (!Array.isArray(buildings) || buildings.length === 0) {
      wrapper.innerHTML = `
        <div class="text-muted small">
          No buildings yet. Use the treasury and King’s traits to shape the village.
        </div>
      `;
      return;
    }

    // Built first, then by name
    const sorted = [...buildings].sort((a, b) => {
      const ab = a.built ? 0 : 1;
      const bb = b.built ? 0 : 1;
      if (ab !== bb) return ab - bb;
      return (a.name || "").localeCompare(b.name || "");
    });

    let html = '<div class="row g-2">';
    for (const b of sorted) {
      const built = !!b.built;
      const lvl = b.level || 0;
      const hpRaw = typeof b.health === "number" ? b.health : 0;
      const hp = Math.max(0, Math.min(100, hpRaw));

      let barClass = "bg-success";
      if (hp <= 25) barClass = "bg-danger";
      else if (hp <= 60) barClass = "bg-warning";

      html += `
        <div class="col-12 col-md-6 col-lg-4">
          <div class="border rounded-3 p-2 small bg-body">
            <div class="d-flex justify-content-between align-items-center mb-1">
              <span class="${built ? "" : "text-muted"}">
                ${escapeHtml(b.name || "")}
              </span>
              ${
                built
                  ? `<span class="badge rounded-pill bg-success-subtle text-success border border-success-subtle">
                       Lv ${lvl}
                     </span>`
                  : `<span class="badge rounded-pill bg-light text-muted border border-secondary-subtle">
                       Not built
                     </span>`
              }
            </div>

            ${
              built
                ? `
                  <div class="d-flex justify-content-between mb-1">
                    <span class="text-muted">Health</span>
                    <span>${hp}%</span>
                  </div>
                  <div class="progress" style="height: 6px;">
                    <div class="progress-bar ${barClass}"
                         role="progressbar"
                         style="width: ${hp}%;"
                         aria-valuenow="${hp}"
                         aria-valuemin="0"
                         aria-valuemax="100"></div>
                  </div>
                `
                : `
                  <div class="text-muted fst-italic">
                    No structure yet. Can be constructed once the treasury has enough coins.
                  </div>
                `
            }
          </div>
        </div>
      `;
    }
    html += "</div>";

    wrapper.innerHTML = html;
  }

  // -------------------------------------------------------------------------
  //  Auto-simulation controls (Start Auto / Stop Auto)
  // -------------------------------------------------------------------------

  const startBtn = document.getElementById("auto-start");
  const stopBtn = document.getElementById("auto-stop");
  const intervalInput = document.getElementById("auto-interval");
  const statusSpan = document.getElementById("auto-status");
  const yearSpan = document.getElementById("current-year");
  const daySpan = document.getElementById("current-day");

  let autoTimer = null;

  function updateStatus(text) {
    if (statusSpan) {
      statusSpan.textContent = text;
    }
  }

  function stopAuto() {
    if (autoTimer !== null) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
    if (startBtn) startBtn.disabled = false;
    if (stopBtn) stopBtn.disabled = true;
    updateStatus("Auto: stopped");
  }

  async function fetchState() {
    try {
      const resp = await fetch("/api/state", {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      });

      if (!resp.ok) {
        console.error("Failed to fetch /api/state:", resp.status);
        updateStatus("Auto: error fetching state");
        stopAuto();
        return;
      }

      const data = await resp.json();

      // Update year/day display
      if (typeof data.year === "number" && yearSpan) {
        yearSpan.textContent = data.year;
      }
      if (typeof data.day === "number" && daySpan) {
        daySpan.textContent = data.day;
      }

      // Update graveyard if provided by API (optional)
      if (data.graveyard_index && typeof data.graveyard_index === "object") {
        awGraveyard = data.graveyard_index;
        window.AW_GRAVEYARD = awGraveyard;
        rebuildGraveyardIndex();
      }

      // Rebuild table with the updated characters
      if (Array.isArray(data.characters)) {
        rebuildTable(data.characters);
      }

      // Update admin buildings if present
      if (Array.isArray(data.buildings)) {
        renderAdminBuildings(data.buildings);
      }

      updateStatus(
        "Auto: refreshing (Year " + data.year + ", Day " + data.day + ")"
      );
    } catch (err) {
      console.error(err);
      updateStatus("Auto: error, stopped");
      stopAuto();
    }
  }

  if (startBtn && stopBtn && intervalInput) {
    startBtn.addEventListener("click", () => {
      const sec = parseFloat(intervalInput.value) || 3;
      const ms = Math.max(1, sec) * 1000;

      // If already running, clear previous timer first
      if (autoTimer !== null) {
        clearInterval(autoTimer);
      }

      // Trigger one refresh immediately
      fetchState();

      // Then repeat
      autoTimer = setInterval(fetchState, ms);

      startBtn.disabled = true;
      stopBtn.disabled = false;
      updateStatus("Auto: refreshing every " + sec + " seconds");
    });

    stopBtn.addEventListener("click", () => {
      stopAuto();
    });
  }

  // -------------------------------------------------------------------------
  //  Row click -> pinned card (admin only)
  // -------------------------------------------------------------------------

  const hasPinnedCard = !!pinned.card && !!tbody;

  if (hasPinnedCard) {
    // Initialize card to empty state
    resetPinnedCard();

    tbody.addEventListener("click", (evt) => {
      const tr = evt.target.closest("tr[data-char-id]");
      if (!tr) return;

      const idAttr = tr.getAttribute("data-char-id");
      const id = parseInt(idAttr, 10);
      if (!idAttr || Number.isNaN(id)) return;

      const villager = idToChar.get(id);
      if (!villager) return;

      if (selectedRow) {
        selectedRow.classList.remove("aw-row-selected");
      }
      selectedRow = tr;
      selectedRow.classList.add("aw-row-selected");

      updatePinnedCard(villager);
    });
  }

  // -------------------------------------------------------------------------
  //  Landing pinned character collapse: persist open/close state
  // -------------------------------------------------------------------------
  const pinnedCollapseEl = document.getElementById("pinnedCharCollapse");
  const pinnedToggleEl = document.getElementById("pinnedCharToggle");

  if (pinnedCollapseEl && pinnedToggleEl && window.bootstrap?.Collapse) {
    const KEY = "aw_pinned_char_open";
    const saved = localStorage.getItem(KEY); // "1" (open) or "0" (closed)

    const bs = new bootstrap.Collapse(pinnedCollapseEl, { toggle: false });

    // Default open in HTML, but override if user previously closed
    if (saved === "1") bs.show();
    else bs.hide();

    pinnedCollapseEl.addEventListener("shown.bs.collapse", () => {
      localStorage.setItem(KEY, "1");
    });

    pinnedCollapseEl.addEventListener("hidden.bs.collapse", () => {
      localStorage.setItem(KEY, "0");
    });
  }

  // Initial filter pass (in case table is already rendered)
  applyFilters();
});

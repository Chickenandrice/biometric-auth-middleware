(function () {
  const STORAGE_API = "bioauth_dashboard_api_base";
  const STORAGE_MOCK = "bioauth_dashboard_use_mock";
  const MOCK_USERS = "bioauth_mock_users_v1";
  const MOCK_LOGS = "bioauth_mock_logs_v1";

  const Charts = window.BioAuthCharts;

  let attemptsChart = null;
  let outcomeChart = null;
  let events = [];
  let people = [];
  let stats = null;
  let currentView = "overview";

  function $(id) {
    return document.getElementById(id);
  }

  function loadPrefs() {
    const api = localStorage.getItem(STORAGE_API);
    const mockRaw = localStorage.getItem(STORAGE_MOCK);
    if (api) $("api-base").value = api;
    if (mockRaw !== null) $("use-mock").checked = mockRaw === "1";
  }

  function savePrefs() {
    localStorage.setItem(STORAGE_API, $("api-base").value.trim());
    localStorage.setItem(STORAGE_MOCK, $("use-mock").checked ? "1" : "0");
  }

  function useMock() {
    return $("use-mock").checked;
  }

  function apiBase() {
    return $("api-base").value.trim().replace(/\/$/, "");
  }

  function showError(msg) {
    const el = $("flash-error");
    if (!msg) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function randomPick(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  function seedMockStore() {
    if (localStorage.getItem(MOCK_USERS)) return;
    const now = Date.now();
    const users = [
      {
        id: 1,
        username: "jdoe",
        display_name: "Jane Doe",
        email: "jane@example.com",
        status: "active",
        created_at: new Date(now - 86400000 * 14).toISOString(),
        enrolled_at: new Date(now - 86400000 * 10).toISOString(),
      },
      {
        id: 2,
        username: "pending.user",
        display_name: "New Hire",
        email: null,
        status: "pending",
        created_at: new Date(now - 86400000).toISOString(),
        enrolled_at: null,
      },
    ];
    const logs = [];
    const devices = ["edge-pi-01", "edge-pi-02", "ble-band"];
    const channels = ["BLE", "HTTP"];
    for (let i = 0; i < 40; i++) {
      const ok = Math.random() > 0.1;
      logs.push({
        id: i + 1,
        ts: new Date(now - i * 90000 - Math.random() * 40000).toISOString(),
        user: randomPick(["jdoe", "demo", "jdoe"]),
        device: randomPick(devices),
        channel: randomPick(channels),
        result: ok ? "success" : "failure",
        score: ok
          ? Number((0.82 + Math.random() * 0.15).toFixed(3))
          : Number((0.3 + Math.random() * 0.3).toFixed(3)),
      });
    }
    localStorage.setItem(MOCK_USERS, JSON.stringify(users));
    localStorage.setItem(MOCK_LOGS, JSON.stringify(logs));
  }

  function readMockUsers() {
    seedMockStore();
    try {
      return JSON.parse(localStorage.getItem(MOCK_USERS) || "[]");
    } catch {
      return [];
    }
  }

  function writeMockUsers(list) {
    localStorage.setItem(MOCK_USERS, JSON.stringify(list));
  }

  function readMockLogs() {
    seedMockStore();
    try {
      return JSON.parse(localStorage.getItem(MOCK_LOGS) || "[]");
    } catch {
      return [];
    }
  }

  function nextMockUserId(users) {
    return users.reduce((m, u) => Math.max(m, u.id), 0) + 1;
  }

  function mockHourlyFromLogs(logs) {
    const labels = [];
    const success = [];
    const failure = [];
    for (let h = 23; h >= 0; h--) {
      const d = new Date();
      d.setMinutes(0, 0, 0);
      d.setHours(d.getHours() - h);
      labels.push(
        d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      );
      success.push(0);
      failure.push(0);
    }
    const dayAgo = Date.now() - 24 * 3600000;
    for (const row of logs) {
      const t = new Date(row.ts).getTime();
      if (t < dayAgo) continue;
      const d = new Date(row.ts);
      d.setMinutes(0, 0, 0);
      const slot = Math.floor((Date.now() - d.getTime()) / 3600000);
      const idx = 23 - Math.min(23, Math.max(0, slot));
      if (row.result === "success") success[idx]++;
      else if (row.result === "failure") failure[idx]++;
    }
    return { labels, success, failure };
  }

  function mockStatsFromData(userList, logList) {
    const dayAgo = Date.now() - 24 * 3600000;
    const recent = logList.filter((l) => new Date(l.ts).getTime() >= dayAgo);
    const failed = recent.filter((l) => l.result === "failure").length;
    const ok = recent.filter((l) => l.result === "success").length;
    const auths = recent.length;
    return {
      enrolledUsers: userList.filter((u) => u.status === "active").length,
      pendingUsers: userList.filter((u) => u.status === "pending").length,
      auths24h: auths,
      successRate: auths ? ok / auths : 1,
      failed24h: failed,
    };
  }

  function mockOutcomeFromLogs(logList) {
    const dayAgo = Date.now() - 24 * 3600000;
    let success = 0;
    let failure = 0;
    let challenge = 0;
    for (const e of logList) {
      if (new Date(e.ts).getTime() < dayAgo) continue;
      if (e.result === "success") success++;
      else if (e.result === "failure") failure++;
      else challenge++;
    }
    return { success, failure, challenge };
  }

  function lastAuthForUser(username, logList) {
    let best = null;
    for (const l of logList) {
      if (l.user !== username) continue;
      const t = new Date(l.ts).getTime();
      if (!best || t > best) best = t;
    }
    return best ? new Date(best).toISOString() : null;
  }

  async function fetchJson(path, options) {
    const base = apiBase();
    if (!base) throw new Error("Set API base URL or enable mock mode.");
    const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
    const res = await fetch(url, {
      headers: {
        Accept: "application/json",
        ...(options && options.body
          ? { "Content-Type": "application/json" }
          : {}),
      },
      ...options,
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || `${res.status} ${res.statusText}`);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return null;
  }

  async function loadOverviewBundle() {
    savePrefs();
    const mock = useMock();
    $("conn-status").classList.toggle("is-live", !mock);
    $("conn-status").innerHTML = mock
      ? '<span class="status-dot"></span> Mock data'
      : '<span class="status-dot"></span> Live API';

    if (mock) {
      const users = readMockUsers();
      const logs = readMockLogs().sort(
        (a, b) => new Date(b.ts) - new Date(a.ts)
      );
      events = logs.slice(0, 50).map((l) => ({
        ts: l.ts,
        user: l.user,
        device: l.device,
        channel: l.channel,
        result: l.result,
        score: l.score,
      }));
      stats = mockStatsFromData(users, logs);
      const hourly = mockHourlyFromLogs(logs);
      const outcome = mockOutcomeFromLogs(logs);
      return { stats, hourly, events, outcome, error: null };
    }

    try {
      const statusRes = await fetchJson("/api/status");
      const logsRes = await fetchJson("/api/logs?limit=100");
      stats = mapRemoteStats(statusRes);
      events = mapRemoteEvents(logsRes);
      const hourly =
        statusRes && statusRes.hourly
          ? statusRes.hourly
          : { labels: [], success: [], failure: [] };
      const outcome =
        statusRes && statusRes.outcome_mix
          ? statusRes.outcome_mix
          : mockOutcomeFromLogs(
              events.map((e) => ({ ts: e.ts, result: e.result }))
            );
      return {
        stats,
        hourly,
        events,
        outcome,
        error: null,
      };
    } catch (e) {
      console.warn(e);
      return {
        stats: {
          enrolledUsers: 0,
          pendingUsers: 0,
          auths24h: 0,
          successRate: 0,
          failed24h: 0,
        },
        hourly: { labels: [], success: [], failure: [] },
        events: [],
        outcome: { success: 0, failure: 0, challenge: 0 },
        error: String(e.message || e),
      };
    }
  }

  function mapRemoteStats(res) {
    if (!res || typeof res !== "object") {
      return {
        enrolledUsers: 0,
        pendingUsers: 0,
        auths24h: 0,
        successRate: 0,
        failed24h: 0,
      };
    }
    return {
      enrolledUsers: res.enrolled_users ?? res.enrolledUsers ?? 0,
      pendingUsers: res.pending_users ?? res.pendingUsers ?? 0,
      auths24h: res.auths_24h ?? res.auths24h ?? 0,
      successRate: Number(
        res.success_rate ?? res.successRate ?? res.match_rate ?? 0
      ),
      failed24h: res.failed_24h ?? res.failed24h ?? 0,
    };
  }

  function mapRemoteEvents(res) {
    if (!res) return [];
    const items = Array.isArray(res) ? res : res.items || res.logs || [];
    return items.map((row) => ({
      ts: row.ts || row.timestamp || row.time,
      user: row.user || row.username || row.user_id || "—",
      device: row.device || row.device_id || "—",
      channel: row.channel || row.transport || "—",
      result: String(row.result || row.outcome || "success").toLowerCase(),
      score: typeof row.score === "number" ? row.score : null,
    }));
  }

  function mapRemotePeople(list) {
    return list.map((u) => ({
      id: u.id,
      username: u.username,
      display_name: u.display_name ?? u.displayName ?? u.username,
      email: u.email ?? null,
      status: String(u.status || "pending").toLowerCase(),
      created_at: u.created_at || u.createdAt,
      enrolled_at: u.enrolled_at ?? u.enrolledAt ?? null,
      last_auth_at: u.last_auth_at ?? u.lastAuthAt ?? null,
    }));
  }

  async function loadPeople() {
    showError("");
    if (useMock()) {
      const logs = readMockLogs();
      people = readMockUsers().map((u) => ({
        ...u,
        last_auth_at: lastAuthForUser(u.username, logs),
      }));
      return;
    }
    try {
      const raw = await fetchJson("/api/users");
      const list = Array.isArray(raw) ? raw : raw.items || [];
      people = mapRemotePeople(list);
    } catch (e) {
      showError("People: " + (e.message || e));
      people = [];
    }
  }

  function renderStats() {
    const el = $("stat-cards");
    if (!stats) {
      el.innerHTML = "";
      return;
    }
    const sr = (stats.successRate * 100).toFixed(1);
    const pending =
      stats.pendingUsers != null ? stats.pendingUsers : "—";
    el.innerHTML = `
      <div class="stat-card">
        <div class="stat-label">Enrolled</div>
        <div class="stat-value">${Number(stats.enrolledUsers).toLocaleString()}</div>
        <div class="stat-delta">Active templates</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Pending enrollment</div>
        <div class="stat-value">${pending}</div>
        <div class="stat-delta">Awaiting device</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Auths (24h)</div>
        <div class="stat-value">${Number(stats.auths24h).toLocaleString()}</div>
        <div class="stat-delta">Success rate ${sr}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Failed (24h)</div>
        <div class="stat-value">${Number(stats.failed24h)}</div>
        <div class="stat-delta ${stats.failed24h > 12 ? "negative" : ""}">Review spikes</div>
      </div>`;
  }

  function statusBadge(status) {
    const s = String(status).toLowerCase();
    if (s === "active")
      return '<span class="badge badge-ok">Enrolled</span>';
    if (s === "pending")
      return '<span class="badge badge-warn">Pending</span>';
    if (s === "disabled")
      return '<span class="badge badge-muted">Disabled</span>';
    return `<span class="badge badge-muted">${escapeHtml(s)}</span>`;
  }

  function renderPeopleTable() {
    const tbody = $("people-body");
    if (!people.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="mono-cell" style="color:var(--muted)">No users yet. Add a person to start enrollment.</td></tr>`;
      return;
    }
    tbody.innerHTML = people
      .map((u) => {
        const last =
          u.last_auth_at == null
            ? "—"
            : new Date(u.last_auth_at).toLocaleString();
        const canComplete = u.status === "pending";
        const canDisable = u.status === "active" || u.status === "pending";
        return `<tr>
        <td>${escapeHtml(u.display_name)}</td>
        <td class="mono-cell">${escapeHtml(u.username)}</td>
        <td>${statusBadge(u.status)}</td>
        <td class="mono-cell">${escapeHtml(last)}</td>
        <td class="row-actions">
          ${
            canComplete
              ? `<button type="button" class="btn btn-sm btn-primary" data-action="enroll" data-id="${u.id}">Complete enrollment</button>`
              : ""
          }
          ${
            canDisable
              ? `<button type="button" class="btn btn-sm btn-danger" data-action="disable" data-id="${u.id}">Disable</button>`
              : ""
          }
        </td>
      </tr>`;
      })
      .join("");

    tbody.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = Number(btn.getAttribute("data-id"));
        if (btn.getAttribute("data-action") === "enroll") completeEnrollment(id);
        else disableUser(id);
      });
    });
  }

  function renderEventsTable(bodyId, list, extraChannel) {
    const tbody = $(bodyId);
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="${extraChannel ? 6 : 5}" style="color:var(--muted)">No events.</td></tr>`;
      return;
    }
    tbody.innerHTML = list
      .map((e) => {
        const t = new Date(e.ts);
        const timeStr = t.toLocaleString();
        const badgeClass =
          e.result === "success"
            ? "badge-ok"
            : e.result === "failure"
              ? "badge-fail"
              : "badge-warn";
        const score =
          e.score == null ? "—" : `<span class="mono-cell">${e.score}</span>`;
        const ch = extraChannel
          ? `<td class="mono-cell">${escapeHtml(String(e.channel))}</td>`
          : "";
        return `<tr>
        <td class="mono-cell">${escapeHtml(timeStr)}</td>
        <td>${escapeHtml(String(e.user))}</td>
        <td class="mono-cell">${escapeHtml(String(e.device))}</td>
        ${ch}
        <td><span class="badge ${badgeClass}">${escapeHtml(e.result)}</span></td>
        <td>${score}</td>
      </tr>`;
      })
      .join("");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderSettingsApi() {
    $("settings-api").innerHTML = `
      <p>With <strong>Use mock data</strong> off, the dashboard calls your API (enable CORS for this origin):</p>
      <ul>
        <li><code>GET /api/status</code> — aggregates; optional <code>hourly</code>, <code>outcome_mix</code></li>
        <li><code>GET /api/logs?limit=…</code> — <code>{ "items": [ … ] }</code> or a JSON array</li>
        <li><code>GET /api/users</code></li>
        <li><code>POST /api/users</code> — <code>{ "username", "display_name", "email?" }</code></li>
        <li><code>POST /api/users/{id}/enroll</code></li>
        <li><code>PATCH /api/users/{id}</code> — <code>{ "status": "disabled" }</code></li>
      </ul>
      <p>BLE / edge ingestion belongs in the <strong>Python SDK</strong>, not this UI.</p>
    `;
  }

  function bindCharts(data) {
    Charts.destroyChart(attemptsChart);
    Charts.destroyChart(outcomeChart);
    const h = data.hourly || { labels: [], success: [], failure: [] };
    attemptsChart = Charts.createAttemptsChart(
      $("chart-attempts"),
      h.labels,
      h.success,
      h.failure
    );
    outcomeChart = Charts.createOutcomeChart($("chart-outcomes"), data.outcome);
  }

  async function refreshOverview() {
    $("btn-refresh").disabled = true;
    showError("");
    const data = await loadOverviewBundle();
    renderStats();
    renderEventsTable("events-body", data.events, false);
    renderEventsTable("log-body", data.events, true);
    bindCharts(data);
    if (data.error) {
      showError("Live API unavailable: " + data.error);
    } else {
      showError("");
    }
    if (currentView === "overview") {
      if (data.error) {
        $("page-desc").textContent =
          "Charts may be empty until the API responds.";
      } else {
        $("page-desc").textContent = useMock()
          ? "Local mock store — add users under People."
          : "Connected to your BioAuth API.";
      }
    }
    $("btn-refresh").disabled = false;
  }

  async function refreshPeople() {
    await loadPeople();
    renderPeopleTable();
  }

  async function refreshAll() {
    await refreshOverview();
    await refreshPeople();
  }

  function setView(name) {
    currentView = name;
    document.querySelectorAll(".nav-link").forEach((a) => {
      a.classList.toggle("active", a.dataset.view === name);
    });
    document.querySelectorAll("[data-view-panel]").forEach((p) => {
      p.classList.toggle("hidden", p.dataset.viewPanel !== name);
    });
    const titles = {
      overview: ["Overview", "System snapshot and recent auth events."],
      people: [
        "People",
        "Provision users and complete enrollment (pending → enrolled).",
      ],
      activity: ["Activity", "Search and review verification attempts."],
      settings: ["Settings", "API contract for live mode."],
    };
    const [title, desc] = titles[name] || titles.overview;
    $("page-title").textContent = title;
    $("page-desc").textContent = desc;
  }

  function filterLog() {
    const q = ($("log-filter").value || "").trim().toLowerCase();
    const filtered = !q
      ? events
      : events.filter(
          (e) =>
            String(e.user).toLowerCase().includes(q) ||
            String(e.device).toLowerCase().includes(q)
        );
    renderEventsTable("log-body", filtered, true);
  }

  function openModal() {
    $("modal-add-user").classList.remove("hidden");
    $("inp-display-name").value = "";
    $("inp-username").value = "";
    $("inp-email").value = "";
    $("inp-display-name").focus();
  }

  function closeModal() {
    $("modal-add-user").classList.add("hidden");
  }

  async function submitAddUser(ev) {
    ev.preventDefault();
    showError("");
    const display_name = $("inp-display-name").value.trim();
    const username = $("inp-username").value.trim().toLowerCase();
    const email = $("inp-email").value.trim() || null;
    if (!display_name || !username) return;

    if (useMock()) {
      const users = readMockUsers();
      if (users.some((u) => u.username === username)) {
        showError("That username already exists.");
        return;
      }
      const row = {
        id: nextMockUserId(users),
        username,
        display_name,
        email,
        status: "pending",
        created_at: new Date().toISOString(),
        enrolled_at: null,
      };
      users.push(row);
      writeMockUsers(users);
      closeModal();
      await refreshAll();
      setView("people");
      return;
    }

    try {
      await fetchJson("/api/users", {
        method: "POST",
        body: JSON.stringify({ username, display_name, email }),
      });
      closeModal();
      await refreshAll();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  async function completeEnrollment(userId) {
    showError("");
    if (useMock()) {
      const users = readMockUsers();
      const u = users.find((x) => x.id === userId);
      if (!u || u.status !== "pending") return;
      u.status = "active";
      u.enrolled_at = new Date().toISOString();
      writeMockUsers(users);
      await refreshAll();
      return;
    }
    try {
      await fetchJson(`/api/users/${userId}/enroll`, { method: "POST" });
      await refreshAll();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  async function disableUser(userId) {
    showError("");
    if (useMock()) {
      const users = readMockUsers();
      const u = users.find((x) => x.id === userId);
      if (!u) return;
      u.status = "disabled";
      writeMockUsers(users);
      await refreshAll();
      return;
    }
    try {
      await fetchJson(`/api/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "disabled" }),
      });
      await refreshAll();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  document.querySelectorAll(".nav-link").forEach((a) => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      setView(a.dataset.view || "overview");
    });
  });

  $("btn-refresh").addEventListener("click", () => refreshAll());
  $("use-mock").addEventListener("change", () => refreshAll());
  $("api-base").addEventListener("change", () => refreshAll());
  $("log-filter").addEventListener("input", filterLog);

  $("btn-add-user").addEventListener("click", openModal);
  $("form-add-user").addEventListener("submit", submitAddUser);
  document.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  loadPrefs();
  renderSettingsApi();
  setView("overview");
  refreshAll();
})();

(function () {
  const STORAGE_API = "bioauth_dashboard_api_base";
  const STORAGE_API_KEY = "bioauth_dashboard_api_key";
  const STORAGE_MOCK = "bioauth_dashboard_use_mock";
  const MOCK_USERS = "bioauth_mock_users_v1";
  const MOCK_LOGS = "bioauth_mock_logs_v1";
  const STORAGE_BLE_SERVICE = "bioauth_ble_service_uuid";
  const STORAGE_BLE_CHAR = "bioauth_ble_char_uuid";
  const STORAGE_BLE_PREFIX = "bioauth_ble_name_prefix";
  const DEFAULT_BLE_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
  const DEFAULT_BLE_CHAR = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";

  const Charts = window.BioAuthCharts;

  let attemptsChart = null;
  let outcomeChart = null;
  let events = [];
  let people = [];
  let stats = null;
  let liveUsersSnapshot = null;
  let liveEventsSnapshot = null;

  let bleDevice = null;
  let bleChar = null;
  let bleNotifyHandler = null;
  let bleServiceUuid = "";
  let bleCharUuid = "";
  let bleNotifications = 0;
  let bleRelayOk = 0;
  let bleForwardChain = Promise.resolve();
  let blePendingEnrollUserId = null;
  let blePendingEnrollName = null;
  let refreshInFlight = false;
  const AUTO_REFRESH_MS = 5000;

  function $(id) {
    return document.getElementById(id);
  }

  function scrollToSection(id) {
    const el = $(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /**
   * Backend often returns UTC as naive ISO strings (no "Z"). JavaScript treats
   * those as *local* wall time, which shifts clocks by your UTC offset (e.g. 4h
   * ahead in Eastern). If the string looks like UTC ISO without a zone, append Z.
   */
  function parseApiTime(value) {
    if (value == null || value === "") return new Date(NaN);
    if (typeof value === "number" && Number.isFinite(value)) {
      return new Date(value);
    }
    const s = String(value).trim();
    if (!s) return new Date(NaN);
    if (/Z$/i.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)) return new Date(s);
    if (/^\d{4}-\d{2}-\d{2}T/.test(s)) return new Date(s + "Z");
    return new Date(s);
  }

  function formatLocalTime(value) {
    const d = parseApiTime(value);
    return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
  }

  function loadPrefs() {
    const api = localStorage.getItem(STORAGE_API);
    const key = localStorage.getItem(STORAGE_API_KEY);
    const mockRaw = localStorage.getItem(STORAGE_MOCK);
    if (api) $("api-base").value = api;
    $("api-key").value = key || "dev-api-key-001";
    if (mockRaw !== null) $("use-mock").checked = mockRaw === "1";
  }

  function savePrefs() {
    localStorage.setItem(STORAGE_API, $("api-base").value.trim());
    localStorage.setItem(STORAGE_API_KEY, $("api-key").value.trim());
    localStorage.setItem(STORAGE_MOCK, $("use-mock").checked ? "1" : "0");
  }

  function apiKey() {
    return $("api-key").value.trim();
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
      const t = parseApiTime(row.ts).getTime();
      if (t < dayAgo) continue;
      const d = parseApiTime(row.ts);
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
    const recent = logList.filter((l) => parseApiTime(l.ts).getTime() >= dayAgo);
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
      if (parseApiTime(e.ts).getTime() < dayAgo) continue;
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
      const t = parseApiTime(l.ts).getTime();
      if (!best || t > best) best = t;
    }
    return best ? new Date(best).toISOString() : null;
  }

  async function fetchJson(path, options) {
    const base = apiBase();
    if (!base) throw new Error("Set API base URL or enable mock mode.");
    const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
    const opts = options || {};
    const headers = {
      Accept: "application/json",
      ...opts.headers,
    };
    const key = apiKey();
    if (key) headers["X-API-Key"] = key;
    if (opts.body && typeof opts.body === "string") {
      headers["Content-Type"] = "application/json";
    }
    const res = await fetch(url, { ...opts, headers });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || `${res.status} ${res.statusText}`);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return null;
  }

  async function fetchHealth() {
    const base = apiBase();
    if (!base) throw new Error("Set API base URL.");
    const url = `${base}/health`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`GET /health → ${res.status}`);
    return res.json();
  }

  function auditLogsToEvents(items) {
    const rows = Array.isArray(items) ? items : [];
    return rows
      .map((row) => {
        const dec = String(row.decision || "").toLowerCase();
        let result = "challenge";
        if (dec === "allow") result = "success";
        else if (dec === "deny") result = "failure";
        return {
          ts: row.timestamp || row.ts,
          user: row.user_id || row.user || "—",
          device: row.transport_mode || "—",
          channel: row.transport_mode || "gateway",
          result,
          score:
            row.similarity_score != null
              ? row.similarity_score
              : row.confidence != null
                ? row.confidence
                : null,
        };
      })
      .sort((a, b) => parseApiTime(b.ts) - parseApiTime(a.ts));
  }

  function statsFromGatewayUsersAndEvents(usersList, allEvents) {
    const enrolledUsers = usersList.filter((u) => u.enrolled).length;
    const pendingUsers = usersList.filter((u) => !u.enrolled).length;
    const dayAgo = Date.now() - 24 * 3600000;
    const recent = allEvents.filter((e) => parseApiTime(e.ts).getTime() >= dayAgo);
    const ok = recent.filter((e) => e.result === "success").length;
    const fail = recent.filter((e) => e.result === "failure").length;
    return {
      enrolledUsers,
      pendingUsers,
      auths24h: recent.length,
      successRate: recent.length ? ok / recent.length : 1,
      failed24h: fail,
    };
  }

  function hourlyFromEvents(evts) {
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
    for (const row of evts) {
      const t = parseApiTime(row.ts).getTime();
      if (t < dayAgo) continue;
      const d = parseApiTime(row.ts);
      d.setMinutes(0, 0, 0);
      const slot = Math.floor((Date.now() - d.getTime()) / 3600000);
      const idx = 23 - Math.min(23, Math.max(0, slot));
      if (row.result === "success") success[idx]++;
      else if (row.result === "failure") failure[idx]++;
    }
    return { labels, success, failure };
  }

  function outcomeFromEvents(evts) {
    const dayAgo = Date.now() - 24 * 3600000;
    let success = 0;
    let failure = 0;
    let challenge = 0;
    for (const e of evts) {
      if (parseApiTime(e.ts).getTime() < dayAgo) continue;
      if (e.result === "success") success++;
      else if (e.result === "failure") failure++;
      else challenge++;
    }
    return { success, failure, challenge };
  }

  function mapGatewayPeople(usersList, allEvents) {
    const lastByUser = {};
    for (const e of allEvents) {
      const u = e.user;
      const t = parseApiTime(e.ts).getTime();
      if (!Number.isFinite(t)) continue;
      if (lastByUser[u] == null || t > lastByUser[u]) lastByUser[u] = t;
    }
    return usersList.map((u) => ({
      id: u.user_id,
      username: u.user_id,
      display_name: u.display_name || u.user_id,
      email: null,
      status: u.enrolled ? "active" : "pending",
      created_at: u.created_at,
      enrolled_at: u.enrolled_at,
      last_auth_at:
        lastByUser[u.user_id] != null
          ? new Date(lastByUser[u.user_id]).toISOString()
          : null,
    }));
  }

  async function loadOverviewBundle() {
    savePrefs();
    const mock = useMock();
    $("conn-status").classList.toggle("is-live", !mock);
    $("conn-status").innerHTML = mock
      ? '<span class="status-dot"></span> Mock data'
      : '<span class="status-dot"></span> Live API';

    if (mock) {
      liveUsersSnapshot = null;
      liveEventsSnapshot = null;
      const users = readMockUsers();
      const logs = readMockLogs().sort(
        (a, b) => parseApiTime(b.ts) - parseApiTime(a.ts)
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
      await fetchHealth();
      const [statusRes, usersRaw, logsRaw] = await Promise.all([
        fetchJson("/status"),
        fetchJson("/users"),
        fetchJson("/logs?limit=200"),
      ]);
      const usersList = Array.isArray(usersRaw) ? usersRaw : [];
      const allEvents = auditLogsToEvents(logsRaw);
      liveUsersSnapshot = usersList;
      liveEventsSnapshot = allEvents;
      events = allEvents.slice(0, 50);
      stats = statsFromGatewayUsersAndEvents(usersList, allEvents);
      if (statusRes && typeof statusRes.edge_connected === "boolean") {
        stats.edgeConnected = statusRes.edge_connected;
      }
      const hourly = hourlyFromEvents(allEvents);
      const outcome = outcomeFromEvents(allEvents);
      return {
        stats,
        hourly,
        events,
        outcome,
        error: null,
      };
    } catch (e) {
      console.warn(e);
      liveUsersSnapshot = null;
      liveEventsSnapshot = null;
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
      let usersRaw = liveUsersSnapshot;
      let ev = liveEventsSnapshot;
      if (!usersRaw) usersRaw = await fetchJson("/users");
      if (!ev) ev = auditLogsToEvents(await fetchJson("/logs?limit=300"));
      const list = Array.isArray(usersRaw) ? usersRaw : [];
      people = mapGatewayPeople(list, ev);
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
    const edgeNote =
      typeof stats.edgeConnected === "boolean"
        ? stats.edgeConnected
          ? "Edge transport: connected"
          : "Edge transport: unreachable"
        : null;
    el.innerHTML = `
      <div class="stat-card">
        <div class="stat-label">Enrolled</div>
        <div class="stat-value">${Number(stats.enrolledUsers).toLocaleString()}</div>
        <div class="stat-delta">Active templates${edgeNote ? ` · ${edgeNote}` : ""}</div>
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
            : formatLocalTime(u.last_auth_at);
        const canComplete = u.status === "pending";
        const canRevoke = useMock()
          ? u.status === "active" || u.status === "pending"
          : u.status === "active";
        const uid = encodeURIComponent(String(u.id));
        const username = String(u.username);
        const isBleTarget =
          blePendingEnrollUserId && blePendingEnrollUserId === username;
        const rowClass = isBleTarget ? " tr--ble-target" : "";
        const bleBtn =
          canComplete && !useMock()
            ? `<button type="button" class="btn btn-sm btn-primary" data-action="ble-enroll" data-user-id="${uid}" data-display-name="${encodeURIComponent(u.display_name || "")}">Record enrollment</button>`
            : canComplete && useMock()
              ? `<span class="mono-cell" style="color:var(--muted);font-size:0.8rem">Use live API for BLE</span>`
              : "";
        return `<tr class="${rowClass.trim()}">
        <td>${escapeHtml(u.display_name)}</td>
        <td class="mono-cell">${escapeHtml(u.username)}</td>
        <td>${statusBadge(u.status)}</td>
        <td class="mono-cell">${escapeHtml(last)}</td>
        <td class="row-actions">
          ${bleBtn}
          ${
            canComplete
              ? `<button type="button" class="btn btn-sm" data-action="enroll" data-user-id="${uid}">Enroll via server</button>`
              : ""
          }
          ${
            canRevoke
              ? `<button type="button" class="btn btn-sm btn-danger" data-action="unenroll" data-user-id="${uid}">Revoke enrollment</button>`
              : ""
          }
          <button type="button" class="btn btn-sm btn-danger" data-action="delete-user" data-user-id="${uid}" data-display-name="${encodeURIComponent(u.display_name || "")}">Delete</button>
        </td>
      </tr>`;
      })
      .join("");

    tbody.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const uid = decodeURIComponent(btn.getAttribute("data-user-id") || "");
        const action = btn.getAttribute("data-action");
        if (action === "enroll") completeEnrollment(uid);
        else if (action === "unenroll") revokeEnrollment(uid);
        else if (action === "delete-user") {
          const dn = decodeURIComponent(
            btn.getAttribute("data-display-name") || ""
          );
          deletePerson(uid, dn);
        } else if (action === "ble-enroll") {
          const dn = decodeURIComponent(
            btn.getAttribute("data-display-name") || ""
          );
          setBleEnrollTarget(uid, dn || uid);
          renderPeopleTable();
          showError("");
          scrollToSection("section-enroll");
        }
      });
    });
  }

  function formatScoreForDisplay(v) {
    if (v == null || v === "") return null;
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    return n.toFixed(4);
  }

  function renderEventsTable(bodyId, list, extraChannel) {
    const tbody = $(bodyId);
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="${extraChannel ? 6 : 5}" style="color:var(--muted)">No events.</td></tr>`;
      return;
    }
    tbody.innerHTML = list
      .map((e) => {
        const timeStr = formatLocalTime(e.ts);
        const badgeClass =
          e.result === "success"
            ? "badge-ok"
            : e.result === "failure"
              ? "badge-fail"
              : "badge-warn";
        const scoreFmt = formatScoreForDisplay(e.score);
        const score =
          scoreFmt == null
            ? "—"
            : `<span class="mono-cell">${escapeHtml(scoreFmt)}</span>`;
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

  function normalizeUuid(s) {
    const t = String(s).trim().toLowerCase().replace(/-/g, "");
    if (!/^[0-9a-f]{32}$/.test(t)) return String(s).trim();
    return `${t.slice(0, 8)}-${t.slice(8, 12)}-${t.slice(12, 16)}-${t.slice(16, 20)}-${t.slice(20)}`;
  }

  function bleSupported() {
    return !!(navigator.bluetooth && navigator.bluetooth.requestDevice);
  }

  function loadBlePrefs() {
    $("inp-ble-service").value =
      localStorage.getItem(STORAGE_BLE_SERVICE) || DEFAULT_BLE_SERVICE;
    $("inp-ble-char").value =
      localStorage.getItem(STORAGE_BLE_CHAR) || DEFAULT_BLE_CHAR;
    $("inp-ble-name-prefix").value = localStorage.getItem(STORAGE_BLE_PREFIX) || "";
  }

  function saveBlePrefs() {
    localStorage.setItem(STORAGE_BLE_SERVICE, $("inp-ble-service").value.trim());
    localStorage.setItem(STORAGE_BLE_CHAR, $("inp-ble-char").value.trim());
    localStorage.setItem(STORAGE_BLE_PREFIX, $("inp-ble-name-prefix").value.trim());
  }

  function clearBleEnrollTarget() {
    blePendingEnrollUserId = null;
    blePendingEnrollName = null;
    updateEnrollBanner();
  }

  function setBleEnrollTarget(userId, displayName) {
    blePendingEnrollUserId = userId;
    blePendingEnrollName = displayName || userId;
    updateEnrollBanner();
  }

  function updateEnrollBanner() {
    const el = $("ble-enroll-banner");
    if (!el) return;
    if (!blePendingEnrollUserId) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.classList.remove("hidden");
    const name = escapeHtml(blePendingEnrollName || blePendingEnrollUserId);
    const uid = escapeHtml(blePendingEnrollUserId);
    el.innerHTML = `Recording enrollment for <strong>${name}</strong> (<code class="inline-code">${uid}</code>). When the device sends a sample, it is stored and used to enroll this person. <button type="button" class="btn btn-ghost btn-sm" id="btn-clear-ble-target">Cancel</button>`;
    const btn = $("btn-clear-ble-target");
    if (btn) {
      btn.addEventListener("click", () => {
        clearBleEnrollTarget();
        renderPeopleTable();
      });
    }
  }

  function updateBleQuickPill() {
    const pill = $("ble-quick-pill");
    const text = $("ble-quick-text");
    if (!pill || !text) return;
    if (useMock() || !bleSupported()) {
      pill.classList.add("hidden");
      return;
    }
    pill.classList.remove("hidden");
    const connected = !!(bleDevice && bleDevice.gatt && bleDevice.gatt.connected);
    const devName = bleDevice && (bleDevice.name || bleDevice.id);
    if (connected && devName) {
      pill.classList.add("is-connected");
      text.textContent = `Connected · ${devName}`;
    } else {
      pill.classList.remove("is-connected");
      text.textContent = "Bluetooth off";
    }
  }

  function initBlePanel() {
    $("ble-unsupported").classList.toggle("hidden", bleSupported());
    loadBlePrefs();
    updateBleMockBanner();
    updateBleQuickPill();
    const pill = $("ble-quick-pill");
    if (pill) {
      pill.style.cursor = "pointer";
      pill.addEventListener("click", () => scrollToSection("section-enroll"));
    }
  }

  function updateBleMockBanner() {
    $("ble-mock-hint").classList.toggle("hidden", !useMock());
    updateBleQuickPill();
  }

  function setBleStatus(t) {
    $("ble-line-status").textContent = t;
    updateBleQuickPill();
  }
  function setBleDeviceLine(t) {
    $("ble-line-device").textContent = t;
  }
  function updateBleCounters() {
    $("ble-line-count").textContent = String(bleNotifications);
    $("ble-line-relay-ok").textContent = String(bleRelayOk);
  }

  function showBleError(msg) {
    const el = $("ble-last-error");
    if (!msg) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function setBleLastResponse(obj) {
    $("ble-last-response").textContent =
      obj == null
        ? "—"
        : typeof obj === "string"
          ? obj
          : JSON.stringify(obj, null, 2);
  }

  function setBleLastCapture(obj) {
    const el = $("ble-last-capture");
    if (!el) return;
    el.textContent =
      obj == null
        ? "—"
        : typeof obj === "string"
          ? obj
          : JSON.stringify(obj, null, 2);
  }

  async function relayEnrollmentFromCapture(parsed) {
    if (useMock()) throw new Error("Turn off mock data to save enrollment to the server.");
    if (!blePendingEnrollUserId) {
      throw new Error("No one selected for enrollment.");
    }
    const body = { ...parsed, user_id: blePendingEnrollUserId };
    return fetchJson("/relay/enrollment", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  function queueEnrollmentRelay(parsed) {
    bleForwardChain = bleForwardChain
      .then(() => relayEnrollmentFromCapture(parsed))
      .then((res) => {
        bleRelayOk++;
        updateBleCounters();
        setBleLastResponse(res);
        showBleError("");
        clearBleEnrollTarget();
        refreshPeople().catch(() => {});
      })
      .catch((e) => {
        showBleError(String(e.message || e));
        setBleLastResponse({ error: String(e.message || e) });
      });
  }

  function onBleNotification(ev) {
    const value = ev.target.value;
    if (!value) return;
    let text;
    try {
      text = new TextDecoder("utf-8").decode(value);
    } catch {
      showBleError("Could not decode notification as UTF-8.");
      return;
    }
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      showBleError("The device must send enrollment data as JSON.");
      return;
    }
    setBleLastCapture(parsed);
    bleNotifications++;
    updateBleCounters();
    if (!blePendingEnrollUserId) {
      showBleError(
        "Choose who you are enrolling: tap “Record enrollment” next to a person below."
      );
      return;
    }
    showBleError("");
    queueEnrollmentRelay(parsed);
  }

  async function onBleDisconnected() {
    setBleStatus("Not connected");
    setBleDeviceLine("—");
    $("btn-ble-connect").disabled = false;
    $("btn-ble-disconnect").disabled = true;
    if (bleChar && bleNotifyHandler) {
      bleChar.removeEventListener(
        "characteristicvaluechanged",
        bleNotifyHandler
      );
      try {
        await bleChar.stopNotifications();
      } catch (_) {}
    }
    bleChar = null;
    bleNotifyHandler = null;
    bleDevice = null;
    setBleLastCapture(null);
  }

  async function disconnectBle() {
    showBleError("");
    if (bleChar && bleNotifyHandler) {
      bleChar.removeEventListener(
        "characteristicvaluechanged",
        bleNotifyHandler
      );
      try {
        await bleChar.stopNotifications();
      } catch (_) {}
    }
    bleChar = null;
    bleNotifyHandler = null;
    if (bleDevice && bleDevice.gatt && bleDevice.gatt.connected) {
      bleDevice.gatt.disconnect();
    } else {
      await onBleDisconnected();
    }
  }

  async function connectBle() {
    if (!bleSupported()) return;
    saveBlePrefs();
    showBleError("");
    if (useMock()) {
      showBleError("Turn off mock data and set API URL + key to save enrollments.");
      return;
    }
    if (!apiBase() || !apiKey()) {
      showBleError("Set API base URL and X-API-Key in the sidebar.");
      return;
    }
    const serviceUuid = normalizeUuid($("inp-ble-service").value);
    const charUuid = normalizeUuid($("inp-ble-char").value);
    const prefix = $("inp-ble-name-prefix").value.trim();
    let device;
    try {
      const optionalServices = [serviceUuid];
      if (prefix) {
        device = await navigator.bluetooth.requestDevice({
          filters: [{ namePrefix: prefix }],
          optionalServices,
        });
      } else {
        device = await navigator.bluetooth.requestDevice({
          acceptAllDevices: true,
          optionalServices,
        });
      }
    } catch (e) {
      if (e && e.name === "NotFoundError") return;
      showBleError(String(e.message || e));
      return;
    }
    bleDevice = device;
    bleServiceUuid = serviceUuid;
    bleCharUuid = charUuid;
    bleNotifications = 0;
    bleRelayOk = 0;
    bleForwardChain = Promise.resolve();
    updateBleCounters();
    device.addEventListener("gattserverdisconnected", () => {
      onBleDisconnected();
    });
    setBleStatus("Connecting…");
    setBleDeviceLine(device.name || device.id || "—");
    $("btn-ble-connect").disabled = true;
    $("btn-ble-disconnect").disabled = false;
    try {
      const server = await device.gatt.connect();
      const svc = await server.getPrimaryService(serviceUuid);
      const ch = await svc.getCharacteristic(charUuid);
      bleChar = ch;
      bleNotifyHandler = onBleNotification;
      await ch.startNotifications();
      ch.addEventListener("characteristicvaluechanged", bleNotifyHandler);
      setBleStatus("Connected — waiting for data…");
    } catch (e) {
      showBleError(String(e.message || e));
      setBleStatus("Error");
      $("btn-ble-connect").disabled = false;
      $("btn-ble-disconnect").disabled = true;
      try {
        if (device.gatt && device.gatt.connected) device.gatt.disconnect();
      } catch (_) {}
      bleDevice = null;
      bleChar = null;
      bleNotifyHandler = null;
    }
  }

  function renderSettingsApi() {
    $("settings-api").innerHTML = `
      <p>Live mode targets the <strong>BioAuth Gateway</strong> (FastAPI). Use base URL <code>http://localhost:8000</code> and header <code>X-API-Key: dev-api-key-001</code> (or your <code>BIOAUTH_API_KEYS</code>).</p>
      <ul>
        <li><code>GET /health</code> — no API key (connectivity check)</li>
        <li><code>GET /status</code> — edge connectivity</li>
        <li><code>GET /users</code>, <code>POST /users</code>, <code>DELETE /users/{user_id}</code> — create/list/remove people (deletes baseline + embedding; keeps audit logs)</li>
        <li><code>GET /logs?limit=…</code> — audit rows (<code>decision</code>, <code>user_id</code>, …)</li>
        <li><code>POST /enroll</code>, <code>POST /unenroll</code> — server transport to edge</li>
        <li><code>POST /relay/enrollment</code> — full <code>EnrollmentPayload</code> JSON (admin dashboard over Web Bluetooth, or SDK over BLE)</li>
        <li><code>POST /relay/authorize</code> — used by apps/SDKs for verification, not the admin enrollment UI</li>
      </ul>
      <p><strong>People</strong>: <strong>Connect</strong> / <strong>Disconnect</strong> only on the surface; optional UUIDs stay under Advanced. Choose <strong>Record enrollment</strong> for a pending user, then capture on the device — the sample is posted to <code>/relay/enrollment</code> with that user id.</p>
      <p>Charts aggregate <code>/logs</code> in the browser. CORS is enabled on the gateway for local dashboards.</p>
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
    showError("");
    const data = await loadOverviewBundle();
    renderStats();
    renderEventsTable("activity-body", data.events, true);
    bindCharts(data);
    if (data.error) {
      showError("Live API unavailable: " + data.error);
    } else {
      showError("");
    }
    if (data.error) {
      $("page-desc").textContent =
        "Live API unreachable — check URL and key. Stats and charts may be empty. Still auto-refreshing every 5s.";
    } else {
      $("page-desc").textContent = useMock()
        ? "Mock data locally. Turn off mock and set API URL + key for a real gateway. Refreshes every 5s."
        : "Scroll to enroll or review the log. Refreshes every 5s.";
    }
    filterLog();
  }

  async function refreshPeople() {
    await loadPeople();
    renderPeopleTable();
  }

  async function refreshAll() {
    if (refreshInFlight) return;
    refreshInFlight = true;
    try {
      await refreshOverview();
      await refreshPeople();
    } finally {
      refreshInFlight = false;
    }
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
    renderEventsTable("activity-body", filtered, true);
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
      scrollToSection("section-enroll");
      return;
    }

    try {
      await fetchJson("/users", {
        method: "POST",
        body: JSON.stringify({
          user_id: username,
          display_name: display_name || null,
        }),
      });
      closeModal();
      await refreshAll();
      scrollToSection("section-enroll");
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  async function completeEnrollment(userId) {
    showError("");
    if (useMock()) {
      const users = readMockUsers();
      const u = users.find((x) => String(x.id) === String(userId));
      if (!u || u.status !== "pending") return;
      u.status = "active";
      u.enrolled_at = new Date().toISOString();
      writeMockUsers(users);
      await refreshAll();
      return;
    }
    try {
      await fetchJson("/enroll", {
        method: "POST",
        body: JSON.stringify({ user_id: userId }),
      });
      await refreshAll();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  async function deletePerson(userId, displayName) {
    const label = displayName || userId;
    if (
      !window.confirm(
        `Remove "${label}" permanently? This deletes the account, baseline, and enrollment template. Audit history is kept.`
      )
    ) {
      return;
    }
    showError("");
    if (useMock()) {
      const users = readMockUsers();
      const removed = users.find(
        (u) =>
          String(u.id) === String(userId) || String(u.username) === String(userId)
      );
      const next = users.filter((u) => u !== removed);
      writeMockUsers(next);
      if (
        removed &&
        blePendingEnrollUserId &&
        removed.username === blePendingEnrollUserId
      ) {
        clearBleEnrollTarget();
      }
      await refreshAll();
      return;
    }
    try {
      await fetchJson(`/users/${encodeURIComponent(userId)}`, {
        method: "DELETE",
      });
      if (blePendingEnrollUserId === userId) clearBleEnrollTarget();
      await refreshAll();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  async function revokeEnrollment(userId) {
    showError("");
    if (useMock()) {
      const users = readMockUsers();
      const u = users.find((x) => String(x.id) === String(userId));
      if (!u) return;
      u.status = "disabled";
      writeMockUsers(users);
      await refreshAll();
      return;
    }
    try {
      await fetchJson("/unenroll", {
        method: "POST",
        body: JSON.stringify({ user_id: userId }),
      });
      await refreshAll();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  $("use-mock").addEventListener("change", () => {
    updateBleMockBanner();
    refreshAll();
  });
  $("api-base").addEventListener("change", () => refreshAll());
  $("api-key").addEventListener("change", () => refreshAll());
  $("log-filter").addEventListener("input", filterLog);

  ["inp-ble-service", "inp-ble-char", "inp-ble-name-prefix"].forEach((id) => {
    $(id).addEventListener("change", saveBlePrefs);
  });
  $("btn-ble-connect").addEventListener("click", () => connectBle());
  $("btn-ble-disconnect").addEventListener("click", () => disconnectBle());

  $("btn-add-user").addEventListener("click", openModal);
  $("form-add-user").addEventListener("submit", submitAddUser);
  document.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  loadPrefs();
  initBlePanel();
  renderSettingsApi();
  refreshAll();
  setInterval(() => {
    refreshAll();
  }, AUTO_REFRESH_MS);
})();

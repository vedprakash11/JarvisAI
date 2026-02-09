(function () {
  "use strict";

  const TOKEN_KEY = "jarvis_admin_token";
  const USER_KEY = "jarvis_admin_user";

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }
  function setToken(t) {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  }
  function getUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY));
    } catch {
      return null;
    }
  }
  function setUser(u) {
    if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
    else localStorage.removeItem(USER_KEY);
  }

  function headers() {
    const t = getToken();
    return {
      "Content-Type": "application/json",
      ...(t ? { Authorization: "Bearer " + t } : {}),
    };
  }

  const apiBase = ""; // same origin
  function api(path) {
    return (path.startsWith("/") ? apiBase + path : apiBase + "/" + path);
  }

  // --- Views ---
  const loginView = document.getElementById("loginView");
  const forbiddenView = document.getElementById("forbiddenView");
  const dashboardView = document.getElementById("dashboardView");

  function showView(view) {
    loginView.classList.add("hidden");
    forbiddenView.classList.add("hidden");
    dashboardView.classList.add("hidden");
    view.classList.remove("hidden");
  }

  function showLogin(message) {
    setToken(null);
    setUser(null);
    document.getElementById("loginError").textContent = message || "";
    showView(loginView);
  }

  function showForbidden() {
    showView(forbiddenView);
  }

  function showDashboard() {
    document.getElementById("userEmail").textContent = (getUser() && getUser().email) || "";
    showView(dashboardView);
    switchPane("overview");
    loadOverview();
    loadStatus();
    loadUsage();
    loadRequests(false);
  }

  function switchPane(paneId) {
    const panes = ["overview", "status", "usage", "requests"];
    panes.forEach(function (id) {
      const el = document.getElementById("pane" + id.charAt(0).toUpperCase() + id.slice(1));
      const link = document.querySelector('.nav-link[data-pane="' + id + '"]');
      if (el) el.classList.toggle("active", id === paneId);
      if (link) link.classList.toggle("active", id === paneId);
    });
    if (paneId === "usage") loadUsage();
    if (paneId === "requests") loadRequests(false);
  }

  document.querySelectorAll(".nav-link[data-pane]").forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      const pane = this.getAttribute("data-pane");
      if (pane) switchPane(pane);
    });
  });

  // --- Login ---
  document.getElementById("loginForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const errEl = document.getElementById("loginError");
    const btn = document.getElementById("loginBtn");
    errEl.textContent = "";
    if (!email || !password) {
      errEl.textContent = "Email and password required";
      return;
    }
    btn.disabled = true;
    try {
      const r = await fetch(api("auth/login"), {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ email, password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        errEl.textContent = data.detail || data.message || r.statusText || "Sign in failed";
        return;
      }
      setToken(data.access_token);
      setUser(data.user);
      const meR = await fetch(api("me"), { headers: headers() });
      const meData = await meR.json().catch(() => ({}));
      if (!meR.ok) {
        showLogin();
        return;
      }
      if (!meData.is_admin) {
        showForbidden();
        return;
      }
      setUser(meData);
      showDashboard();
    } catch (err) {
      errEl.textContent = err.message || "Network error";
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("logoutBtn").addEventListener("click", showLogin);
  document.getElementById("forbiddenLogout").addEventListener("click", showLogin);

  // --- Overview & insights ---
  function renderOverview(data) {
    if (!data || !data.log_file_available) {
      var cards = document.getElementById("insightCards");
      if (cards) cards.innerHTML = "<p class=\"unavailable\">Log file unavailable. Set LOG_FILE in .env.</p>";
      ["insightHealth", "insightPeak", "insightLatency", "insightMode"].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.innerHTML = "<p class=\"muted\">—</p>";
      });
      return;
    }
    const total = data.total_requests || 0;
    const success = data.success_count || 0;
    const errors = data.error_count || 0;
    const successRate = total ? Math.round((success / total) * 100) : 0;
    const errorRate = total ? Math.round((errors / total) * 100) : 0;
    const avgLat = data.avg_latency_ms != null ? data.avg_latency_ms.toFixed(0) : "—";
    const byMode = data.by_mode || {};
    const general = byMode.general ?? 0;
    const realtime = byMode.realtime ?? 0;

    document.getElementById("insightCards").innerHTML = `
      <div class="insight-card-kpi"><div class="kpi-value">${total}</div><div class="kpi-label">Total requests</div></div>
      <div class="insight-card-kpi success"><div class="kpi-value">${successRate}%</div><div class="kpi-label">Success rate</div></div>
      <div class="insight-card-kpi danger"><div class="kpi-value">${errorRate}%</div><div class="kpi-label">Error rate</div></div>
      <div class="insight-card-kpi"><div class="kpi-value">${avgLat}</div><div class="kpi-label">Avg latency (ms)</div></div>
      <div class="insight-card-kpi"><div class="kpi-value">${general}</div><div class="kpi-label">General</div></div>
      <div class="insight-card-kpi"><div class="kpi-value">${realtime}</div><div class="kpi-label">Realtime</div></div>
    `;

    const byStatus = data.by_status || {};
    const status2xx = Object.keys(byStatus).filter(function (k) { return k.startsWith("2"); }).reduce(function (s, k) { return s + (byStatus[k] || 0); }, 0);
    const status4xx = Object.keys(byStatus).filter(function (k) { return k.startsWith("4"); }).reduce(function (s, k) { return s + (byStatus[k] || 0); }, 0);
    const status5xx = Object.keys(byStatus).filter(function (k) { return k.startsWith("5"); }).reduce(function (s, k) { return s + (byStatus[k] || 0); }, 0);
    const healthText = total === 0
      ? "No traffic in the last 24h. Usage will appear once requests are logged."
      : errors === 0
        ? "All requests succeeded in the last 24h."
        : "Some errors in the last 24h. Check the Activity tab for details.";
    const healthClass = total === 0 ? "muted" : errors === 0 ? "highlight" : "";

    document.getElementById("insightHealth").innerHTML =
      "<p class=\"" + healthClass + "\">" + escapeHtml(healthText) + "</p>" +
      (total > 0 ? "<p class=\"muted\">2xx: " + status2xx + " · 4xx: " + status4xx + " · 5xx: " + status5xx + "</p>" : "");

    let peakHtml = "<p class=\"muted\">No hourly data.</p>";
    if (data.sorted_hours && data.sorted_hours.length > 0) {
      const peak = data.sorted_hours.reduce(function (best, cur) {
        const tot = cur[1] && cur[1].total ? cur[1].total : 0;
        return tot > (best.total || 0) ? { label: cur[0], total: tot } : best;
      }, { label: "", total: 0 });
      if (peak.label) {
        peakHtml = "<p><span class=\"highlight\">" + escapeHtml(peak.label) + "</span></p><p class=\"muted\">" + peak.total + " requests</p>";
      }
    }
    document.getElementById("insightPeak").innerHTML = peakHtml;

    let latencyHtml = "<p class=\"muted\">No latency data.</p>";
    if (data.avg_latency_ms != null && data.latency_samples > 0) {
      latencyHtml = "<p><span class=\"highlight\">" + Number(data.avg_latency_ms).toFixed(0) + " ms</span> average</p><p class=\"muted\">" + data.latency_samples + " samples</p>";
      if (data.sorted_latency_buckets && data.sorted_latency_buckets.length > 0) {
        const buckets = data.sorted_latency_buckets.slice(0, 5).map(function (b) { return b[0] + ": " + b[1]; }).join(" · ");
        latencyHtml += "<p class=\"muted\" style=\"margin-top:0.5rem;font-size:0.8rem;\">" + escapeHtml(buckets) + "</p>";
      }
    }
    document.getElementById("insightLatency").innerHTML = latencyHtml;

    const totalMode = general + realtime;
    const generalPct = totalMode ? Math.round((general / totalMode) * 100) : 0;
    const realtimePct = totalMode ? Math.round((realtime / totalMode) * 100) : 0;
    document.getElementById("insightMode").innerHTML =
      "<p><span class=\"highlight\">General</span> " + general + " (" + generalPct + "%)</p>" +
      "<p><span class=\"highlight\">Realtime</span> " + realtime + " (" + realtimePct + "%)</p>";
  }

  async function loadOverview() {
    const cardsEl = document.getElementById("insightCards");
    if (!cardsEl) return;
    cardsEl.innerHTML = '<div class="skeleton" data-skeleton="overview"></div>';
    try {
      const r = await fetch(api("admin/usage?hours=24"), { headers: headers() });
      if (r.status === 401) {
        showLogin("Session expired. Please sign in again.");
        return;
      }
      if (!r.ok) throw new Error("Failed to load usage");
      const data = await r.json();
      cardsEl.querySelector("[data-skeleton]")?.remove();
      renderOverview(data);
    } catch (err) {
      cardsEl.innerHTML = "<p class=\"unavailable\">" + escapeHtml(err.message || "Could not load overview.") + "</p>";
    }
  }

  // --- Helpers ---
  function clearSkeleton(id) {
    const el = document.getElementById(id);
    if (el) {
      const sk = el.querySelector("[data-skeleton]");
      if (sk) sk.remove();
    }
  }

  function showCardError(id, message) {
    const content = document.getElementById(id + "Content");
    const errEl = document.getElementById(id + "Error");
    if (errEl) {
      errEl.textContent = message;
      errEl.classList.remove("hidden");
    }
    if (content) content.innerHTML = "";
  }

  function hideCardError(id) {
    const errEl = document.getElementById(id + "Error");
    if (errEl) errEl.classList.add("hidden");
  }

  // --- Status ---
  function renderStatus(data) {
    if (!data) return "";
    const groq = data.groq || {};
    const vs = data.vector_store || {};
    let lastUsed = groq.last_used_at;
    if (lastUsed != null) {
      try {
        const d = new Date(lastUsed * 1000);
        lastUsed = d.toISOString().replace("T", " ").slice(0, 19) + " UTC";
      } catch (_) {
        lastUsed = String(lastUsed);
      }
    } else {
      lastUsed = "—";
    }
    let rebuild = vs.last_rebuild_time;
    if (rebuild != null) {
      try {
        const d = new Date(rebuild * 1000);
        rebuild = d.toISOString().replace("T", " ").slice(0, 19) + " UTC";
      } catch (_) {
        rebuild = String(rebuild);
      }
    } else {
      rebuild = "—";
    }
    return `
      <div class="status-grid">
        <div class="status-row"><span class="status-label">Keys in rotation</span><span>${groq.keys_in_rotation ?? "—"}</span></div>
        <div class="status-row"><span class="status-label">Last key (suffix)</span><span>••••${groq.last_used_key_suffix ?? "—"}</span></div>
        <div class="status-row"><span class="status-label">Last used</span><span>${lastUsed}</span></div>
        <div class="status-row"><span class="status-label">Vector store docs</span><span>${vs.doc_count ?? "—"}</span></div>
        <div class="status-row"><span class="status-label">Last rebuild</span><span>${rebuild}</span></div>
      </div>
    `;
  }

  async function loadStatus() {
    const content = document.getElementById("statusContent");
    const errEl = document.getElementById("statusError");
    hideCardError("status");
    content.innerHTML = '<div class="skeleton" data-skeleton="status"></div>';
    try {
      const r = await fetch(api("admin/status"), { headers: headers() });
      if (r.status === 401) {
        showLogin("Session expired. Please sign in again.");
        return;
      }
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || d.message || "Failed to load status");
      }
      const data = await r.json();
      clearSkeleton("statusContent");
      content.innerHTML = renderStatus(data);
    } catch (err) {
      errEl.textContent = err.message || "API unreachable. Ensure python run.py is running.";
      errEl.classList.remove("hidden");
      content.innerHTML = "";
    }
  }

  // --- Usage ---
  let currentHours = 24;

  function renderUsage(data) {
    if (!data) return "";
    const ok = data.log_file_available;
    if (!ok) {
      return '<p class="unavailable">Log file unavailable. Set LOG_FILE in .env and ensure the app writes logs.</p>';
    }
    const total = data.total_requests || 0;
    const success = data.success_count || 0;
    const errors = data.error_count || 0;
    const avg = data.avg_latency_ms != null ? data.avg_latency_ms.toFixed(1) : "—";
    const byMode = data.by_mode || {};
    return `
      <div class="usage-summary">
        <div class="usage-stat"><div class="value">${total}</div><div class="label">Total</div></div>
        <div class="usage-stat"><div class="value">${success}</div><div class="label">Success</div></div>
        <div class="usage-stat"><div class="value">${errors}</div><div class="label">Errors</div></div>
        <div class="usage-stat"><div class="value">${avg}</div><div class="label">Avg latency (ms)</div></div>
        <div class="usage-stat"><div class="value">${byMode.general ?? 0}</div><div class="label">General</div></div>
        <div class="usage-stat"><div class="value">${byMode.realtime ?? 0}</div><div class="label">Realtime</div></div>
      </div>
    `;
  }

  async function loadUsage() {
    const content = document.getElementById("usageContent");
    hideCardError("usage");
    content.innerHTML = '<div class="skeleton" data-skeleton="usage"></div>';
    try {
      const r = await fetch(api("admin/usage?hours=" + currentHours), { headers: headers() });
      if (r.status === 401) {
        showLogin("Session expired. Please sign in again.");
        return;
      }
      if (!r.ok) throw new Error("Failed to load usage");
      const data = await r.json();
      clearSkeleton("usageContent");
      content.innerHTML = renderUsage(data);
      renderChart(data);
    } catch (err) {
      document.getElementById("usageError").textContent = err.message || "Failed to load usage.";
      document.getElementById("usageError").classList.remove("hidden");
      content.innerHTML = "";
    }
  }

  function renderChart(data) {
    const container = document.getElementById("chartContent");
    const errEl = document.getElementById("chartError");
    errEl.classList.add("hidden");
    if (!data || !data.sorted_hours || data.sorted_hours.length === 0) {
      container.innerHTML = "<p class=\"unavailable\">No hourly data in range.</p>";
      return;
    }
    const max = Math.max(1, ...data.sorted_hours.map(([, v]) => v.total || 0));
    const bars = data.sorted_hours
      .map(([label, v]) => {
        const h = max ? Math.round(((v.total || 0) / max) * 100) : 0;
        return `<div class="bar" style="height:${h}%" title="${label}: ${v.total}"></div>`;
      })
      .join("");
    const labels = data.sorted_hours.map(([label]) => label);
    const first = labels[0] || "";
    const last = labels[labels.length - 1] || "";
    container.innerHTML = `
      <div class="bar-chart" role="img" aria-label="Requests by hour">${bars}</div>
      <div class="chart-labels"><span>${first}</span><span>${last}</span></div>
    `;
  }

  document.querySelectorAll(".range-tab").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".range-tab").forEach(function (b) {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      currentHours = parseInt(btn.getAttribute("data-hours"), 10) || 24;
      loadUsage();
    });
  });

  // --- Recent requests ---
  let requestsOffset = 0;
  const requestsLimit = 50;

  function renderRequests(items) {
    if (!items || items.length === 0) {
      return "<p class=\"unavailable\">No recent requests.</p>";
    }
    const rows = items
      .map(
        (r) => `
        <tr>
          <td>${escapeHtml(r.path)}</td>
          <td>${escapeHtml(r.mode)}</td>
          <td class="${r.status_code >= 400 ? "status-err" : "status-ok"}">${r.status_code ?? "—"}</td>
          <td>${r.latency_ms != null ? Number(r.latency_ms).toFixed(0) : "—"} ms</td>
          <td>${escapeHtml(r.client_ip)}</td>
          <td>${escapeHtml(r.session_id)}</td>
          <td>${escapeHtml(r.timestamp)}</td>
        </tr>
      `
      )
      .join("");
    return `
      <table>
        <thead><tr><th>Path</th><th>Mode</th><th>Status</th><th>Latency</th><th>IP</th><th>Session</th><th>Time</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  async function loadRequests(append) {
    const content = document.getElementById("requestsContent");
    const loadMoreBtn = document.getElementById("loadMoreBtn");
    if (!append) {
      requestsOffset = 0;
      hideCardError("requests");
      content.innerHTML = '<div class="skeleton" data-skeleton="requests"></div>';
    }
    try {
      const r = await fetch(
        api("admin/requests?limit=" + requestsLimit + "&offset=" + requestsOffset),
        { headers: headers() }
      );
      if (r.status === 401) {
        showLogin("Session expired. Please sign in again.");
        return;
      }
      if (!r.ok) throw new Error("Failed to load requests");
      const data = await r.json();
      if (!append) {
        clearSkeleton("requestsContent");
        content.innerHTML = "";
      }
      if (!data.log_file_available) {
        content.innerHTML = "<p class=\"unavailable\">Log file unavailable. Set LOG_FILE in .env.</p>";
        loadMoreBtn.classList.add("hidden");
        return;
      }
      const items = data.items || [];
      if (append) {
        const tbody = content.querySelector("tbody");
        if (tbody && items.length) {
          items.forEach((row) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td>${escapeHtml(row.path)}</td>
              <td>${escapeHtml(row.mode)}</td>
              <td class="${row.status_code >= 400 ? "status-err" : "status-ok"}">${row.status_code ?? "—"}</td>
              <td>${row.latency_ms != null ? Number(row.latency_ms).toFixed(0) : "—"} ms</td>
              <td>${escapeHtml(row.client_ip)}</td>
              <td>${escapeHtml(row.session_id)}</td>
              <td>${escapeHtml(row.timestamp)}</td>
            `;
            tbody.appendChild(tr);
          });
        }
      } else {
        content.innerHTML = renderRequests(items);
      }
      requestsOffset += items.length;
      loadMoreBtn.classList.toggle("hidden", items.length < requestsLimit);
    } catch (err) {
      document.getElementById("requestsError").textContent = err.message || "Failed to load requests.";
      document.getElementById("requestsError").classList.remove("hidden");
      if (!append) content.innerHTML = "";
    }
  }

  document.getElementById("loadMoreBtn").addEventListener("click", function () {
    loadRequests(true);
  });

  function loadAll() {
    loadOverview();
    loadStatus();
    loadUsage();
    loadRequests(false);
  }

  // --- Init ---
  (function init() {
    const token = getToken();
    if (!token) {
      showView(loginView);
      return;
    }
    fetch(api("me"), { headers: headers() })
      .then(function (r) {
        return r.ok ? r.json() : Promise.reject(new Error("Unauthorized"));
      })
      .then(function (user) {
        if (!user.is_admin) {
          showForbidden();
          return;
        }
        setUser(user);
        showDashboard();
      })
      .catch(function () {
        showLogin();
      });
  })();
})();

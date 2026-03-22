let token = "";

function showMessage(message, isError = false) {
  const el = document.getElementById("message");
  el.textContent = message;
  el.className = isError ? "error" : "success";
}

function setLoading(buttonId, isLoading, loadingLabel) {
  const button = document.getElementById(buttonId);
  if (!button) {
    return;
  }
  if (isLoading) {
    button.dataset.originalText = button.textContent;
    button.textContent = loadingLabel;
    button.disabled = true;
    return;
  }
  button.textContent = button.dataset.originalText || button.textContent;
  button.disabled = false;
}

function setAuthenticatedUI(isAuthenticated) {
  document.getElementById("employee-btn").disabled = !isAuthenticated;
  document.getElementById("shift-btn").disabled = !isAuthenticated;
  document.getElementById("run-btn").disabled = !isAuthenticated;
  document.getElementById("kpi-btn").disabled = !isAuthenticated;
  document.getElementById("runs-btn").disabled = !isAuthenticated;
  document.getElementById("delete-latest-run-btn").disabled = !isAuthenticated;
  document.getElementById("heatmap-btn").disabled = !isAuthenticated;
}

function initializeDefaultShiftWindow() {
  const now = new Date();
  const end = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  const toLocalInput = (date) => {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
  };
  document.getElementById("shift-start").value = toLocalInput(now);
  document.getElementById("shift-end").value = toLocalInput(end);
}

function initializeDefaultHeatmapWindow() {
  const now = new Date();
  const end = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  const toLocalInput = (date) => {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
  };
  document.getElementById("heatmap-start").value = toLocalInput(now);
  document.getElementById("heatmap-end").value = toLocalInput(end);
}

function ensureLoggedIn() {
  if (!token) {
    throw new Error("Log eerst in om deze actie uit te voeren.");
  }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}

function parseSkills(raw) {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function loadRuns() {
  const teamId = document.getElementById("run-team").value.trim();
  const siteId = document.getElementById("run-site").value.trim();
  const runLimit = Number(document.getElementById("run-limit").value || "20");
  const sortDir = document.getElementById("run-sort-dir").value;
  const runOffset = Number(document.getElementById("run-offset").value || "0");
  const params = new URLSearchParams({
    limit: String(Math.max(1, Math.min(100, Number.isNaN(runLimit) ? 20 : runLimit))),
    offset: String(Math.max(0, Number.isNaN(runOffset) ? 0 : runOffset)),
    sort_dir: sortDir,
  });
  if (teamId) {
    params.set("team_id", teamId);
  }
  if (siteId) {
    params.set("site_id", siteId);
  }

  const data = await api(`/runs?${params.toString()}`);
  document.getElementById("runs-summary").textContent = JSON.stringify(data, null, 2);
}

async function loadKpis() {
  const teamId = document.getElementById("run-team").value.trim();
  const siteId = document.getElementById("run-site").value.trim();
  const params = new URLSearchParams();
  if (teamId) {
    params.set("team_id", teamId);
  }
  if (siteId) {
    params.set("site_id", siteId);
  }

  const query = params.toString();
  const data = await api(`/kpis${query ? `?${query}` : ""}`);
  document.getElementById("kpi-summary").textContent = JSON.stringify(data, null, 2);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function toIsoLocal(value) {
  return new Date(value).toISOString();
}

function validateEmployeeForm() {
  const id = document.getElementById("emp-id").value.trim();
  const skills = parseSkills(document.getElementById("emp-skills").value);
  const cost = Number(document.getElementById("emp-cost").value || "0");

  if (!id) {
    throw new Error("Employee ID is verplicht.");
  }
  if (skills.length === 0) {
    throw new Error("Geef minstens 1 skill op.");
  }
  if (Number.isNaN(cost) || cost < 0) {
    throw new Error("Cost per shift moet 0 of hoger zijn.");
  }

  return { id, skills, cost };
}

function validateShiftForm() {
  const id = document.getElementById("shift-id").value.trim();
  const requiredSkill = document.getElementById("shift-skill").value.trim();
  const routeDistance = Number(document.getElementById("shift-distance").value || "0");
  const start = document.getElementById("shift-start").value;
  const end = document.getElementById("shift-end").value;

  if (!id) {
    throw new Error("Shift ID is verplicht.");
  }
  if (!requiredSkill) {
    throw new Error("Required skill is verplicht.");
  }
  if (Number.isNaN(routeDistance) || routeDistance < 0) {
    throw new Error("Route distance moet 0 of hoger zijn.");
  }
  if (!start || !end) {
    throw new Error("Start en end zijn verplicht.");
  }
  if (new Date(end) <= new Date(start)) {
    throw new Error("Shift end moet na start liggen.");
  }

  return { id, requiredSkill, routeDistance, start, end };
}

async function refreshEmployees() {
  const team = document.getElementById("emp-filter-team").value.trim();
  const site = document.getElementById("emp-filter-site").value.trim();
  const limit = Number(document.getElementById("emp-filter-limit").value || "100");
  const offset = Number(document.getElementById("emp-filter-offset").value || "0");
  const sortBy = document.getElementById("emp-sort-by").value;
  const sortDir = document.getElementById("emp-sort-dir").value;
  const params = new URLSearchParams();
  if (team) {
    params.set("team_id", team);
  }
  if (site) {
    params.set("site_id", site);
  }
  if (!Number.isNaN(limit)) {
    params.set("limit", String(Math.max(1, Math.min(200, limit))));
  }
  if (!Number.isNaN(offset)) {
    params.set("offset", String(Math.max(0, offset)));
  }
  params.set("sort_by", sortBy);
  params.set("sort_dir", sortDir);

  const query = params.toString();
  const employees = await api(`/employees${query ? `?${query}` : ""}`);
  document.getElementById("employee-rows").innerHTML = employees
    .map(
      (employee) =>
        `<tr><td>${employee.id}</td><td>${employee.skills.join(", ")}</td><td>${employee.team_id || "-"}/${
          employee.site_id || "-"
        }</td><td>${employee.available ? "yes" : "no"}</td><td><button data-employee-delete="${
          employee.id
        }">Delete</button></td></tr>`,
    )
    .join("");
}

async function refreshShifts() {
  const team = document.getElementById("shift-filter-team").value.trim();
  const site = document.getElementById("shift-filter-site").value.trim();
  const skill = document.getElementById("shift-filter-skill").value.trim();
  const limit = Number(document.getElementById("shift-filter-limit").value || "100");
  const offset = Number(document.getElementById("shift-filter-offset").value || "0");
  const sortBy = document.getElementById("shift-sort-by").value;
  const sortDir = document.getElementById("shift-sort-dir").value;
  const params = new URLSearchParams();
  if (team) {
    params.set("team_id", team);
  }
  if (site) {
    params.set("site_id", site);
  }
  if (skill) {
    params.set("required_skill", skill);
  }
  if (!Number.isNaN(limit)) {
    params.set("limit", String(Math.max(1, Math.min(200, limit))));
  }
  if (!Number.isNaN(offset)) {
    params.set("offset", String(Math.max(0, offset)));
  }
  params.set("sort_by", sortBy);
  params.set("sort_dir", sortDir);

  const query = params.toString();
  const shifts = await api(`/shifts${query ? `?${query}` : ""}`);
  document.getElementById("shift-rows").innerHTML = shifts
    .map(
      (shift) =>
        `<tr><td>${shift.id}</td><td>${shift.required_skill}</td><td>${new Date(
          shift.start,
        ).toLocaleString()} - ${new Date(shift.end).toLocaleString()}</td><td>${shift.team_id || "-"}/${
          shift.site_id || "-"
        }</td><td><button data-shift-delete="${shift.id}">Delete</button></td></tr>`,
    )
    .join("");
}

async function loadCapacityHeatmap() {
  const startRaw = document.getElementById("heatmap-start").value;
  const endRaw = document.getElementById("heatmap-end").value;
  if (!startRaw || !endRaw) {
    throw new Error("Start en end zijn verplicht voor de heatmap.");
  }

  const teamId = document.getElementById("heatmap-team").value.trim();
  const siteId = document.getElementById("heatmap-site").value.trim();
  const params = new URLSearchParams({
    start: toIsoLocal(startRaw),
    end: toIsoLocal(endRaw),
    bucket_minutes: "60",
  });
  if (teamId) {
    params.set("team_id", teamId);
  }
  if (siteId) {
    params.set("site_id", siteId);
  }

  const data = await api(`/capacity/heatmap?${params.toString()}`);
  const grid = document.getElementById("heatmap-grid");
  grid.innerHTML = data.buckets
    .map((bucket) => {
      const start = new Date(bucket.bucket_start).toLocaleString();
      const end = new Date(bucket.bucket_end).toLocaleString();
      const riskClass =
        bucket.risk_level === "high"
          ? "risk-high"
          : bucket.risk_level === "medium"
            ? "risk-medium"
            : "";
      const tip = `Required ${bucket.required_count}, Available ${bucket.available_count}, Absent ${bucket.absence_count}, Gap ${bucket.gap}`;
      return `<div class="heatmap-cell ${riskClass}" title="${tip}">
        <strong>${start}</strong><br/>
        <small>tot ${end}</small><br/>
        <span>Req: ${bucket.required_count} | Cap: ${bucket.available_count}</span><br/>
        <span>Absent: ${bucket.absence_count} | Gap: ${bucket.gap}</span>
      </div>`;
    })
    .join("");
}


document.getElementById("emp-refresh-btn").addEventListener("click", () => {
  refreshEmployees().catch((error) => showMessage(`Employee refresh mislukt: ${error.message}`, true));
});

document.getElementById("shift-refresh-btn").addEventListener("click", () => {
  refreshShifts().catch((error) => showMessage(`Shift refresh mislukt: ${error.message}`, true));
});

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading("login-btn", true, "Logging in...");
  try {
    const payload = {
      username: document.getElementById("username").value.trim(),
      password: document.getElementById("password").value,
    };
    if (!payload.username || !payload.password) {
      throw new Error("Vul username en password in.");
    }

    const data = await api("/auth/token", { method: "POST", body: JSON.stringify(payload) });
    token = data.access_token;
    const profile = await api("/auth/me");
    document.getElementById("auth-status").textContent = `Logged in as ${profile.username} (${profile.role})`;
    setAuthenticatedUI(true);
    await refreshEmployees();
    await refreshShifts();
    showMessage("Login gelukt.");
  } catch (error) {
    showMessage(`Login mislukt: ${error.message}`, true);
  } finally {
    setLoading("login-btn", false);
  }
});

document.getElementById("employee-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading("employee-btn", true, "Saving...");
  try {
    ensureLoggedIn();
    const validated = validateEmployeeForm();
    const payload = {
      id: validated.id,
      team_id: document.getElementById("emp-team").value || null,
      site_id: document.getElementById("emp-site").value || null,
      skills: validated.skills,
      cost_per_shift: validated.cost,
      available: document.getElementById("emp-available").checked,
    };
    await api("/employees", { method: "POST", body: JSON.stringify(payload) });
    await refreshEmployees();
    showMessage("Employee aangemaakt.");
    event.target.reset();
  } catch (error) {
    showMessage(`Employee create mislukt: ${error.message}`, true);
  } finally {
    setLoading("employee-btn", false);
  }
});

document.getElementById("employee-rows").addEventListener("click", async (event) => {
  const target = event.target;
  const employeeId = target.getAttribute("data-employee-delete");
  if (!employeeId) {
    return;
  }

  if (!window.confirm(`Weet je zeker dat je employee ${employeeId} wilt verwijderen?`)) {
    return;
  }

  try {
    ensureLoggedIn();
    await api(`/employees/${employeeId}`, { method: "DELETE" });
    await refreshEmployees();
    showMessage(`Employee ${employeeId} verwijderd.`);
  } catch (error) {
    showMessage(`Employee delete mislukt: ${error.message}`, true);
  }
});

document.getElementById("shift-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading("shift-btn", true, "Saving...");
  try {
    ensureLoggedIn();
    const validated = validateShiftForm();
    const payload = {
      id: validated.id,
      team_id: document.getElementById("shift-team").value || null,
      site_id: document.getElementById("shift-site").value || null,
      required_skill: validated.requiredSkill,
      route_distance_km: validated.routeDistance,
      start: toIsoLocal(validated.start),
      end: toIsoLocal(validated.end),
    };
    await api("/shifts", { method: "POST", body: JSON.stringify(payload) });
    await refreshShifts();
    showMessage("Shift aangemaakt.");
    event.target.reset();
  } catch (error) {
    showMessage(`Shift create mislukt: ${error.message}`, true);
  } finally {
    setLoading("shift-btn", false);
  }
});

document.getElementById("shift-rows").addEventListener("click", async (event) => {
  const target = event.target;
  const shiftId = target.getAttribute("data-shift-delete");
  if (!shiftId) {
    return;
  }

  if (!window.confirm(`Weet je zeker dat je shift ${shiftId} wilt verwijderen?`)) {
    return;
  }

  try {
    ensureLoggedIn();
    await api(`/shifts/${shiftId}`, { method: "DELETE" });
    await refreshShifts();
    showMessage(`Shift ${shiftId} verwijderd.`);
  } catch (error) {
    showMessage(`Shift delete mislukt: ${error.message}`, true);
  }
});

document.getElementById("run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading("run-btn", true, "Running...");
  try {
    ensureLoggedIn();
    const payload = {
      team_id: document.getElementById("run-team").value || null,
      site_id: document.getElementById("run-site").value || null,
      constraints: [],
    };
    const result = await api("/optimize/run", { method: "POST", body: JSON.stringify(payload) });
    document.getElementById("run-summary").textContent = JSON.stringify(
      {
        run_id: result.run_id,
        score: result.score,
        score_breakdown: result.score_breakdown,
        violations: result.violations,
      },
      null,
      2,
    );
    document.getElementById("assignment-rows").innerHTML = result.assignments
      .map(
        (assignment) =>
          `<tr><td>${assignment.shift_id}</td><td>${assignment.employee_id || "-"}</td><td>${
            assignment.reason
          }</td></tr>`,
      )
      .join("");

    await Promise.all([loadKpis(), loadRuns()]);
    showMessage("Optimize run uitgevoerd (KPI + run history ververst).");
  } catch (error) {
    showMessage(`Optimize run mislukt: ${error.message}`, true);
  } finally {
    setLoading("run-btn", false);
  }
});

document.getElementById("runs-btn").addEventListener("click", async () => {
  try {
    ensureLoggedIn();
    setLoading("runs-btn", true, "Loading...");
    await loadRuns();
    showMessage("Run history geladen.");
  } catch (error) {
    showMessage(`Run history laden mislukt: ${error.message}`, true);
  } finally {
    setLoading("runs-btn", false);
  }
});

document.getElementById("delete-latest-run-btn").addEventListener("click", async () => {
  try {
    ensureLoggedIn();
    setLoading("delete-latest-run-btn", true, "Deleting...");
    const teamId = document.getElementById("run-team").value.trim();
    const siteId = document.getElementById("run-site").value.trim();
    const params = new URLSearchParams({ limit: "1", sort_dir: "desc" });
    if (teamId) {
      params.set("team_id", teamId);
    }
    if (siteId) {
      params.set("site_id", siteId);
    }

    const runs = await api(`/runs?${params.toString()}`);
    if (!runs.length) {
      showMessage("Geen runs gevonden om te verwijderen.");
      return;
    }

    if (!window.confirm(`Weet je zeker dat je run ${runs[0].id} wilt verwijderen?`)) {
      return;
    }

    await api(`/runs/${runs[0].id}`, { method: "DELETE" });
    await Promise.all([loadRuns(), loadKpis()]);
    showMessage(`Run ${runs[0].id} verwijderd.`);
  } catch (error) {
    showMessage(`Run verwijderen mislukt: ${error.message}`, true);
  } finally {
    setLoading("delete-latest-run-btn", false);
  }
});

document.getElementById("copy-run-btn").addEventListener("click", async () => {
  try {
    await copyText(document.getElementById("run-summary").textContent);
    showMessage("Run JSON gekopieerd.");
  } catch (error) {
    showMessage(`Kopiëren mislukt: ${error.message}`, true);
  }
});

document.getElementById("copy-kpi-btn").addEventListener("click", async () => {
  try {
    await copyText(document.getElementById("kpi-summary").textContent);
    showMessage("KPI JSON gekopieerd.");
  } catch (error) {
    showMessage(`Kopiëren mislukt: ${error.message}`, true);
  }
});

document.getElementById("copy-runs-btn").addEventListener("click", async () => {
  try {
    await copyText(document.getElementById("runs-summary").textContent);
    showMessage("Runs JSON gekopieerd.");
  } catch (error) {
    showMessage(`Kopiëren mislukt: ${error.message}`, true);
  }
});

document.getElementById("reset-btn").addEventListener("click", () => {
  document.getElementById("run-summary").textContent = "No run yet.";
  document.getElementById("kpi-summary").textContent = "No KPI data yet.";
  document.getElementById("runs-summary").textContent = "No run history yet.";
  document.getElementById("assignment-rows").innerHTML = "";
  showMessage("Resultaatweergave gereset.");
});

document.getElementById("kpi-btn").addEventListener("click", async () => {
  try {
    ensureLoggedIn();
    setLoading("kpi-btn", true, "Loading...");
    await loadKpis();
    showMessage("KPI data geladen.");
  } catch (error) {
    showMessage(`KPI laden mislukt: ${error.message}`, true);
  } finally {
    setLoading("kpi-btn", false);
  }
});

document.getElementById("heatmap-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    ensureLoggedIn();
    setLoading("heatmap-btn", true, "Loading...");
    await loadCapacityHeatmap();
    showMessage("Capaciteit heatmap geladen.");
  } catch (error) {
    showMessage(`Heatmap laden mislukt: ${error.message}`, true);
  } finally {
    setLoading("heatmap-btn", false);
  }
});

setAuthenticatedUI(false);
initializeDefaultShiftWindow();
initializeDefaultHeatmapWindow();

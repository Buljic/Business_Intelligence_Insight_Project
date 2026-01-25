const outputPre = document.getElementById("output-pre");
const outputTable = document.getElementById("output-table");
const statusDb = document.getElementById("status-db");
const statusMl = document.getElementById("status-ml");

function setStatus(el, ok, label) {
  el.textContent = label + ": " + (ok ? "ok" : "down");
  el.style.borderColor = ok ? "rgba(55, 214, 194, 0.6)" : "rgba(255, 120, 120, 0.6)";
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function renderTable(rows) {
  outputTable.innerHTML = "";
  if (!Array.isArray(rows) || rows.length === 0) {
    return;
  }
  const columns = Object.keys(rows[0]);
  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.replace(/_/g, " ");
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = row[col];
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  outputTable.appendChild(table);
}

function renderOutput(title, payload) {
  outputPre.textContent = JSON.stringify(payload, null, 2);
  if (payload && payload.rows) {
    renderTable(payload.rows);
  } else if (payload && payload.steps) {
    renderTable(payload.steps);
  } else if (payload && payload.checks) {
    renderTable(payload.checks);
  } else if (payload && payload.etl_steps) {
    renderTable(payload.etl_steps);
  } else if (payload && payload.result) {
    renderTable([payload.result]);
  } else if (payload && payload.datasets) {
    renderTable(payload.datasets.map((name) => ({ dataset: name })));
  } else {
    outputTable.innerHTML = "";
  }
}

async function refreshHealth() {
  try {
    const data = await fetchJson("/api/health");
    setStatus(statusDb, data.database_connected, "database");
    setStatus(statusMl, data.ml_connected, "ml");
  } catch (error) {
    setStatus(statusDb, false, "database");
    setStatus(statusMl, false, "ml");
  }
}

async function handleAction(url, options, title) {
  outputPre.textContent = "Running...";
  outputTable.innerHTML = "";
  try {
    const data = await fetchJson(url, options);
    renderOutput(title, data);
  } catch (error) {
    outputPre.textContent = "Error: " + error.message;
    outputTable.innerHTML = "";
  }
}

document.getElementById("btn-etl").addEventListener("click", () => {
  handleAction("/api/run-etl", { method: "POST" }, "run etl");
});

document.getElementById("btn-import").addEventListener("click", () => {
  const runEtl = document.getElementById("import-run-etl").checked;
  const runMl = document.getElementById("import-run-ml").checked;
  handleAction("/api/import-csv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_etl: runEtl, run_ml: runMl })
  }, "import csv");
});

document.getElementById("btn-dq").addEventListener("click", () => {
  handleAction("/api/run-dq", { method: "POST" }, "run dq");
});

document.getElementById("btn-ml").addEventListener("click", () => {
  handleAction("/api/train-ml", { method: "POST" }, "train ml");
});

document.getElementById("btn-backtest").addEventListener("click", () => {
  const metric = document.getElementById("backtest-metric").value;
  const model = document.getElementById("backtest-model").value;
  const testDays = parseInt(document.getElementById("backtest-days").value, 10);
  handleAction("/api/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ metric, model, test_days: testDays })
  }, "backtest");
});

document.querySelectorAll("[data-query]").forEach((button) => {
  button.addEventListener("click", () => {
    const key = button.getAttribute("data-query");
    handleAction(`/api/query/${key}`, { method: "GET" }, key);
  });
});

document.getElementById("btn-forecasts").addEventListener("click", () => {
  handleAction("/api/forecasts/latest", { method: "GET" }, "forecasts latest");
});

document.getElementById("btn-anomalies").addEventListener("click", () => {
  handleAction("/api/anomalies/latest", { method: "GET" }, "anomalies latest");
});

document.getElementById("btn-superset").addEventListener("click", () => {
  handleAction("/api/setup-superset", { method: "POST" }, "setup superset");
});

refreshHealth();
setInterval(refreshHealth, 20000);

const gbp = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

async function getJSON(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

function setStatus(text, kind) {
  const el = document.getElementById("status");
  el.textContent = text;
  el.className = `status ${kind}`;
}

function renderCards(details, monthly) {
  const total = details.reduce((sum, d) => sum + d.all_properties, 0);
  const occupied = details.reduce((sum, d) => sum + d.active_properties, 0);
  const rent = monthly.reduce((sum, m) => sum + Number(m.collected), 0);

  document.getElementById("kpi-properties").textContent = total;
  document.getElementById("kpi-occupancy").textContent = `${((occupied / total) * 100).toFixed(1)}%`;
  document.getElementById("kpi-rent").textContent = gbp.format(rent);
}

function renderCharts(details, monthly) {
  new Chart(document.getElementById("occupancy-chart"), {
    type: "bar",
    data: {
      labels: details.map((d) => d.branch_name),
      datasets: [{ label: "Occupancy %", data: details.map((d) => Number(d.property_share_pct)) }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, max: 100 } },
    },
  });

  new Chart(document.getElementById("rent-chart"), {
    type: "line",
    data: {
      labels: monthly.map((m) => m.payment_month),
      datasets: [{
        label: "Rent collected (£)",
        data: monthly.map((m) => Number(m.collected)),
        tension: 0.25,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function renderTable(branches, details) {
  const tbody = document.querySelector("#branches-table tbody");
  tbody.replaceChildren();

  branches.forEach((branch, index) => {
    const row = document.createElement("tr");
    const cells = [
      branch.branch_name,
      branch.total_properties,
      gbp.format(branch.average_listed_rent),
      `${Number(details[index].property_share_pct).toFixed(1)}%`,
    ];
    cells.forEach((text) => {
      const cell = document.createElement("td");
      cell.textContent = text; // textContent, never innerHTML, for data that came from the API
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
}

async function loadDashboard() {
  try {
    await getJSON("/health");
    const branches = await getJSON("/branches");
    const [details, monthly] = await Promise.all([
      Promise.all(branches.map((b) => getJSON(`/branches/${b.branch_id}`))),
      getJSON("/analytics/monthly-rent?year=2025"),
    ]);

    renderCards(details, monthly);
    renderCharts(details, monthly);
    renderTable(branches, details);
    setStatus("Connected", "ok");
  } catch (error) {
    console.error(error);
    setStatus(`Could not load data: ${error.message}`, "error");
  }
}

loadDashboard();
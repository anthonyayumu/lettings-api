const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });

const els = {
  arrearsBody: document.querySelector("#arrears-table tbody"),
  arrearsSummary: document.getElementById("arrears-summary"),
  arrearsLimit: document.getElementById("arrears-limit"),
  arrearsError: document.getElementById("arrears-error"),
  slaBody: document.querySelector("#sla-table tbody"),
  slaBranch: document.getElementById("sla-branch"),
  slaError: document.getElementById("sla-error"),
};

let arrearsRows = [];

function cell(content, className) {
  const td = document.createElement("td");
  if (content instanceof Node) {
    td.appendChild(content);
  } else {
    td.textContent = content; // textContent, never innerHTML, for data from the API
  }
  if (className) {
    td.className = className;
  }
  return td;
}

function showError(el, text) {
  el.textContent = text;
  el.hidden = false;
}

function renderArrears() {
  const limit = Number(els.arrearsLimit.value);
  els.arrearsBody.replaceChildren();
  arrearsRows.slice(0, limit).forEach((row) => {
    const tr = document.createElement("tr");
    tr.append(
      cell(row.tenancy_id),
      cell(row.full_name),
      cell(row.missed_payments, "num"),
      cell(gbp.format(Number(row.short_falls)), "num"),
    );
    els.arrearsBody.appendChild(tr);
  });
}

function renderArrearsSummary() {
  const total = arrearsRows.reduce((sum, row) => sum + Number(row.short_falls), 0);
  els.arrearsSummary.textContent =
    `${arrearsRows.length} active tenancies owe ${gbp.format(total)} in total, ` +
    "as of 30 September 2025 (the latest due date in the data).";
}

function rateBar(rate) {
  const wrap = document.createElement("div");
  wrap.className = "bar";
  const fill = document.createElement("div");
  fill.className = "bar-fill";
  fill.style.width = `${Math.min(100, Math.max(0, rate))}%`;
  const label = document.createElement("span");
  label.textContent = `${rate.toFixed(1)}%`;
  wrap.append(fill, label);
  return wrap;
}

function renderSla(rows) {
  els.slaBody.replaceChildren();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.append(
      cell(row.branch_name),
      cell(row.priority),
      cell(row.sla_days, "num"),
      cell(row.all_jobs, "num"),
      cell(row.jobs_resolved_on_time, "num"),
      cell(rateBar(Number(row.on_time_rate_pct))),
      cell(row.still_open, "num"),
    );
    els.slaBody.appendChild(tr);
  });
}

async function loadSla() {
  els.slaError.hidden = true;
  try {
    const branch = els.slaBranch.value;
    const path = branch ? `/analytics/sla?branch_id=${branch}` : "/analytics/sla";
    renderSla(await getJSON(path));
  } catch (error) {
    showError(els.slaError, `Could not load SLA data: ${error.message}`);
  }
}

async function init() {
  // allSettled waits for every request and reports each result separately,
  // so one failing request does not blank the other panel.
  const [arrears, branches] = await Promise.allSettled([
    getJSON("/analytics/arrears?limit=200"),
    getJSON("/branches"),
  ]);

  if (arrears.status === "fulfilled") {
    arrearsRows = arrears.value;
    renderArrearsSummary();
    renderArrears();
  } else {
    els.arrearsSummary.textContent = "";
    showError(els.arrearsError, `Could not load arrears: ${arrears.reason.message}`);
  }

  if (branches.status === "fulfilled") {
    branches.value.forEach((branch) => {
      const option = document.createElement("option");
      option.value = branch.branch_id;
      option.textContent = branch.branch_name;
      els.slaBranch.appendChild(option);
    });
  }

  loadSla();
}

els.arrearsLimit.addEventListener("change", renderArrears);
els.slaBranch.addEventListener("change", loadSla);

init();
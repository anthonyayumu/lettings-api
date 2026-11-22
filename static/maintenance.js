const PAGE_SIZE = 15;
let page = 1;
let resolvingId = null;

const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });

const els = {
  message: document.getElementById("message"),
  createForm: document.getElementById("create-form"),
  filter: document.getElementById("status-filter"),
  tbody: document.querySelector("#repairs-table tbody"),
  prev: document.getElementById("prev"),
  next: document.getElementById("next"),
  pageInfo: document.getElementById("page-info"),
  dialog: document.getElementById("resolve-dialog"),
  dialogTitle: document.getElementById("resolve-title"),
  resolveForm: document.getElementById("resolve-form"),
  resolveCancel: document.getElementById("resolve-cancel"),
};

function showMessage(text, kind) {
  els.message.textContent = text;
  els.message.className = `message ${kind}`;
  els.message.hidden = false;
}

function today() {
  return new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text; // textContent, never innerHTML, for data from the API
  return td;
}

function renderRows(items) {
  els.tbody.replaceChildren();
  items.forEach((item) => {
    const row = document.createElement("tr");
    row.append(
      cell(item.request_id),
      cell(`${item.property_id} · ${item.address}, ${item.town}`),
      cell(item.category),
      cell(item.priority),
      cell(item.reported_date),
      cell(item.resolved_date ?? "Open"),
      cell(item.cost === null ? "-" : gbp.format(item.cost)),
    );

    const action = document.createElement("td");
    if (item.resolved_date === null) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Resolve";
      button.addEventListener("click", () => openResolveDialog(item));
      action.appendChild(button);
    }
    row.appendChild(action);
    els.tbody.appendChild(row);
  });
}

async function loadRepairs() {
  try {
    const status = els.filter.value;
    const data = await getJSON(
      `/maintenance-requests?status=${status}&page=${page}&page_size=${PAGE_SIZE}`
    );
    renderRows(data.items);
    const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
    els.pageInfo.textContent = `Page ${page} of ${pages} (${data.total} repairs)`;
    els.prev.disabled = page <= 1;
    els.next.disabled = page >= pages;
  } catch (error) {
    showMessage(`Could not load repairs: ${error.message}`, "error");
  }
}

function openResolveDialog(item) {
  resolvingId = item.request_id;
  els.dialogTitle.textContent = `Resolve repair #${item.request_id}`;
  const resolvedDate = document.getElementById("resolved_date");
  resolvedDate.value = today();
  resolvedDate.min = item.reported_date;
  document.getElementById("cost").value = "";
  els.dialog.showModal();
}

els.createForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {
    property_id: Number(document.getElementById("property_id").value),
    category: document.getElementById("category").value,
    priority: document.getElementById("priority").value,
  };
  const reported = document.getElementById("reported_date").value;
  if (reported) {
    body.reported_date = reported;
  }
  try {
    const created = await sendJSON("/maintenance-requests", "POST", body);
    showMessage(`Repair #${created.request_id} logged.`, "ok");
    els.createForm.reset();
    els.filter.value = "open";
    page = 1;
    loadRepairs();
  } catch (error) {
    showMessage(`Could not log repair: ${error.message}`, "error");
  }
});

els.resolveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await sendJSON(`/maintenance-requests/${resolvingId}/resolve`, "PATCH", {
      resolved_date: document.getElementById("resolved_date").value,
      cost: Number(document.getElementById("cost").value),
    });
    els.dialog.close();
    showMessage(`Repair #${resolvingId} resolved.`, "ok");
    loadRepairs();
  } catch (error) {
    els.dialog.close();
    showMessage(`Could not resolve repair: ${error.message}`, "error");
  }
});

els.filter.addEventListener("change", () => {
  page = 1;
  loadRepairs();
});
els.prev.addEventListener("click", () => {
  page -= 1;
  loadRepairs();
});
els.next.addEventListener("click", () => {
  page += 1;
  loadRepairs();
});
els.resolveCancel.addEventListener("click", () => els.dialog.close());

loadRepairs();
import { apiFetch, withQuery } from "./api.js";
import { apiBase, getColumns, totalRows } from "./dataset.js";
import { clear, el, fmt, fmtPct, spinner } from "./ui.js";

const KIND_BADGE = { numeric: "primary", categorical: "success", datetime: "warning", boolean: "info", text: "secondary" };
const cards = document.getElementById("metric-cards");
const tableContainer = document.getElementById("columns-table");
const modalEl = document.getElementById("values-modal");
const modal = new window.bootstrap.Modal(modalEl);

export function metricCard(label, value, icon, hint) {
  return el("div", { class: "col-6 col-md-4 col-xl-2" }, el("div", { class: "card card-metric shadow-sm h-100" }, el("div", { class: "card-body" }, [
    el("div", { class: "metric-label" }, [el("i", { class: `bi ${icon} me-1` }), label]),
    el("div", { class: "metric-value", text: value }),
    hint ? el("div", { class: "small text-body-secondary", text: hint }) : null,
  ])));
}

async function showValues(column) {
  document.getElementById("values-modal-title").textContent = `Top values: ${column.name}`;
  const body = clear(document.getElementById("values-modal-body"));
  body.append(spinner());
  modal.show();
  try {
    const res = await apiFetch(withQuery(`${apiBase}/columns/${encodeURIComponent(column.name)}/values`, { top: 25 }));
    clear(body);
    body.append(el("p", { class: "small text-body-secondary", text: `${fmt(res.distinct)} distinct values · ${fmt(res.null)} missing` }));
    const rows = res.values.map((v) => el("tr", {}, [
      el("td", { class: "text-truncate", style: "max-width: 22rem", title: String(v.value), text: String(v.value) }),
      el("td", { class: "text-end", text: fmt(v.count) }),
      el("td", { style: "width: 40%" }, el("div", { class: "progress", role: "progressbar", "aria-label": `${v.percent}%`, "aria-valuenow": String(v.percent), "aria-valuemin": "0", "aria-valuemax": "100" },
        el("div", { class: "progress-bar", style: `width: ${v.percent}%`, text: `${v.percent}%` }))),
    ]));
    if (res.other_count) rows.push(el("tr", {}, [el("td", { class: "fst-italic", text: "Other values" }), el("td", { class: "text-end", text: fmt(res.other_count) }), el("td")]));
    body.append(el("table", { class: "table table-sm align-middle" }, [
      el("thead", {}, el("tr", {}, [el("th", { text: "Value" }), el("th", { class: "text-end", text: "Count" }), el("th", { text: "Share of non-missing" })])),
      el("tbody", {}, rows),
    ]));
  } catch (err) {
    clear(body).append(el("div", { class: "alert alert-danger", text: err.message }));
  }
}

async function init() {
  tableContainer.append(spinner());
  const columns = await getColumns();
  const totalCells = totalRows * columns.length;
  const missing = columns.reduce((acc, c) => acc + c.null_count, 0);
  const kindCounts = columns.reduce((acc, c) => ({ ...acc, [c.kind]: (acc[c.kind] || 0) + 1 }), {});
  const kindsHint = Object.entries(kindCounts).map(([k, n]) => `${n} ${k}`).join(", ");
  clear(cards).append(
    metricCard("Rows", fmt(totalRows), "bi-list-ol"),
    metricCard("Columns", fmt(columns.length), "bi-layout-three-columns", kindsHint),
    metricCard("Missing cells", fmtPct(totalCells ? Math.round((missing / totalCells) * 10000) / 100 : 0), "bi-question-diamond", `${fmt(missing)} cells`),
    metricCard("Columns with missing", fmt(columns.filter((c) => c.null_count > 0).length), "bi-exclamation-triangle"),
  );
  const rows = columns.map((c) => el("tr", {}, [
    el("td", { class: "fw-semibold", text: c.name }),
    el("td", {}, el("span", { class: `badge text-bg-${KIND_BADGE[c.kind] ?? "secondary"}`, text: c.kind })),
    el("td", { class: "text-body-secondary font-monospace small", text: c.dtype }),
    el("td", { class: "text-end", text: fmt(c.non_null) }),
    el("td", { class: "text-end", text: `${fmt(c.null_count)} (${fmtPct(totalRows ? Math.round((c.null_count / totalRows) * 10000) / 100 : 0)})` }),
    el("td", { class: "text-end", text: fmt(c.unique) }),
    el("td", { class: "text-end" }, el("button", { type: "button", class: "btn btn-sm btn-outline-primary", onclick: () => showValues(c), "aria-label": `Top values for ${c.name}` }, [el("i", { class: "bi bi-bar-chart" }), " Values"])),
  ]));
  clear(tableContainer).append(el("div", { class: "table-responsive" }, el("table", { class: "table table-sm table-hover align-middle mb-0" }, [
    el("thead", {}, el("tr", {}, ["Column", "Kind", "Type", "Non-missing", "Missing", "Unique", ""].map((h, i) => el("th", { scope: "col", class: i >= 3 && i <= 5 ? "text-end" : "", text: h })))),
    el("tbody", {}, rows),
  ])));
}

init().catch((err) => clear(tableContainer).append(el("div", { class: "alert alert-danger", text: err.message })));

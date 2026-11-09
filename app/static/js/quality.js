import { apiFetch, withQuery } from "./api.js";
import { apiBase, getColumns, getFilters } from "./dataset.js";
import { initFilterPanel, showFilterError, showMatchCount } from "./filters.js";
import { clear, el, fmt, fmtPct, spinner, table } from "./ui.js";

const summaryEl = document.getElementById("quality-summary");
const columnsEl = document.getElementById("missing-columns");
const patternsEl = document.getElementById("missing-patterns");
const dupForm = document.getElementById("dup-form");
const dupColumns = document.getElementById("dup-columns");
const dupNormalize = document.getElementById("dup-normalize");
const dupResult = document.getElementById("dup-result");
let missingRequest = 0;
let dupRequest = 0;
const metrics = {};

const filterQuery = () => (getFilters().length ? getFilters() : undefined);

function metric(key, label, value, sub, variant) {
  const node = el("div", { class: "col-6 col-lg-3" }, el("div", { class: `card card-metric shadow-sm h-100 ${variant ? `border-${variant}` : ""}` },
    el("div", { class: "card-body" }, [
      el("div", { class: "metric-label", text: label }),
      el("div", { class: "metric-value", text: value }),
      sub ? el("div", { class: "small text-body-secondary", text: sub }) : null,
    ])));
  metrics[key] = node;
  return node;
}

function renderSummary() {
  clear(summaryEl).append(...["missing", "rows", "complete", "dups"].map((k) => metrics[k]).filter(Boolean));
}

function bar(pct) {
  const inner = el("div", { class: `progress-bar ${pct > 20 ? "bg-danger" : pct > 5 ? "bg-warning" : "bg-success"}` });
  inner.style.width = `${Math.max(pct, pct > 0 ? 1 : 0)}%`;
  return el("div", { class: "progress missing-bar", role: "progressbar", "aria-valuenow": String(pct), "aria-valuemin": "0", "aria-valuemax": "100", "aria-label": `${pct}% missing` }, inner);
}

function renderMissing(data) {
  metric("missing", "Missing cells", fmtPct(data.missing_pct), `${fmt(data.missing_cells)} of ${fmt(data.cells)}`, data.missing_cells ? "warning" : "success");
  metric("rows", "Rows with missing values", fmt(data.rows_with_missing), fmtPct(data.rows_with_missing_pct));
  metric("complete", "Complete rows", fmt(data.complete_rows), fmtPct(data.complete_rows_pct));
  renderSummary();
  const sorted = [...data.columns].sort((a, b) => b.missing - a.missing);
  clear(columnsEl).append(table(
    ["Column", "Kind", "Missing", "%", ""],
    sorted.map((c) => [el("strong", { text: c.column }), c.kind, c.missing, fmtPct(c.missing_pct), bar(c.missing_pct)]),
  ));
  if (data.fully_missing_columns.length) {
    columnsEl.append(el("div", { class: "alert alert-warning small mt-2 mb-0", text: `Entirely empty: ${data.fully_missing_columns.join(", ")}` }));
  }
  clear(patternsEl).append(data.patterns.length
    ? table(["Missing together", "Rows", "%"], data.patterns.map((p) => [
      el("div", { class: "d-flex flex-wrap gap-1" }, p.columns.map((c) => el("span", { class: "badge text-bg-light border", text: c }))), p.rows, fmtPct(p.percent),
    ]))
    : el("div", { class: "text-body-secondary small", text: "No missing values." }));
}

function renderDuplicates(data) {
  metric("dups", "Duplicate rows", fmt(data.duplicate_rows), `${fmtPct(data.duplicate_pct)} · ${data.all_columns ? "all columns" : `${data.columns.length} column(s)`}`, data.duplicate_rows ? "danger" : "success");
  renderSummary();
  const lead = el("p", { class: "small mb-2" }, data.duplicate_rows
    ? `${fmt(data.duplicate_rows)} extra copies across ${fmt(data.groups_count)} group(s) (${fmt(data.rows_in_groups)} rows involved, ${fmt(data.unique_rows)} unique)${data.normalized ? ", ignoring case and whitespace" : ""}.`
    : "No duplicate rows found.");
  clear(dupResult).append(lead);
  if (!data.groups.length) return;
  dupResult.append(table(
    ["Copies", "Row numbers", ...data.columns],
    data.groups.map((g) => [g.size, `${g.row_numbers.join(", ")}${g.size > g.row_numbers.length ? ", …" : ""}`, ...data.columns.map((c) => g.values[c] ?? el("span", { class: "null-cell", text: "null" }))]),
    { classes: "table table-sm table-striped table-hover align-middle mb-0 table-data" },
  ));
  if (data.truncated) dupResult.append(el("div", { class: "small text-body-secondary mt-1", text: `Showing the ${data.groups.length} largest of ${fmt(data.groups_count)} groups.` }));
}

async function loadMissing() {
  const id = ++missingRequest;
  if (!columnsEl.firstChild) columnsEl.append(spinner());
  try {
    const data = await apiFetch(withQuery(`${apiBase}/quality/missing`, { filters: filterQuery() }));
    if (id !== missingRequest) return;
    showFilterError("");
    showMatchCount(data.matched_rows, data.total_rows);
    renderMissing(data);
  } catch (err) {
    if (id !== missingRequest) return;
    if (err.status === 422) showFilterError(err.message);
    clear(columnsEl).append(el("div", { class: "alert alert-danger", text: err.message }));
  }
}

async function loadDuplicates() {
  const id = ++dupRequest;
  clear(dupResult).append(spinner());
  const selected = [...dupColumns.selectedOptions].map((o) => o.value);
  try {
    const data = await apiFetch(withQuery(`${apiBase}/quality/duplicates`, {
      filters: filterQuery(), columns: selected.length ? selected : undefined, normalize: dupNormalize.checked ? "true" : undefined,
    }));
    if (id === dupRequest) renderDuplicates(data);
  } catch (err) {
    if (id === dupRequest) clear(dupResult).append(el("div", { class: "alert alert-danger", text: err.message }));
  }
}

dupForm.addEventListener("submit", (e) => { e.preventDefault(); loadDuplicates(); });
document.getElementById("dup-reset").addEventListener("click", () => {
  [...dupColumns.options].forEach((o) => { o.selected = false; });
  dupNormalize.checked = false;
  loadDuplicates();
});
document.addEventListener("filters-changed", () => { loadMissing(); loadDuplicates(); });

getColumns().then((cols) => cols.forEach((c) => dupColumns.append(el("option", { value: c.name, text: `${c.name} (${c.kind})` })))).catch(() => {});
initFilterPanel();
loadMissing();
loadDuplicates();

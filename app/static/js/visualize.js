/* global Plotly */
import { apiFetch, withQuery } from "./api.js";
import { apiBase, datasetName, getColumns, getFilters } from "./dataset.js";
import { initFilterPanel, showFilterError, showMatchCount } from "./filters.js";
import { clear, el, fmt, spinner } from "./ui.js";

const CATEGORY = ["categorical", "boolean", "text"];
const AGGS = ["count", "sum", "mean", "median", "min", "max"];
const FIELDS = {
  histogram: [{ name: "x", label: "Column", kinds: ["numeric", "datetime"] }, { name: "bins", label: "Bins", type: "number", min: 2, max: 200, value: 30 }],
  bar: [{ name: "x", label: "Category", kinds: [...CATEGORY, "numeric"] }, { name: "y", label: "Value (optional)", kinds: ["numeric"], optional: true }, { name: "agg", label: "Aggregation", options: AGGS }, { name: "top", label: "Top N", type: "number", min: 2, max: 50, value: 20 }],
  line: [{ name: "x", label: "X axis", kinds: ["datetime", "numeric"] }, { name: "y", label: "Y axis (optional)", kinds: ["numeric"], optional: true }, { name: "agg", label: "Aggregation", options: AGGS }, { name: "freq", label: "Interval (dates)", options: ["auto", "hour", "day", "week", "month", "quarter", "year"] }],
  scatter: [{ name: "x", label: "X axis", kinds: ["numeric"] }, { name: "y", label: "Y axis", kinds: ["numeric"], second: true }, { name: "color", label: "Colour by (optional)", kinds: CATEGORY, optional: true }],
  box: [{ name: "y", label: "Value", kinds: ["numeric"] }, { name: "x", label: "Group by (optional)", kinds: CATEGORY, optional: true }, { name: "top", label: "Max groups", type: "number", min: 2, max: 50, value: 20 }],
  pie: [{ name: "x", label: "Slices", kinds: CATEGORY }, { name: "y", label: "Values (optional, summed)", kinds: ["numeric"], optional: true }, { name: "top", label: "Max slices", type: "number", min: 2, max: 50, value: 10 }],
  heatmap: [{ name: "method", label: "Method", options: ["pearson", "spearman"] }],
  missing: [],
};

const form = document.getElementById("chart-form");
const typeSelect = document.getElementById("chart-type");
const fieldsEl = document.getElementById("chart-fields");
const chartEl = document.getElementById("chart");
const metaEl = document.getElementById("chart-meta");
const downloadBtn = document.getElementById("chart-download");
let columns = [];
let requestId = 0;
let currentType = "";

function field(def) {
  const id = `field-${def.name}`;
  let control;
  if (def.kinds) {
    // Prefer low-cardinality kinds first so defaults are meaningful (text columns last).
    const matching = columns.filter((c) => def.kinds.includes(c.kind))
      .sort((a, b) => (a.kind === "text") - (b.kind === "text"));
    control = el("select", { id, name: def.name, class: "form-select form-select-sm" }, [
      def.optional ? el("option", { value: "", text: "— none —" }) : null,
      ...matching.map((c) => el("option", { value: c.name, text: `${c.name} (${c.kind})` })),
    ]);
    if (!def.optional && def.second && matching.length > 1) control.selectedIndex = 1;
    if (!def.optional && !matching.length) control.append(el("option", { value: "", text: "No suitable columns" }));
  } else if (def.options) {
    control = el("select", { id, name: def.name, class: "form-select form-select-sm" }, def.options.map((o) => el("option", { value: o, text: o })));
  } else {
    control = el("input", { id, name: def.name, type: "number", class: "form-control form-control-sm", min: String(def.min), max: String(def.max), value: String(def.value) });
  }
  return el("div", { class: "mb-2" }, [el("label", { for: id, class: "form-label small mb-1", text: def.label }), control]);
}

function renderFields() {
  clear(fieldsEl).append(...FIELDS[typeSelect.value].map(field));
}

function params() {
  const out = { type: typeSelect.value };
  for (const input of fieldsEl.querySelectorAll("select, input")) if (input.value !== "") out[input.name] = input.value;
  const filters = getFilters();
  if (filters.length) out.filters = filters;
  return out;
}

function describeMeta(meta, data) {
  const parts = [`${fmt(meta.rows_used)} rows used`];
  if (data.matched_rows !== data.total_rows) parts.push(`filtered from ${fmt(data.total_rows)}`);
  if (meta.sampled) parts.push(`random sample of ${fmt(meta.points)} points shown`);
  if (meta.groups && meta.groups > meta.points) parts.push(`top ${fmt(meta.points)} of ${fmt(meta.groups)} groups`);
  if (meta.interval) parts.push(`interval: ${meta.interval}`);
  if (meta.binned) parts.push("x values binned");
  if (meta.outliers_hidden) parts.push(`${fmt(meta.outliers_hidden)} outliers beyond whiskers not drawn`);
  return parts.join(" · ");
}

async function render() {
  const id = ++requestId;
  const p = params();
  currentType = p.type;
  chartEl.classList.add("opacity-50");
  if (!chartEl.querySelector(".plot-container")) clear(chartEl).append(spinner("Building chart…"));
  try {
    const data = await apiFetch(withQuery(`${apiBase}/chart`, p));
    if (id !== requestId) return;
    showFilterError("");
    showMatchCount(data.matched_rows, data.total_rows);
    if (!chartEl.querySelector(".plot-container")) clear(chartEl);
    await Plotly.react(chartEl, data.figure.data, data.figure.layout, {
      responsive: true, displaylogo: false,
      toImageButtonOptions: { format: "png", filename: fileName(), scale: 2 },
    });
    metaEl.textContent = describeMeta(data.meta, data);
    downloadBtn.disabled = false;
  } catch (err) {
    if (id !== requestId) return;
    if (err.status === 422 && String(err.details ?? "").includes("filter")) showFilterError(err.message);
    Plotly.purge(chartEl);
    clear(chartEl).append(el("div", { class: "alert alert-warning", text: err.message }));
    metaEl.textContent = "";
    downloadBtn.disabled = true;
  } finally {
    if (id === requestId) chartEl.classList.remove("opacity-50");
  }
}

function fileName() {
  const safe = `${datasetName}-${currentType}`.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return safe || "chart";
}

downloadBtn.addEventListener("click", () => {
  Plotly.downloadImage(chartEl, { format: "png", width: 1400, height: 800, filename: fileName() });
});
typeSelect.addEventListener("change", () => { renderFields(); render(); });
form.addEventListener("submit", (e) => { e.preventDefault(); render(); });
document.addEventListener("filters-changed", render);

initFilterPanel();
getColumns().then((cols) => {
  columns = cols;
  if (!cols.some((c) => c.kind === "numeric" || c.kind === "datetime")) typeSelect.value = "missing";
  renderFields();
  render();
}).catch((err) => clear(chartEl).append(el("div", { class: "alert alert-danger", text: err.message })));

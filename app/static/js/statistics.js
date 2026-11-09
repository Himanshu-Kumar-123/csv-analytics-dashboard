import { apiFetch, withQuery } from "./api.js";
import { apiBase, getFilters } from "./dataset.js";
import { initFilterPanel, showFilterError, showMatchCount } from "./filters.js";
import { clear, el, fmt, fmtBytes, fmtPct, spinner, table } from "./ui.js";

const summaryEl = document.getElementById("stats-summary");
const sectionsEl = document.getElementById("stats-sections");
const matrixEl = document.getElementById("corr-matrix");
const pairsEl = document.getElementById("corr-pairs");
const methodSelect = document.getElementById("corr-method");
let statsRequest = 0;
let corrRequest = 0;

const filterQuery = () => (getFilters().length ? getFilters() : undefined);

function metric(label, value, sub) {
  return el("div", { class: "col-6 col-md-4 col-xl-2" }, el("div", { class: "card card-metric shadow-sm h-100" },
    el("div", { class: "card-body" }, [
      el("div", { class: "metric-label", text: label }),
      el("div", { class: "metric-value", text: value }),
      sub ? el("div", { class: "small text-body-secondary", text: sub }) : null,
    ])));
}

function section(title, count, content) {
  return el("div", { class: "card shadow-sm mb-3" }, el("div", { class: "card-body" }, [
    el("h2", { class: "h6" }, [title, " ", el("span", { class: "badge text-bg-light", text: String(count) })]),
    content,
  ]));
}

const missingCell = (s) => `${fmt(s.missing)} (${fmtPct(s.missing_pct)})`;

function topValues(values) {
  return el("div", { class: "small" }, values.map((v) => el("div", { class: "text-truncate", title: v.value }, [
    el("span", { text: v.value }), " ", el("span", { class: "text-body-secondary", text: `${fmt(v.count)} · ${fmtPct(v.percent)}` }),
  ])));
}

function renderStats(data) {
  const s = data.summary;
  clear(summaryEl).append(
    metric("Rows", fmt(s.rows), data.matched_rows !== data.total_rows ? `filtered from ${fmt(data.total_rows)}` : null),
    metric("Columns", fmt(s.columns)),
    metric("Numeric", fmt(s.kinds.numeric ?? 0)),
    metric("Categorical / text", fmt((s.kinds.categorical ?? 0) + (s.kinds.text ?? 0))),
    metric("Missing cells", fmtPct(s.missing_pct), `${fmt(s.missing_cells)} of ${fmt(s.cells)}`),
    metric("Memory", fmtBytes(s.memory_bytes)),
  );
  const parts = [];
  if (data.numeric.length) {
    parts.push(section("Numeric columns", data.numeric.length, table(
      ["Column", "Count", "Missing", "Mean", "Std", "Min", "Q1", "Median", "Q3", "Max", "IQR", "Skew", "Kurtosis", "Unique", "Zeros", "Outliers"],
      data.numeric.map((c) => [el("strong", { text: c.column }), c.count, missingCell(c), c.mean, c.std, c.min, c.q1, c.median, c.q3, c.max, c.iqr, c.skewness, c.kurtosis, c.unique, c.zeros, c.outliers]),
      { classes: "table table-sm table-striped table-hover align-middle mb-0 table-stats" },
    )));
  }
  if (data.categorical.length) {
    parts.push(section("Categorical & text columns", data.categorical.length, table(
      ["Column", "Kind", "Count", "Missing", "Unique", "Top values", "Length (min / mean / max)", "Entropy"],
      data.categorical.map((c) => [el("strong", { text: c.column }), c.kind, c.count, missingCell(c), c.unique, topValues(c.top_values),
        c.count ? `${fmt(c.min_length)} / ${fmt(c.mean_length)} / ${fmt(c.max_length)}` : "—", c.entropy]),
    )));
  }
  if (data.datetime.length) {
    parts.push(section("Date & time columns", data.datetime.length, table(
      ["Column", "Count", "Missing", "Earliest", "Median", "Latest", "Range (days)", "Unique"],
      data.datetime.map((c) => [el("strong", { text: c.column }), c.count, missingCell(c), c.min, c.median, c.max, c.range_days, c.unique]),
    )));
  }
  if (data.boolean.length) {
    parts.push(section("Boolean columns", data.boolean.length, table(
      ["Column", "Count", "Missing", "True", "False", "True %"],
      data.boolean.map((c) => [el("strong", { text: c.column }), c.count, missingCell(c), c.true_count, c.false_count, fmtPct(c.true_pct)]),
    )));
  }
  clear(sectionsEl).append(...parts);
}

function corrColor(r) {
  if (r === null) return "transparent";
  const alpha = Math.min(1, Math.abs(r)) * 0.85;
  return r >= 0 ? `rgba(13, 110, 253, ${alpha})` : `rgba(220, 53, 69, ${alpha})`;
}

function renderCorrelations(data) {
  clear(matrixEl);
  clear(pairsEl);
  if (data.columns.length < 2) {
    matrixEl.append(el("div", { class: "text-body-secondary small", text: data.message ?? "Not enough numeric columns." }));
    return;
  }
  const head = el("tr", {}, [el("th", {}), ...data.columns.map((c) => el("th", { scope: "col", class: "corr-head", title: c, text: c }))]);
  const rows = data.matrix.map((row, i) => el("tr", {}, [
    el("th", { scope: "row", class: "text-nowrap", text: data.columns[i] }),
    ...row.map((r, j) => {
      const td = el("td", { class: "text-center corr-cell", title: `${data.columns[i]} × ${data.columns[j]}: ${r ?? "n/a"}`, text: r === null ? "—" : r.toFixed(2) });
      td.style.backgroundColor = corrColor(r);
      if (r !== null && Math.abs(r) > 0.55) td.classList.add("text-white");
      return td;
    }),
  ]));
  matrixEl.append(el("table", { class: "table table-sm table-bordered mb-0 table-corr" }, [el("thead", {}, head), el("tbody", {}, rows)]));
  if (data.truncated) matrixEl.append(el("div", { class: "small text-body-secondary mt-1", text: "Showing the first 50 numeric columns." }));
  pairsEl.append(data.pairs.length
    ? el("ol", { class: "list-group list-group-numbered small" }, data.pairs.map((p) => el("li", { class: "list-group-item d-flex justify-content-between gap-2" }, [
      el("span", { class: "text-truncate", text: `${p.a} × ${p.b}` }),
      el("span", { class: `badge ${p.r >= 0 ? "text-bg-primary" : "text-bg-danger"}`, text: p.r.toFixed(3) }),
    ])))
    : el("div", { class: "small text-body-secondary", text: "No pairs with enough overlapping values." }));
}

async function loadStats() {
  const id = ++statsRequest;
  if (!sectionsEl.firstChild) sectionsEl.append(spinner());
  sectionsEl.classList.add("opacity-50");
  try {
    const data = await apiFetch(withQuery(`${apiBase}/statistics`, { filters: filterQuery() }));
    if (id !== statsRequest) return;
    showFilterError("");
    showMatchCount(data.matched_rows, data.total_rows);
    renderStats(data);
  } catch (err) {
    if (id !== statsRequest) return;
    if (err.status === 422) showFilterError(err.message);
    clear(sectionsEl).append(el("div", { class: "alert alert-danger", text: err.message }));
  } finally {
    if (id === statsRequest) sectionsEl.classList.remove("opacity-50");
  }
}

async function loadCorrelations() {
  const id = ++corrRequest;
  clear(matrixEl).append(spinner());
  try {
    const data = await apiFetch(withQuery(`${apiBase}/correlations`, { method: methodSelect.value, filters: filterQuery() }));
    if (id === corrRequest) renderCorrelations(data);
  } catch (err) {
    if (id === corrRequest) clear(matrixEl).append(el("div", { class: "alert alert-danger", text: err.message }));
  }
}

methodSelect.addEventListener("change", loadCorrelations);
document.addEventListener("filters-changed", () => { loadStats(); loadCorrelations(); });
initFilterPanel();
loadStats();
loadCorrelations();

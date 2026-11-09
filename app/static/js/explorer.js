import { apiFetch, withQuery } from "./api.js";
import { apiBase, getFilters } from "./dataset.js";
import { initFilterPanel, showFilterError, showMatchCount } from "./filters.js";
import { clear, el, fmt, spinner } from "./ui.js";

const tableContainer = document.getElementById("data-table");
const summary = document.getElementById("table-summary");
const pageInput = document.getElementById("page-input");
const pageTotal = document.getElementById("page-total");
const pageSizeSelect = document.getElementById("page-size");
const state = { page: 1, pageSize: 50, sort: null, order: "asc", totalPages: 1 };
let requestId = 0;

const KIND_BADGE = { numeric: "primary", categorical: "success", datetime: "warning", boolean: "info", text: "secondary" };

function renderTable(data) {
  const headerCells = data.columns.map((col) => {
    const active = state.sort === col.name;
    const icon = active ? (state.order === "asc" ? "bi-sort-up" : "bi-sort-down") : "bi-arrow-down-up opacity-25";
    const th = el("th", {
      scope: "col", class: "sortable", tabindex: "0",
      "aria-sort": active ? (state.order === "asc" ? "ascending" : "descending") : "none",
      title: `Sort by ${col.name}`,
    }, [
      el("span", { text: col.name }), " ",
      el("i", { class: `bi ${icon}` }),
      el("div", {}, el("span", { class: `badge kind-badge text-bg-${KIND_BADGE[col.kind] ?? "secondary"}`, text: col.kind })),
    ]);
    const toggle = () => {
      if (state.sort !== col.name) { state.sort = col.name; state.order = "asc"; }
      else if (state.order === "asc") state.order = "desc";
      else { state.sort = null; state.order = "asc"; }
      state.page = 1;
      load();
    };
    th.addEventListener("click", toggle);
    th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
    return th;
  });
  const rowNumberHeader = el("th", { scope: "col", class: "text-body-secondary", text: "#" });
  const body = data.rows.map((row, i) => el("tr", {}, [
    el("td", { class: "text-body-secondary", text: fmt(data.first_row + i) }),
    ...data.columns.map((col) => {
      const v = row[col.name];
      if (v === null || v === undefined) return el("td", { class: "null-cell", text: "null" });
      return el("td", { title: String(v), text: typeof v === "number" ? fmt(v) : String(v) });
    }),
  ]));
  clear(tableContainer).append(el("table", { class: "table table-sm table-striped table-hover table-data mb-0" }, [
    el("thead", { class: "table-light" }, el("tr", {}, [rowNumberHeader, ...headerCells])),
    el("tbody", {}, body.length ? body : el("tr", {}, el("td", { colspan: String(data.columns.length + 1), class: "text-center text-body-secondary py-4", text: "No rows match the current filters." }))),
  ]));
}

async function load() {
  const id = ++requestId;
  tableContainer.classList.add("opacity-50");
  if (!tableContainer.firstChild) tableContainer.append(spinner());
  try {
    const data = await apiFetch(withQuery(`${apiBase}/preview`, {
      page: state.page, page_size: state.pageSize, sort: state.sort, order: state.order,
      filters: getFilters().length ? getFilters() : undefined,
    }));
    if (id !== requestId) return;
    showFilterError("");
    state.page = data.page;
    state.totalPages = data.total_pages;
    renderTable(data);
    const last = data.first_row ? data.first_row + data.rows.length - 1 : 0;
    summary.textContent = data.matched_rows
      ? `Showing rows ${fmt(data.first_row)}–${fmt(last)} of ${fmt(data.matched_rows)}${data.matched_rows !== data.total_rows ? ` (filtered from ${fmt(data.total_rows)})` : ""}`
      : "No matching rows";
    showMatchCount(data.matched_rows, data.total_rows);
    pageInput.value = String(data.page);
    pageInput.max = String(data.total_pages);
    pageTotal.textContent = `of ${fmt(data.total_pages)}`;
    document.getElementById("page-first").disabled = data.page <= 1;
    document.getElementById("page-prev").disabled = data.page <= 1;
    document.getElementById("page-next").disabled = data.page >= data.total_pages;
    document.getElementById("page-last").disabled = data.page >= data.total_pages;
  } catch (err) {
    if (id !== requestId) return;
    if (err.status === 422) showFilterError(err.message);
    clear(tableContainer).append(el("div", { class: "alert alert-danger", text: err.message }));
  } finally {
    if (id === requestId) tableContainer.classList.remove("opacity-50");
  }
}

function goTo(page) {
  state.page = Math.min(Math.max(1, page), state.totalPages);
  load();
}

document.getElementById("page-first").addEventListener("click", () => goTo(1));
document.getElementById("page-prev").addEventListener("click", () => goTo(state.page - 1));
document.getElementById("page-next").addEventListener("click", () => goTo(state.page + 1));
document.getElementById("page-last").addEventListener("click", () => goTo(state.totalPages));
pageInput.addEventListener("change", () => goTo(Number(pageInput.value) || 1));
pageSizeSelect.addEventListener("change", () => { state.pageSize = Number(pageSizeSelect.value); state.page = 1; load(); });
document.addEventListener("filters-changed", () => { state.page = 1; load(); });

initFilterPanel();
load();

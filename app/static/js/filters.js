// Filter panel: builds structured conditions; the server validates and applies them.
import { apiFetch, withQuery } from "./api.js";
import { apiBase, getColumns, getFilters, setFilters } from "./dataset.js";
import { clear, el, fmt } from "./ui.js";

const OP_LABELS = {
  eq: "equals", ne: "not equal", gt: ">", gte: "≥", lt: "<", lte: "≤", between: "between",
  in: "is one of", not_in: "is not one of", contains: "contains", starts_with: "starts with",
  is_null: "is missing", not_null: "is not missing",
};

const panel = document.getElementById("filter-panel");
const rowsContainer = document.getElementById("filter-rows");
const countBadge = document.getElementById("filter-count");
const matchLabel = document.getElementById("filter-match");
const errorBox = document.getElementById("filter-error");
let columns = [];

function inputType(kind) {
  if (kind === "numeric") return "number";
  if (kind === "datetime") return "date";
  return "text";
}

function valueEditor(column, op, value) {
  const wrap = el("div", { class: "filter-value flex-grow-1 d-flex gap-2" });
  if (!column || op === "is_null" || op === "not_null") return wrap;
  const kind = column.kind;
  if (kind === "boolean") {
    const select = el("select", { class: "form-select form-select-sm", "aria-label": "Value" }, [
      el("option", { value: "true", text: "true" }), el("option", { value: "false", text: "false" }),
    ]);
    if (value !== undefined) select.value = String(value);
    wrap.append(select);
  } else if (op === "between") {
    const [a, b] = Array.isArray(value) ? value : ["", ""];
    wrap.append(
      el("input", { type: inputType(kind), class: "form-control form-control-sm", "aria-label": "Minimum", placeholder: "min", value: String(a ?? "").slice(0, kind === "datetime" ? 10 : undefined), step: "any" }),
      el("input", { type: inputType(kind), class: "form-control form-control-sm", "aria-label": "Maximum", placeholder: "max", value: String(b ?? "").slice(0, kind === "datetime" ? 10 : undefined), step: "any" }),
    );
  } else if (op === "in" || op === "not_in") {
    const input = el("input", { type: "text", class: "form-control form-control-sm", "aria-label": "Values (comma separated)", placeholder: "value1, value2, …", value: Array.isArray(value) ? value.join(", ") : "" });
    const listId = `values-${Math.random().toString(36).slice(2)}`;
    input.setAttribute("list", listId);
    const datalist = el("datalist", { id: listId });
    apiFetch(withQuery(`${apiBase}/columns/${encodeURIComponent(column.name)}/values`, { top: 50 }))
      .then((res) => res.values.forEach((v) => datalist.append(el("option", { value: String(v.value) }))))
      .catch(() => {});
    wrap.append(input, datalist);
  } else {
    const shown = value === undefined || value === null ? "" : String(value).slice(0, kind === "datetime" ? 10 : undefined);
    wrap.append(el("input", { type: inputType(kind), class: "form-control form-control-sm", "aria-label": "Value", value: shown, step: "any" }));
  }
  return wrap;
}

function addRow(condition = {}) {
  const row = el("div", { class: "filter-row d-flex flex-wrap flex-md-nowrap gap-2 align-items-center" });
  const colSelect = el("select", { class: "form-select form-select-sm", style: "max-width: 16rem", "aria-label": "Column" },
    columns.map((c) => el("option", { value: c.name, text: `${c.name} (${c.kind})` })));
  const opSelect = el("select", { class: "form-select form-select-sm", style: "max-width: 11rem", "aria-label": "Operator" });
  const remove = el("button", { type: "button", class: "btn btn-sm btn-outline-secondary", "aria-label": "Remove condition" }, el("i", { class: "bi bi-x" }));
  let editor = el("div");

  const refreshOps = (selectedOp) => {
    const column = columns.find((c) => c.name === colSelect.value);
    clear(opSelect);
    (column?.operators ?? []).forEach((op) => opSelect.append(el("option", { value: op, text: OP_LABELS[op] ?? op })));
    if (selectedOp && column?.operators.includes(selectedOp)) opSelect.value = selectedOp;
  };
  const refreshEditor = (value) => {
    const column = columns.find((c) => c.name === colSelect.value);
    const next = valueEditor(column, opSelect.value, value);
    editor.replaceWith(next);
    editor = next;
  };

  if (condition.column) colSelect.value = condition.column;
  refreshOps(condition.op);
  row.append(colSelect, opSelect, editor, remove);
  refreshEditor(condition.value);
  colSelect.addEventListener("change", () => { refreshOps(); refreshEditor(); });
  opSelect.addEventListener("change", () => refreshEditor());
  remove.addEventListener("click", () => row.remove());
  rowsContainer.append(row);
}

function readRows() {
  const conditions = [];
  for (const row of rowsContainer.querySelectorAll(".filter-row")) {
    const [colSelect, opSelect] = row.querySelectorAll("select");
    const column = columns.find((c) => c.name === colSelect.value);
    const op = opSelect.value;
    const inputs = [...row.querySelectorAll(".filter-value input, .filter-value select")];
    const cond = { column: column.name, op };
    if (op === "between") {
      if (inputs.some((i) => i.value === "")) throw new Error(`Enter both bounds for "${column.name}".`);
      cond.value = inputs.map((i) => (column.kind === "numeric" ? Number(i.value) : i.value));
    } else if (op === "in" || op === "not_in") {
      cond.value = inputs[0].value.split(",").map((v) => v.trim()).filter(Boolean);
      if (!cond.value.length) throw new Error(`Enter at least one value for "${column.name}".`);
    } else if (op !== "is_null" && op !== "not_null") {
      if (inputs[0].value === "") throw new Error(`Enter a value for "${column.name}".`);
      cond.value = column.kind === "numeric" ? Number(inputs[0].value) : column.kind === "boolean" ? inputs[0].value === "true" : inputs[0].value;
    }
    conditions.push(cond);
  }
  return conditions;
}

function updateBadge(filters) {
  countBadge.textContent = String(filters.length);
  countBadge.classList.toggle("d-none", filters.length === 0);
}

export function showMatchCount(matched, total) {
  if (!matchLabel) return;
  matchLabel.textContent = getFilters().length ? `${fmt(matched)} of ${fmt(total)} rows match` : "";
}

export function showFilterError(message) {
  if (!errorBox) return;
  errorBox.textContent = message || "";
  errorBox.classList.toggle("d-none", !message);
  if (message) window.bootstrap.Collapse.getOrCreateInstance("#filter-body", { toggle: false }).show();
}

export async function initFilterPanel() {
  if (!panel) return;
  columns = await getColumns();
  const current = getFilters();
  current.forEach((c) => addRow(c));
  updateBadge(current);
  if (current.length) window.bootstrap.Collapse.getOrCreateInstance("#filter-body", { toggle: false }).show();
  document.getElementById("filter-add").addEventListener("click", () => addRow());
  document.getElementById("filter-apply").addEventListener("click", () => {
    try {
      const filters = readRows();
      showFilterError("");
      updateBadge(filters);
      setFilters(filters);
    } catch (err) {
      showFilterError(err.message);
    }
  });
  document.getElementById("filter-clear").addEventListener("click", () => {
    clear(rowsContainer);
    showFilterError("");
    updateBadge([]);
    setFilters([]);
  });
}

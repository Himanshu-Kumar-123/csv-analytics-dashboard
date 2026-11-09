// Shared DOM helpers. Data is always inserted with textContent, never innerHTML.
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function toast(message, variant = "danger") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const body = el("div", { class: "d-flex" }, [
    el("div", { class: "toast-body", text: message }),
    el("button", { type: "button", class: "btn-close btn-close-white me-2 m-auto", "data-bs-dismiss": "toast", "aria-label": "Close" }),
  ]);
  const node = el("div", { class: `toast align-items-center text-bg-${variant} border-0`, role: "alert", "aria-live": "assertive", "aria-atomic": "true" }, body);
  container.append(node);
  const instance = window.bootstrap.Toast.getOrCreateInstance(node, { delay: 6000 });
  node.addEventListener("hidden.bs.toast", () => node.remove());
  instance.show();
}

export function spinner(label = "Loading…") {
  return el("div", { class: "d-flex align-items-center gap-2 text-body-secondary py-3" }, [
    el("div", { class: "spinner-border spinner-border-sm", role: "status", "aria-hidden": "true" }),
    el("span", { text: label }),
  ]);
}

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });
const intFormat = new Intl.NumberFormat();

export function fmt(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? intFormat.format(value) : numberFormat.format(value);
  return String(value);
}

export function fmtPct(value) {
  if (value === null || value === undefined) return "—";
  return `${numberFormat.format(value)}%`;
}

export function fmtBytes(bytes) {
  if (!Number.isFinite(bytes)) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function table(headers, rows, { classes = "table table-sm table-striped table-hover align-middle mb-0" } = {}) {
  const thead = el("thead", {}, el("tr", {}, headers.map((h) => el("th", { scope: "col", text: h }))));
  const tbody = el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) => (c instanceof Node ? el("td", {}, c) : el("td", { text: fmt(c) }))))));
  return el("div", { class: "table-responsive" }, el("table", { class: classes }, [thead, tbody]));
}

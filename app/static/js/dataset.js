// Dataset page context + shared filter state (stored per dataset in sessionStorage).
const root = document.getElementById("dataset-root");
export const datasetId = root?.dataset.datasetId ?? "";
export const datasetName = root?.dataset.datasetName ?? "";
export const totalRows = Number(root?.dataset.totalRows ?? 0);
export const apiBase = `/api/v1/datasets/${encodeURIComponent(datasetId)}`;

const storageKey = `csv-dashboard:filters:${datasetId}`;

export function getFilters() {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(storageKey) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function setFilters(filters) {
  if (filters.length) sessionStorage.setItem(storageKey, JSON.stringify(filters));
  else sessionStorage.removeItem(storageKey);
  document.dispatchEvent(new CustomEvent("filters-changed", { detail: { filters } }));
}

let columnsPromise = null;
export function getColumns() {
  if (!columnsPromise) {
    columnsPromise = fetch(`${apiBase}/columns`, { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Could not load columns."))))
      .then((body) => body.columns);
  }
  return columnsPromise;
}

// Export menu: downloads summaries for the current filters without navigating away.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-export]");
  if (!button) return;
  const { toast } = await import("./ui.js");
  const kind = button.dataset.export;
  const path = kind === "report" ? "report.pdf" : `${kind}.csv`;
  const params = new URLSearchParams();
  if (getFilters().length) params.set("filters", JSON.stringify(getFilters()));
  const url = `${apiBase}/export/${path}${params.toString() ? `?${params}` : ""}`;
  button.disabled = true;
  try {
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message ?? `Export failed (${response.status}).`);
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? path;
    const objectUrl = URL.createObjectURL(await response.blob());
    const link = Object.assign(document.createElement("a"), { href: objectUrl, download: filename });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } catch (err) {
    toast(err.message);
  } finally {
    button.disabled = false;
  }
});

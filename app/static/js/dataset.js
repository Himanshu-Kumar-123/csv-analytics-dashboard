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

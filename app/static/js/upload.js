import { apiFetch, getCsrfToken } from "./api.js";
import { clear, el, fmt, fmtBytes, spinner, toast } from "./ui.js";

const MAX_MB = Number(document.getElementById("upload-script").dataset.maxMb || 50);
const form = document.getElementById("upload-form");
const dropZone = document.getElementById("drop-zone");
const dropLabel = document.getElementById("drop-zone-label");
const fileInput = document.getElementById("file-input");
const nameInput = document.getElementById("dataset-name");
const button = document.getElementById("upload-button");
const progress = document.getElementById("upload-progress");
const progressBar = progress.querySelector(".progress-bar");
const errorBox = document.getElementById("upload-error");
const listContainer = document.getElementById("dataset-list");
const countBadge = document.getElementById("dataset-count");
const samplesContainer = document.getElementById("samples");
const deleteModalEl = document.getElementById("delete-modal");
const deleteModal = new window.bootstrap.Modal(deleteModalEl);
let selectedFile = null;
let pendingDelete = null;

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.toggle("d-none", !message);
}

function validateFile(file) {
  if (!file) return "Please choose a file.";
  if (!file.name.toLowerCase().endsWith(".csv")) return "Only .csv files are supported.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_MB * 1024 * 1024) return `File exceeds the ${MAX_MB} MB limit.`;
  return null;
}

function selectFile(file) {
  const error = validateFile(file);
  selectedFile = error ? null : file;
  dropLabel.textContent = file ? `${file.name} (${fmtBytes(file.size)})` : "Drag & drop a CSV file here";
  showError(error || "");
  button.disabled = Boolean(error);
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));
["dragenter", "dragover"].forEach((evt) => dropZone.addEventListener(evt, (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
}));
["dragleave", "drop"].forEach((evt) => dropZone.addEventListener(evt, (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
}));
dropZone.addEventListener("drop", (e) => selectFile(e.dataTransfer.files[0]));

function uploadWithProgress(formData) {
  // XMLHttpRequest is used (instead of fetch) because it reports upload progress.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/datasets");
    xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.addEventListener("progress", (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round((e.loaded / e.total) * 100);
      progressBar.style.width = `${pct}%`;
      progressBar.textContent = pct < 100 ? `${pct}%` : "Processing…";
    });
    xhr.addEventListener("load", () => {
      let body = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error(body?.error?.message || `Upload failed (${xhr.status}).`));
    });
    xhr.addEventListener("error", () => reject(new Error("Network error during upload.")));
    xhr.send(formData);
  });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const error = validateFile(selectedFile);
  if (error) { showError(error); return; }
  const formData = new FormData();
  formData.append("file", selectedFile);
  if (nameInput.value.trim()) formData.append("name", nameInput.value.trim());
  button.disabled = true;
  showError("");
  progress.classList.remove("d-none");
  progressBar.style.width = "0%";
  try {
    const dataset = await uploadWithProgress(formData);
    window.location.href = `/datasets/${encodeURIComponent(dataset.id)}`;
  } catch (err) {
    showError(err.message);
    button.disabled = false;
  } finally {
    progress.classList.add("d-none");
  }
});

function renderDatasets(datasets) {
  countBadge.textContent = String(datasets.length);
  clear(listContainer);
  if (!datasets.length) {
    listContainer.append(el("p", { class: "text-body-secondary mb-0", text: "No datasets yet. Upload a CSV or load a sample to get started." }));
    return;
  }
  const rows = datasets.map((d) => {
    const link = el("a", { href: `/datasets/${encodeURIComponent(d.id)}`, class: "fw-semibold text-decoration-none", text: d.name });
    const nameCell = el("td", {}, [link, d.is_sample ? el("span", { class: "badge text-bg-info ms-2", text: "sample" }) : null,
      el("div", { class: "small text-body-secondary text-truncate", style: "max-width: 16rem", text: d.original_filename })]);
    const del = el("button", {
      type: "button", class: "btn btn-sm btn-outline-danger", "aria-label": `Delete ${d.name}`,
      onclick: () => { pendingDelete = d; document.getElementById("delete-modal-name").textContent = d.name; deleteModal.show(); },
    }, el("i", { class: "bi bi-trash" }));
    return el("tr", {}, [
      nameCell,
      el("td", { class: "text-end", text: fmt(d.rows) }),
      el("td", { class: "text-end", text: fmt(d.columns) }),
      el("td", { class: "text-end", text: fmtBytes(d.size_bytes) }),
      el("td", { text: new Date(d.created_at).toLocaleString() }),
      el("td", { class: "text-end" }, del),
    ]);
  });
  const thead = el("thead", {}, el("tr", {}, ["Name", "Rows", "Columns", "Size", "Uploaded", ""].map((h, i) =>
    el("th", { scope: "col", class: i >= 1 && i <= 3 ? "text-end" : "", text: h }))));
  listContainer.append(el("div", { class: "table-responsive" }, el("table", { class: "table table-hover align-middle mb-0" }, [thead, el("tbody", {}, rows)])));
}

async function loadDatasets() {
  clear(listContainer).append(spinner());
  try {
    const { datasets } = await apiFetch("/api/v1/datasets");
    renderDatasets(datasets);
  } catch (err) {
    clear(listContainer).append(el("div", { class: "alert alert-danger", text: err.message }));
  }
}

async function loadSamples() {
  try {
    const { samples } = await apiFetch("/api/v1/samples");
    clear(samplesContainer);
    for (const s of samples) {
      const btn = el("button", { type: "button", class: "btn btn-sm btn-outline-primary flex-shrink-0", text: "Load" });
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Loading…";
        try {
          const dataset = await apiFetch(`/api/v1/samples/${encodeURIComponent(s.key)}`, { method: "POST" });
          window.location.href = `/datasets/${encodeURIComponent(dataset.id)}`;
        } catch (err) {
          toast(err.message);
          btn.disabled = false;
          btn.textContent = "Load";
        }
      });
      samplesContainer.append(el("div", { class: "list-group-item d-flex justify-content-between align-items-start gap-3 px-0" }, [
        el("div", {}, [el("div", { class: "fw-semibold", text: s.title }), el("div", { class: "small text-body-secondary", text: s.description })]),
        btn,
      ]));
    }
  } catch (err) {
    clear(samplesContainer).append(el("div", { class: "text-danger small", text: err.message }));
  }
}

document.getElementById("delete-confirm").addEventListener("click", async () => {
  if (!pendingDelete) return;
  try {
    await apiFetch(`/api/v1/datasets/${encodeURIComponent(pendingDelete.id)}`, { method: "DELETE" });
    toast(`Deleted "${pendingDelete.name}".`, "success");
    loadDatasets();
  } catch (err) {
    toast(err.message);
  } finally {
    pendingDelete = null;
    deleteModal.hide();
  }
});

loadDatasets();
loadSamples();

/** CB-06: Leaflet map pin picker modal. */

let mapInstance = null;
let marker = null;
let onConfirmCallback = null;
let suppressComposerUntil = 0;

function getModalElements() {
  return {
    modal: document.getElementById("map-picker-modal"),
    mapEl: document.getElementById("map-picker-map"),
    confirmBtn: document.getElementById("map-picker-confirm"),
    cancelBtn: document.getElementById("map-picker-cancel"),
  };
}

/** Block taps/clicks from reaching the composer right after the modal closes. */
function suppressComposerPointerEvents(ms = 900) {
  const chatWidget = document.getElementById("chat-widget");
  if (!chatWidget) return;
  suppressComposerUntil = Date.now() + ms;
  chatWidget.style.pointerEvents = "none";
  window.setTimeout(() => {
    if (Date.now() >= suppressComposerUntil) {
      chatWidget.style.pointerEvents = "";
    }
  }, ms);
}

export function isComposerInteractionSuppressed() {
  return Date.now() < suppressComposerUntil;
}

function ensureMap(lat, lng) {
  const { mapEl } = getModalElements();
  if (!mapEl || !globalThis.L) return;

  if (mapInstance) {
    mapInstance.setView([lat, lng], 13);
    if (marker) marker.setLatLng([lat, lng]);
    return;
  }

  mapInstance = globalThis.L.map(mapEl).setView([lat, lng], 13);
  globalThis.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(mapInstance);

  marker = globalThis.L.marker([lat, lng], { draggable: true }).addTo(mapInstance);
  mapInstance.on("click", (e) => {
    marker.setLatLng(e.latlng);
  });
}

export function openMapPicker({ defaultLat = 27.7172, defaultLng = 85.324, onConfirm }) {
  const { modal, confirmBtn, cancelBtn } = getModalElements();
  if (!modal) return;

  onConfirmCallback = onConfirm;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");

  setTimeout(() => {
    ensureMap(defaultLat, defaultLng);
    mapInstance?.invalidateSize();
  }, 80);

  const handleConfirm = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!marker || !onConfirmCallback) return;
    const { lat, lng } = marker.getLatLng();
    suppressComposerPointerEvents();
    onConfirmCallback({ lat, lng });
    window.requestAnimationFrame(() => closeMapPicker());
  };

  const handleCancel = (event) => {
    event.preventDefault();
    event.stopPropagation();
    closeMapPicker();
  };

  confirmBtn?.replaceWith(confirmBtn.cloneNode(true));
  cancelBtn?.replaceWith(cancelBtn.cloneNode(true));
  const fresh = getModalElements();
  fresh.confirmBtn?.addEventListener("click", handleConfirm);
  fresh.cancelBtn?.addEventListener("click", handleCancel);
}

export function closeMapPicker() {
  const { modal } = getModalElements();
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  onConfirmCallback = null;
  suppressComposerPointerEvents();
}

export function extendComposerInteractionSuppression(ms = 900) {
  suppressComposerPointerEvents(ms);
}

export function initMapPicker() {
  const { modal } = getModalElements();
  if (!modal) return;
  modal.addEventListener("click", (e) => {
    if (e.target !== modal) return;
    e.preventDefault();
    e.stopPropagation();
    closeMapPicker();
  });
  const panel = modal.querySelector(".map-picker-panel");
  panel?.addEventListener("click", (e) => {
    e.stopPropagation();
  });
}

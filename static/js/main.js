// Update label nama file yang dipilih
const fileInput = document.getElementById("file-input");
const fileboxName = document.getElementById("filebox-name");

if (fileInput && fileboxName) {
  fileInput.addEventListener("change", () => {
    fileboxName.textContent = fileInput.files.length
      ? fileInput.files[0].name
      : "Tidak Ada File Yang Dipilih";
  });
}

// Modal saran pengendalian
const btnSaran = document.getElementById("btn-saran");
const modalOverlay = document.getElementById("modal-overlay");
const modalClose = document.getElementById("modal-close");

function openModal() {
  if (modalOverlay) modalOverlay.classList.add("is-open");
}

function closeModal() {
  if (modalOverlay) modalOverlay.classList.remove("is-open");
}

if (btnSaran) btnSaran.addEventListener("click", openModal);
if (modalClose) modalClose.addEventListener("click", closeModal);

if (modalOverlay) {
  modalOverlay.addEventListener("click", (e) => {
    if (e.target === modalOverlay) closeModal();
  });
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

// Form upload: validasi ukuran sisi klien + indikator "memproses" untuk video
window.addEventListener("pageshow", () => {
  const ov = document.getElementById("loading-overlay");
  if (ov) ov.classList.remove("is-open");
});

const uploadForm = document.querySelector(".upload-form");
const loadingOverlay = document.getElementById("loading-overlay");
const MAX_IMAGE_MB = 16;
const MAX_VIDEO_MB = 200;

if (uploadForm && fileInput) {
  uploadForm.addEventListener("submit", (e) => {
    const f = fileInput.files[0];
    if (!f) return;
    const isVideo =
      /\.(mp4|avi|mov|mkv)$/i.test(f.name) || f.type.startsWith("video/");
    const limit = (isVideo ? MAX_VIDEO_MB : MAX_IMAGE_MB) * 1024 * 1024;
    if (f.size > limit) {
      e.preventDefault();
      alert(
        "Ukuran file terlalu besar. Batas " +
          (isVideo ? "video " + MAX_VIDEO_MB : "gambar " + MAX_IMAGE_MB) +
          " MB.",
      );
      return;
    }
    if (isVideo && loadingOverlay) loadingOverlay.classList.add("is-open");
  });
}

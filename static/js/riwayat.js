/* Riwayat: tab, pencarian, pop-up detail video/foto, dan seek ke waktu tracking.
   Tidak mengubah model YOLOv8, ByteTrack, atau data JSON yang disimpan. */
(() => {
  "use strict";

  const cards = Array.from(document.querySelectorAll(".riwayat-card"));
  const tabs = Array.from(document.querySelectorAll(".riwayat-tab"));
  const search = document.getElementById("riwayat-search");
  const counter = document.getElementById("riwayat-filter-count");
  const noMatch = document.getElementById("riwayat-no-match");
  let activeType = "semua";

  const applyFilters = () => {
    const keyword = (search?.value || "").toLocaleLowerCase("id-ID").trim();
    let visible = 0;
    cards.forEach((card) => {
      const typeMatch =
        activeType === "semua" || card.dataset.kind === activeType;
      const searchMatch =
        !keyword || (card.dataset.search || "").includes(keyword);
      card.hidden = !(typeMatch && searchMatch);
      if (!card.hidden) visible++;
    });
    if (counter)
      counter.textContent = `Menampilkan ${visible} dari ${cards.length} riwayat`;
    if (noMatch) noMatch.hidden = visible > 0;
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      activeType = tab.dataset.filter || "semua";
      tabs.forEach((t) => {
        const selected = t === tab;
        t.classList.toggle("is-active", selected);
        t.setAttribute("aria-selected", String(selected));
      });
      applyFilters();
    });
  });
  search?.addEventListener("input", applyFilters);
  applyFilters();

  const toSeconds = (mm, ss) => Number(mm) * 60 + Number(ss);
  function parseRange(text) {
    // Contoh dari riwayat.json: "muncul 0:16–0:19"
    const match = (text || "").match(/(\d+):(\d+)\s*[–—-]\s*(\d+):(\d+)/);
    if (!match) return null;
    return {
      start: toSeconds(match[1], match[2]),
      end: toSeconds(match[3], match[4]),
    };
  }

  function buildTimeline(dialog) {
    const timeline = dialog.querySelector(".riwayat-timeline-block");
    if (!timeline || timeline.dataset.rendered === "true") return;
    const holder = timeline.querySelector(".riwayat-timeline-list");
    const duration = Number(timeline.dataset.duration);
    if (!holder || !Number.isFinite(duration) || duration <= 0) return;

    dialog.querySelectorAll(".riwayat-track-row").forEach((tr) => {
      const range = parseRange(tr.dataset.range);
      if (!range) return;
      const start = Math.max(0, Math.min(duration, range.start));
      const end = Math.max(start, Math.min(duration, range.end));
      const row = document.createElement("div");
      row.className = "riwayat-timeline-row";
      const label = document.createElement("strong");
      label.textContent =
        (tr.dataset.track || "").match(/#\d+$/)?.[0] ||
        tr.dataset.track ||
        "Objek";
      const track = document.createElement("div");
      track.className = "riwayat-timeline-track";
      const bar = document.createElement("span");
      bar.className = "riwayat-timeline-bar";
      bar.style.left = `${(100 * start) / duration}%`;
      // Tanda titik minimal 4px untuk interval yang dibulatkan pada detik sama.
      bar.style.width = `${(100 * (end - start)) / duration}%`;
      bar.style.background = tr.dataset.color || "#C08A34";
      bar.title = `${tr.dataset.track}: ${tr.dataset.range}`;
      track.appendChild(bar);
      row.append(label, track);
      holder.appendChild(row);
    });
    timeline.dataset.rendered = "true";
  }

  function closeDialog(dialog) {
    if (!dialog) return;
    const video = dialog.querySelector(".riwayat-detail-media video");
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
    if (dialog.open) dialog.close();
  }

  document.querySelectorAll("[data-open-riwayat]").forEach((button) => {
    button.addEventListener("click", () => {
      const dialog = document.getElementById(button.dataset.openRiwayat);
      if (!dialog || typeof dialog.showModal !== "function") return;
      dialog.showModal();
      buildTimeline(dialog);
      const video = dialog.querySelector(
        ".riwayat-detail-media video[data-src]",
      );
      if (video && !video.hasAttribute("src")) {
        video.src = video.dataset.src;
        video.load();
      }
    });
  });
  document.querySelectorAll(".riwayat-dialog").forEach((dialog) => {
    dialog
      .querySelector("[data-close-riwayat]")
      ?.addEventListener("click", () => closeDialog(dialog));
    // Klik di luar konten dialog (backdrop) menutup detail.
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog(dialog);
    });
    // Escape menutup native dialog; reset media setelah benar-benar tertutup.
    dialog.addEventListener("close", () => {
      const video = dialog.querySelector(".riwayat-detail-media video");
      if (video) {
        video.pause();
        video.removeAttribute("src");
        video.load();
      }
    });
    dialog.querySelectorAll("[data-jump]").forEach((jumpButton) => {
      jumpButton.addEventListener("click", () => {
        const row = jumpButton.closest(".riwayat-track-row");
        const range = parseRange(row?.dataset.range);
        const video = dialog.querySelector(".riwayat-detail-media video");
        if (!video || !range || !video.src) return;
        const seek = () => {
          video.currentTime = Math.min(
            Math.max(0, range.start),
            Number.isFinite(video.duration) ? video.duration : range.start,
          );
          video.play().catch(() => {}); // Browser dapat menolak autoplay.
        };
        if (video.readyState >= 1) seek();
        else video.addEventListener("loadedmetadata", seek, { once: true });
      });
    });
  });
})();

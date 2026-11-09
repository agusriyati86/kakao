"""
app.py
Controller utama aplikasi deteksi hama dan penyakit kakao (YOLOv8).

Mode deteksi:
  1. Unggah gambar / foto kamera  -> /klasifikasi (riwayat disimpan)
  2. Unggah video                 -> /klasifikasi (inferensi per frame, tanpa tracking)
  3. Kamera realtime di browser   -> /kamera + /api/deteksi-frame
"""
import logging
import os
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    CLASS_COLORS,
    CLASS_LABEL,
    CLASS_ORDER,
    CLASS_SARAN,
    CONFIDENCE_THRESHOLD,
    IMAGE_SIZE,
    INFO_KELAS,
    IS_PRODUCTION,
    MAX_FRAME_BYTES,
    MAX_IMAGE_BYTES,
    MAX_VIDEO_BYTES,
    PHOTO_CAPTURE_MAX_SIDE,
    PHOTO_JPEG_QUALITY,
    REALTIME_DEFAULT_FPS,
    REALTIME_FPS_OPTIONS,
    REALTIME_JPEG_QUALITY,
    REALTIME_SEND_MAX_SIDE,
    SARAN_SUMBER,
    VIDEO_FRAME_STRIDE,
    VIDEO_MAX_DURATION,
    VIDEO_MAX_SIDE,
)
from domain import (
    CitraKakao,
    HasilDeteksi,
    ImageProcessor,
    RiwayatDeteksi,
    VideoProcessor,
    VideoTidakValid,
    YOLOv8Detector,
    cari_ffmpeg,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kakao")

# =========================================================
# PATH
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"   # hanya sementara (video)
RESULT_FOLDER = BASE_DIR / "static" / "results"
MODEL_PATH = Path(os.getenv("MODEL_PATH", BASE_DIR / "models" / "best.pt"))
RIWAYAT_FILE = BASE_DIR / "static" / "riwayat.json"

for folder in (UPLOAD_FOLDER, RESULT_FOLDER, RIWAYAT_FILE.parent):
    folder.mkdir(parents=True, exist_ok=True)

# =========================================================
# FLASK
# =========================================================
app = Flask(__name__)

_secret = os.getenv("SECRET_KEY")
if not _secret:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY wajib diisi pada APP_ENV=production. "
            'Buat dengan: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    # Mode pengembangan: kunci acak per proses (sesi/flash reset saat restart).
    _secret = secrets.token_hex(32)
    logger.warning("SECRET_KEY tidak diatur; memakai kunci acak sementara.")
app.config["SECRET_KEY"] = _secret
app.config["MAX_CONTENT_LENGTH"] = MAX_VIDEO_BYTES + 1024 * 1024

# =========================================================
# MODEL
# =========================================================
detector: Optional[YOLOv8Detector] = None
video_processor: Optional[VideoProcessor] = None
model_error: Optional[str] = None
IMAGE_PROCESSOR = ImageProcessor(id="default", targetSize=(IMAGE_SIZE, IMAGE_SIZE))


def muat_model() -> None:
    """Memuat best.pt. Jika gagal, aplikasi tetap berjalan dan melaporkan galat."""
    global detector, video_processor, model_error
    if not MODEL_PATH.is_file():
        model_error = f"File model tidak ditemukan: {MODEL_PATH}"
        logger.error(model_error)
        return
    try:
        detector = YOLOv8Detector(
            modelPath=str(MODEL_PATH),
            confidenceThreshold=CONFIDENCE_THRESHOLD,
            imageSize=IMAGE_SIZE,
        )
        video_processor = VideoProcessor(
            detector=detector,
            colors=CLASS_COLORS,
            labels=CLASS_LABEL,
            frameStride=VIDEO_FRAME_STRIDE,
            maxSide=VIDEO_MAX_SIDE,
            maxDurationSec=VIDEO_MAX_DURATION,
        )
        model_error = None
        logger.info("Model dimuat: %s", MODEL_PATH)
    except Exception as exc:  # noqa: BLE001
        detector = None
        video_processor = None
        model_error = f"Model gagal dimuat: {exc}"
        logger.exception("Model gagal dimuat.")


muat_model()

# Hanya satu video diproses pada satu waktu (beban CPU/RAM besar).
VIDEO_SLOT = threading.Lock()


# =========================================================
# UTILITAS
# =========================================================
def allowed_image(filename: str) -> bool:
    """Memeriksa ekstensi gambar."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def allowed_video(filename: str) -> bool:
    """Memeriksa ekstensi video."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def susun_ringkasan_dan_saran(counts: dict):
    """Menyusun ringkasan dan saran hasil deteksi."""
    ringkasan = [
        {
            "nama": CLASS_LABEL[class_name],
            "jumlah": counts[class_name],
            "warna": CLASS_COLORS[class_name],
        }
        for class_name in CLASS_ORDER
    ]
    kelas_terdeteksi = [c for c in CLASS_ORDER if counts[c] > 0]
    saran_list = [
        {
            "nama": CLASS_LABEL[c],
            "warna": CLASS_COLORS[c],
            "poin": CLASS_SARAN.get(c, []),
        }
        for c in kelas_terdeteksi
    ]
    return ringkasan, kelas_terdeteksi, saran_list


def buat_timestamp() -> str:
    """Membuat ID berdasarkan waktu."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def path_dalam_folder(folder: Path, nama: str) -> Optional[Path]:
    """Mengembalikan path file di dalam folder, atau None jika tidak aman.

    Hanya nama file (tanpa direktori) yang dipakai, lalu dipastikan hasil
    resolve tetap berada di dalam folder milik aplikasi.
    """
    nama_aman = Path(str(nama)).name
    if not nama_aman or nama_aman in {".", ".."}:
        return None
    kandidat = (folder / nama_aman).resolve()
    try:
        kandidat.relative_to(folder.resolve())
    except ValueError:
        return None
    return kandidat


def hapus_file_aman(folder: Path, nama: str) -> None:
    """Menghapus file hanya jika berada di folder aplikasi."""
    target = path_dalam_folder(folder, nama)
    if target is not None and target.is_file():
        try:
            target.unlink()
        except OSError:
            logger.exception("Gagal menghapus %s", target)


def model_siap() -> bool:
    """True jika model termuat. Jika tidak, tampilkan pesan ke pengguna."""
    if detector is None:
        flash(model_error or "Model deteksi belum tersedia.")
        return False
    return True


def susun_hasil(
    tipe: str,
    result_filename: str,
    counts: dict,
    deteksi_list: list,
    detections: list,
    extra: dict,
) -> tuple:
    """Menyusun dict hasil untuk template dan data riwayat (gambar & video)."""
    ringkasan, kelas_terdeteksi, saran_list = susun_ringkasan_dan_saran(counts)
    hasil_label = (
        ", ".join(CLASS_LABEL[c] for c in kelas_terdeteksi) or "Tidak terdeteksi"
    )
    confidence_tertinggi = max((d.getConfidence() for d in detections), default=0.0)
    jumlah_total = sum(counts.values())

    hasil = HasilDeteksi(
        gambarHasil=f"results/{result_filename}",
        hasil=hasil_label,
        confidence=confidence_tertinggi * 100,
        waktu=datetime.now(),
        detections=detections,
    ).tampilkanHasil()
    hasil.update(
        {
            "tipe": tipe,
            "jumlah_total": jumlah_total,
            "deteksi_list": deteksi_list,
            "ringkasan": ringkasan,
            "kelas_terdeteksi": kelas_terdeteksi,
            "saran_list": saran_list,
            "saran_sumber": SARAN_SUMBER,
        }
    )
    hasil.update(extra)
    record = {
        "tipe": tipe,
        "waktu": hasil["waktu"],
        "gambar_hasil": f"results/{result_filename}",
        "hasil": hasil_label,
        "confidence": round(confidence_tertinggi * 100, 1),
        "jumlah_total": jumlah_total,
        "deteksi_list": deteksi_list,
    }
    return hasil, record


# =========================================================
# ERROR HANDLER
# =========================================================
@app.errorhandler(413)
def file_terlalu_besar(_error):
    if request.path.startswith("/api/"):
        return jsonify(ok=False, pesan="Ukuran data terlalu besar."), 413
    flash(
        f"Ukuran file terlalu besar. Batas gambar {MAX_IMAGE_BYTES // (1024 * 1024)} MB "
        f"dan video {MAX_VIDEO_BYTES // (1024 * 1024)} MB."
    )
    return redirect(url_for("klasifikasi"))


# =========================================================
# HOME & HEALTH
# =========================================================
@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")


@app.route("/health", methods=["GET"])
def health():
    """Pemeriksaan status untuk hosting / pengujian."""
    return jsonify(
        status="ok" if detector is not None else "model_tidak_tersedia",
        model_siap=detector is not None,
        model_path=str(MODEL_PATH),
        pesan=model_error,
        ffmpeg=bool(cari_ffmpeg()),
        confidence_threshold=CONFIDENCE_THRESHOLD,
        image_size=IMAGE_SIZE,
    ), (200 if detector is not None else 503)


# =========================================================
# KLASIFIKASI GAMBAR & VIDEO (unggah / foto kamera)
# =========================================================
@app.route("/klasifikasi", methods=["GET", "POST"])
def klasifikasi():
    """Menangani klasifikasi gambar atau video."""
    if request.method == "GET":
        return render_template("klasifikasi.html", hasil=None)

    file = request.files.get("gambar")
    if file is None or not file.filename:
        flash("Pilih gambar atau video terlebih dahulu.")
        return redirect(url_for("klasifikasi"))

    if not model_siap():
        return redirect(url_for("klasifikasi"))

    if allowed_video(file.filename):
        return klasifikasi_video(file)

    if not allowed_image(file.filename):
        flash("Format file tidak didukung. Gunakan JPG, PNG, MP4, AVI, MOV, atau MKV.")
        return redirect(url_for("klasifikasi"))

    # Gambar dibaca langsung ke memori (tanpa file sementara).
    data = file.stream.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        flash(f"Ukuran gambar terlalu besar. Maksimal {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
        return redirect(url_for("klasifikasi"))

    record_id = f"{buat_timestamp()}_{Path(secure_filename(file.filename) or 'gambar').stem}"
    result_filename = f"hasil_{record_id}.jpg"
    result_path = RESULT_FOLDER / result_filename

    try:
        citra = CitraKakao(id=record_id)
        citra.loadFromBytes(data)
        IMAGE_PROCESSOR.preprocessing(citra)
        detections, raw_result = detector.detect(citra.imageFile)
        detections = detector.filterDetection(detections, CLASS_ORDER)
        if not cv2.imwrite(str(result_path), raw_result.plot()):
            raise RuntimeError("Gagal menyimpan gambar hasil.")
    except ValueError as error:
        flash(str(error))
        return redirect(url_for("klasifikasi"))
    except Exception:
        logger.exception("Gagal memproses gambar.")
        hapus_file_aman(RESULT_FOLDER, result_filename)
        flash("Gambar tidak dapat diproses. Periksa format gambar dan log aplikasi.")
        return redirect(url_for("klasifikasi"))

    counts = {c: 0 for c in CLASS_ORDER}
    deteksi_list = []
    for detection in detections:
        class_name = detection.getClass()
        if class_name not in counts:
            continue
        counts[class_name] += 1
        deteksi_list.append(
            {
                "nama": CLASS_LABEL[class_name],
                "confidence": round(detection.getConfidence() * 100, 1),
                "warna": CLASS_COLORS[class_name],
            }
        )
    deteksi_list.sort(key=lambda item: item["confidence"], reverse=True)

    hasil, record = susun_hasil(
        "gambar", result_filename, counts, deteksi_list, detections, {}
    )
    record["id"] = record_id
    RiwayatDeteksi(RIWAYAT_FILE).simpan(record)
    return render_template("klasifikasi.html", hasil=hasil)


def klasifikasi_video(file):
    """Memproses video unggahan: YOLOv8 per frame, tanpa tracking."""
    if not VIDEO_SLOT.acquire(blocking=False):
        flash("Server sedang memproses video lain. Coba lagi beberapa saat.")
        return redirect(url_for("klasifikasi"))

    extension = file.filename.rsplit(".", 1)[1].lower()
    nama_video = secure_filename(file.filename.rsplit(".", 1)[0]) or "video"
    timestamp = buat_timestamp()
    upload_name = f"{timestamp}_{nama_video}.{extension}"
    upload_path = UPLOAD_FOLDER / upload_name
    record_id = f"{timestamp}_{nama_video}"
    result_filename = f"hasil_{record_id}.mp4"
    result_path = RESULT_FOLDER / result_filename

    try:
        file.save(upload_path)
        if upload_path.stat().st_size > MAX_VIDEO_BYTES:
            flash(f"Ukuran video terlalu besar. Maksimal {MAX_VIDEO_BYTES // (1024 * 1024)} MB.")
            return redirect(url_for("klasifikasi"))
        try:
            hasil_kelas, info = video_processor.proses(upload_path, result_path)
        except VideoTidakValid as error:
            hapus_file_aman(RESULT_FOLDER, result_filename)
            flash(str(error))
            return redirect(url_for("klasifikasi"))
        except Exception:
            logger.exception("Gagal memproses video.")
            hapus_file_aman(RESULT_FOLDER, result_filename)
            flash("Video tidak dapat diproses. Pastikan file valid dan tidak rusak.")
            return redirect(url_for("klasifikasi"))
    finally:
        # Video asli tidak diperlukan lagi setelah diproses.
        hapus_file_aman(UPLOAD_FOLDER, upload_name)
        VIDEO_SLOT.release()

    # Jumlah = maksimum objek per kelas dalam satu frame (bukan objek unik).
    counts = {c: 0 for c in CLASS_ORDER}
    deteksi_list = []
    detections = []
    for item in hasil_kelas:
        class_name = item.className
        if class_name not in counts:
            continue
        counts[class_name] = item.maksPerFrame
        detections.append(item.detection)
        deteksi_list.append(
            {
                "nama": CLASS_LABEL[class_name],
                "confidence": round(item.detection.getConfidence() * 100, 1),
                "warna": CLASS_COLORS[class_name],
                "keterangan": (
                    f"maks. {item.maksPerFrame} objek dalam satu frame; "
                    f"muncul di {item.frameTerdeteksi} dari "
                    f"{info['frame_diproses']} frame diproses"
                ),
            }
        )
    deteksi_list.sort(key=lambda item: item["confidence"], reverse=True)

    hasil, record = susun_hasil(
        "video", result_filename, counts, deteksi_list, detections,
        {"info_video": info},
    )
    record["id"] = record_id
    record["info_video"] = info
    RiwayatDeteksi(RIWAYAT_FILE).simpan(record)

    if not info["h264"]:
        flash("Video hasil tidak dikonversi ke H.264 karena ffmpeg tidak ditemukan.")
    return render_template("klasifikasi.html", hasil=hasil)


# =========================================================
# KAMERA REALTIME (frame dari browser -> YOLOv8 di server)
# =========================================================
@app.route("/kamera", methods=["GET"])
def kamera():
    """Halaman kamera: realtime + ambil foto."""
    return render_template(
        "kamera.html",
        config={
            "frameUrl": url_for("api_deteksi_frame"),
            "sendMaxSide": REALTIME_SEND_MAX_SIDE,
            "jpegQuality": REALTIME_JPEG_QUALITY,
            "photoMaxSide": PHOTO_CAPTURE_MAX_SIDE,
            "photoQuality": PHOTO_JPEG_QUALITY,
            "defaultFps": REALTIME_DEFAULT_FPS,
        },
        fps_options=REALTIME_FPS_OPTIONS,
        default_fps=REALTIME_DEFAULT_FPS,
        kelas=[
            {"nama": CLASS_LABEL[c], "warna": CLASS_COLORS[c]} for c in CLASS_ORDER
        ],
        confidence_threshold=CONFIDENCE_THRESHOLD,
        model_error=None if detector is not None else model_error,
    )


@app.route("/api/deteksi-frame", methods=["POST"])
def api_deteksi_frame():
    """Menerima satu frame JPEG dan mengembalikan hasil deteksi YOLOv8 (JSON).

    Tidak ada tracking dan tidak ada ID objek. Frame tidak disimpan ke disk
    dan tidak dicatat ke riwayat.
    """
    if detector is None:
        return jsonify(ok=False, pesan=model_error or "Model belum tersedia."), 503

    if request.content_length and request.content_length > MAX_FRAME_BYTES:
        return jsonify(ok=False, pesan="Ukuran frame terlalu besar."), 413
    data = request.get_data(cache=False)
    if not data:
        return jsonify(ok=False, pesan="Frame kosong."), 400
    if len(data) > MAX_FRAME_BYTES:
        return jsonify(ok=False, pesan="Ukuran frame terlalu besar."), 413

    try:
        frame = CitraKakao.decodeBytes(data)
    except ValueError as error:
        return jsonify(ok=False, pesan=str(error)), 400

    mulai = time.perf_counter()
    try:
        detections = detector.filterDetection(detector.detectFrame(frame), CLASS_ORDER)
    except Exception:
        logger.exception("Gagal memproses frame.")
        return jsonify(ok=False, pesan="Gagal memproses frame."), 500
    durasi_ms = round((time.perf_counter() - mulai) * 1000, 1)

    tinggi, lebar = frame.shape[:2]
    counts = {c: 0 for c in CLASS_ORDER}
    items = []
    for det in detections:
        nama = det.getClass()
        if nama not in counts:
            continue
        counts[nama] += 1
        x1, y1, x2, y2 = det.boundingBox.getCoordinates()
        items.append(
            {
                "kelas": nama,
                "label": CLASS_LABEL[nama],
                "confidence": round(det.getConfidence() * 100, 1),
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                "warna": CLASS_COLORS[nama],
            }
        )

    response = jsonify(
        ok=True,
        lebar=lebar,
        tinggi=tinggi,
        durasi_ms=durasi_ms,
        deteksi=items,
        ringkasan=[
            {"label": CLASS_LABEL[c], "warna": CLASS_COLORS[c], "jumlah": counts[c]}
            for c in CLASS_ORDER
        ],
    )
    response.headers["Cache-Control"] = "no-store"
    return response


# =========================================================
# RIWAYAT
# =========================================================
@app.route("/riwayat", methods=["GET"])
def riwayat():
    """Menampilkan riwayat deteksi."""
    data = list(reversed(RiwayatDeteksi(RIWAYAT_FILE).ambilSemua()))
    return render_template("riwayat.html", riwayat=data)


@app.route("/riwayat/hapus/<record_id>", methods=["POST"])
def hapus_riwayat(record_id):
    """Menghapus riwayat dan file hasil terkait (hanya milik aplikasi)."""
    store = RiwayatDeteksi(RIWAYAT_FILE)
    record = next((r for r in store.ambilSemua() if r.get("id") == record_id), None)
    if record is None:
        flash("Data riwayat tidak ditemukan.")
        return redirect(url_for("riwayat"))

    if record.get("gambar_hasil"):
        hapus_file_aman(RESULT_FOLDER, record["gambar_hasil"])
    # Riwayat lama menyimpan file unggahan dengan nama = id.
    hapus_file_aman(UPLOAD_FOLDER, record_id)

    store.hapus(record_id)
    flash("Riwayat deteksi berhasil dihapus.")
    return redirect(url_for("riwayat"))


# =========================================================
# INFO
# =========================================================
@app.route("/info", methods=["GET"])
def info():
    """Menampilkan informasi kelas."""
    return render_template("info.html", kartu=INFO_KELAS)


# =========================================================
# MAIN (pengembangan lokal)
# =========================================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        use_reloader=False,
        threaded=True,
    )
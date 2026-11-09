"""
app.py
Controller utama aplikasi deteksi hama dan penyakit kakao.
"""
import os
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, flash, redirect, render_template, request, url_for
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
    MAX_IMAGE_BYTES,
    MAX_VIDEO_BYTES,
    SARAN_SUMBER,
    VIDEO_FRAME_STRIDE,
    VIDEO_MAX_DURATION,
    VIDEO_MAX_SIDE,
    VIDEO_MIN_HITS,
)
from domain import (
    CitraKakao,
    HasilDeteksi,
    ImageProcessor,
    RiwayatDeteksi,
    VideoProcessor,
    VideoTidakValid,
    YOLOv8Detector,
)
# Path
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
RESULT_FOLDER = BASE_DIR / "static" / "results"
MODEL_PATH = BASE_DIR / "models" / "best.pt"
RIWAYAT_FILE = BASE_DIR / "static" / "riwayat.json"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
RESULT_FOLDER.mkdir(parents=True, exist_ok=True)
# Flask
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "skripsi-kakao-development-key")
app.config["MAX_CONTENT_LENGTH"] = MAX_VIDEO_BYTES + 1024 * 1024
# Model
detector = YOLOv8Detector(
    modelPath=str(MODEL_PATH),
    confidenceThreshold=CONFIDENCE_THRESHOLD,
    imageSize=IMAGE_SIZE,
)
IMAGE_PROCESSOR = ImageProcessor(id="default", targetSize=(IMAGE_SIZE, IMAGE_SIZE))
video_processor = VideoProcessor(
    detector=detector,
    colors=CLASS_COLORS,
    labels=CLASS_LABEL,
    frameStride=VIDEO_FRAME_STRIDE,
    maxSide=VIDEO_MAX_SIDE,
    minHits=VIDEO_MIN_HITS,
    maxDurationSec=VIDEO_MAX_DURATION,
)
VIDEO_LOCK = threading.Lock()
# Utilitas
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
    kelas_terdeteksi = [
        class_name for class_name in CLASS_ORDER if counts[class_name] > 0
    ]
    saran_list = [
        {
            "nama": CLASS_LABEL[class_name],
            "warna": CLASS_COLORS[class_name],
            "poin": CLASS_SARAN.get(class_name, []),
        }
        for class_name in kelas_terdeteksi
    ]
    return ringkasan, kelas_terdeteksi, saran_list
def format_detik(detik: float) -> str:
    """Mengubah detik ke format menit:detik."""
    detik = int(detik)
    return f"{detik // 60}:{detik % 60:02d}"
def buat_timestamp() -> str:
    """Membuat ID berdasarkan waktu."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
def hapus_file(*paths: Path) -> None:
    """Menghapus file jika tersedia."""
    for path in paths:
        if path is not None and path.exists():
            path.unlink()
# Error handler
@app.errorhandler(413)
def file_terlalu_besar(_error):
    flash("Ukuran file terlalu besar. Batas gambar 16 MB dan video 200 MB.")
    return redirect(url_for("klasifikasi"))
# Home
@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")
# Klasifikasi gambar dan video
@app.route("/klasifikasi", methods=["GET", "POST"])
def klasifikasi():
    """Menangani klasifikasi gambar atau video."""
    if request.method == "GET":
        return render_template("klasifikasi.html", hasil=None)
    file = request.files.get("gambar")
    if file is None or not file.filename:
        flash("Pilih gambar atau video terlebih dahulu.")
        return redirect(url_for("klasifikasi"))
    if allowed_video(file.filename):
        return klasifikasi_video(file)
    if not allowed_image(file.filename):
        flash("Format file tidak didukung. Gunakan JPG, PNG, MP4, AVI, MOV, atau MKV.")
        return redirect(url_for("klasifikasi"))
    timestamp = buat_timestamp()
    nama_asli = secure_filename(file.filename)
    filename = f"{timestamp}_{nama_asli}"
    upload_path = UPLOAD_FOLDER / filename
    file.save(upload_path)
    if upload_path.stat().st_size > MAX_IMAGE_BYTES:
        hapus_file(upload_path)
        flash("Ukuran gambar terlalu besar. Maksimal 16 MB.")
        return redirect(url_for("klasifikasi"))
    try:
        citra = CitraKakao(id=filename, filePath=str(upload_path))
        IMAGE_PROCESSOR.preprocessing(citra)
        detections, raw_result = detector.detect(str(upload_path))
        detections = detector.filterDetection(detections, CLASS_ORDER)
    except Exception:
        app.logger.exception("Gagal memproses gambar.")
        hapus_file(upload_path)
        flash("Gambar tidak dapat diproses. Pastikan file valid dan tidak rusak.")
        return redirect(url_for("klasifikasi"))
    result_filename = f"hasil_{filename}"
    result_path = RESULT_FOLDER / result_filename
    raw_result.save(filename=str(result_path))
    counts = {class_name: 0 for class_name in CLASS_ORDER}
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
    ringkasan, kelas_terdeteksi, saran_list = susun_ringkasan_dan_saran(counts)
    hasil_label = (
        ", ".join(CLASS_LABEL[class_name] for class_name in kelas_terdeteksi)
        or "Tidak terdeteksi"
    )
    confidence_tertinggi = max(
        (detection.getConfidence() for detection in detections),
        default=0.0,
    )
    hasil_deteksi = HasilDeteksi(
        gambarHasil=f"results/{result_filename}",
        hasil=hasil_label,
        confidence=confidence_tertinggi * 100,
        waktu=datetime.now(),
        detections=detections,
    )
    hasil = hasil_deteksi.tampilkanHasil()
    hasil.update(
        {
            "tipe": "gambar",
            "jumlah_total": len(detections),
            "deteksi_list": deteksi_list,
            "ringkasan": ringkasan,
            "kelas_terdeteksi": kelas_terdeteksi,
            "saran_list": saran_list,
            "saran_sumber": SARAN_SUMBER,
        }
    )
    RiwayatDeteksi(RIWAYAT_FILE).simpan(
        {
            "id": filename,
            "tipe": "gambar",
            "waktu": hasil["waktu"],
            "gambar_hasil": f"results/{result_filename}",
            "hasil": hasil_label,
            "confidence": round(confidence_tertinggi * 100, 1),
            "jumlah_total": len(detections),
            "deteksi_list": deteksi_list,
        }
    )
    return render_template("klasifikasi.html", hasil=hasil)
def klasifikasi_video(file):
    """Memproses video dengan YOLOv8 dan ByteTrack."""
    extension = file.filename.rsplit(".", 1)[1].lower()
    nama_video = secure_filename(file.filename.rsplit(".", 1)[0]) or "video"
    timestamp = buat_timestamp()
    filename = f"{timestamp}_{nama_video}.{extension}"
    upload_path = UPLOAD_FOLDER / filename
    file.save(upload_path)
    if upload_path.stat().st_size > MAX_VIDEO_BYTES:
        hapus_file(upload_path)
        flash("Ukuran video terlalu besar. Maksimal 200 MB.")
        return redirect(url_for("klasifikasi"))
    result_filename = f"hasil_{timestamp}_{nama_video}.mp4"
    result_path = RESULT_FOLDER / result_filename
    try:
        with VIDEO_LOCK:
            objek_list, info = video_processor.proses(upload_path, result_path)
    except VideoTidakValid as error:
        hapus_file(upload_path, result_path)
        flash(str(error))
        return redirect(url_for("klasifikasi"))
    except Exception:
        app.logger.exception("Gagal memproses video.")
        hapus_file(upload_path, result_path)
        flash("Video tidak dapat diproses. Pastikan file valid dan tidak rusak.")
        return redirect(url_for("klasifikasi"))
    counts = {class_name: 0 for class_name in CLASS_ORDER}
    deteksi_list = []
    detections = []
    for objek in objek_list:
        class_name = objek.detection.getClass()
        if class_name not in counts:
            continue
        counts[class_name] += 1
        detections.append(objek.detection)
        deteksi_list.append(
            {
                "nama": f"{CLASS_LABEL[class_name]} #{objek.trackId}",
                # Confidence = confidence YOLO terbaik untuk kelas final.
                "confidence": round(objek.detection.getConfidence() * 100, 1),
                # Vote share = dominasi kelas hasil weighted voting.
                "vote_share": round(objek.voteShare * 100, 1),
                "warna": CLASS_COLORS[class_name],
                "keterangan": (
                    f"muncul {format_detik(objek.detikMuncul)}"
                    f"–{format_detik(objek.detikHilang)}"
                ),
            }
        )
    deteksi_list.sort(key=lambda item: item["confidence"], reverse=True)
    ringkasan, kelas_terdeteksi, saran_list = susun_ringkasan_dan_saran(counts)
    hasil_label = (
        ", ".join(CLASS_LABEL[class_name] for class_name in kelas_terdeteksi)
        or "Tidak terdeteksi"
    )
    confidence_tertinggi = max(
        (detection.getConfidence() for detection in detections),
        default=0.0,
    )
    hasil_deteksi = HasilDeteksi(
        gambarHasil=f"results/{result_filename}",
        hasil=hasil_label,
        confidence=confidence_tertinggi * 100,
        waktu=datetime.now(),
        detections=detections,
    )
    hasil = hasil_deteksi.tampilkanHasil()
    hasil.update(
        {
            "tipe": "video",
            "info_video": info,
            "jumlah_total": len(detections),
            "deteksi_list": deteksi_list,
            "ringkasan": ringkasan,
            "kelas_terdeteksi": kelas_terdeteksi,
            "saran_list": saran_list,
            "saran_sumber": SARAN_SUMBER,
        }
    )
    RiwayatDeteksi(RIWAYAT_FILE).simpan(
        {
            "id": filename,
            "tipe": "video",
            "waktu": hasil["waktu"],
            "gambar_hasil": f"results/{result_filename}",
            "hasil": hasil_label,
            "confidence": round(confidence_tertinggi * 100, 1),
            "jumlah_total": len(detections),
            "deteksi_list": deteksi_list,
            "info_video": info,
        }
    )
    if not info["h264"]:
        flash("Video hasil tidak dikonversi ke H.264 karena ffmpeg tidak ditemukan.")
    return render_template("klasifikasi.html", hasil=hasil)
# Riwayat
@app.route("/riwayat", methods=["GET"])
def riwayat():
    """Menampilkan riwayat deteksi."""
    riwayat_store = RiwayatDeteksi(RIWAYAT_FILE)
    data = list(reversed(riwayat_store.ambilSemua()))
    return render_template("riwayat.html", riwayat=data)
@app.route("/riwayat/hapus/<record_id>", methods=["POST"])
def hapus_riwayat(record_id):
    """Menghapus riwayat dan file terkait."""
    riwayat_store = RiwayatDeteksi(RIWAYAT_FILE)
    records = riwayat_store.ambilSemua()
    record = next((item for item in records if item.get("id") == record_id), None)
    nama_hasil = (
        Path(record["gambar_hasil"]).name
        if record and record.get("gambar_hasil")
        else f"hasil_{record_id}"
    )
    upload_path = UPLOAD_FOLDER / record_id
    result_path = RESULT_FOLDER / nama_hasil
    hapus_file(upload_path, result_path)
    if riwayat_store.hapus(record_id):
        flash("Riwayat deteksi berhasil dihapus.")
    else:
        flash("Data riwayat tidak ditemukan.")
    return redirect(url_for("riwayat"))
# Info
@app.route("/info", methods=["GET"])
def info():
    """Menampilkan informasi kelas."""
    return render_template("info.html", kartu=INFO_KELAS)
# Main
if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
    
"""
domain.py
Kelas domain untuk deteksi gambar dan video kakao."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO


# =========================================================
# UTILITAS
# =========================================================
def normalize_class_name(name: str) -> str:
    """Menyeragamkan nama kelas."""
    return str(name).strip().lower()


def cari_ffmpeg() -> Optional[str]:
    """Mencari executable ffmpeg (imageio-ffmpeg atau PATH sistem)."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


# =========================================================
# BOUNDING BOX
# =========================================================
@dataclass
class BoundingBox:
    """Koordinat bounding box."""

    x1: float
    y1: float
    x2: float
    y2: float

    def getCoordinates(self) -> tuple:
        return self.x1, self.y1, self.x2, self.y2


# =========================================================
# DETECTION
# =========================================================
@dataclass
class Detection:
    """Satu objek hasil deteksi."""

    boundingBox: BoundingBox
    className: str
    confidence: float

    def getClass(self) -> str:
        return self.className

    def getConfidence(self) -> float:
        return self.confidence


# =========================================================
# CITRA KAKAO
# =========================================================
class CitraKakao:
    """Representasi citra kakao."""

    def __init__(self, id: str, filePath: str = ""):
        self.id = id
        self.filePath = filePath
        self.imageFile: Optional[np.ndarray] = None

    @staticmethod
    def decodeBytes(data: bytes) -> np.ndarray:
        """Mendekode bytes gambar (JPG/PNG) menjadi array BGR dan memvalidasinya."""
        if not data:
            raise ValueError("File gambar kosong.")
        file_bytes = np.frombuffer(data, dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("File bukan gambar valid atau format tidak didukung.")
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Citra harus memiliki 3 kanal warna.")
        height, width = image.shape[:2]
        if height <= 0 or width <= 0:
            raise ValueError("Ukuran citra tidak valid.")
        return image

    def loadFromBytes(self, data: bytes) -> np.ndarray:
        """Membaca citra dari memori (tanpa file sementara)."""
        self.imageFile = self.decodeBytes(data)
        return self.imageFile

    def loadImage(self) -> np.ndarray:
        """Membaca dan memvalidasi citra dari file."""
        try:
            data = np.fromfile(self.filePath, dtype=np.uint8).tobytes()
        except OSError as e:
            raise ValueError(f"Gagal membaca file gambar: {e}") from e
        self.imageFile = self.decodeBytes(data)
        return self.imageFile

    def resize(self, targetSize: tuple) -> np.ndarray:
        """Mengubah ukuran citra."""
        if self.imageFile is None:
            self.loadImage()
        self.imageFile = cv2.resize(self.imageFile, targetSize)
        return self.imageFile


# =========================================================
# IMAGE PROCESSOR
# =========================================================
class ImageProcessor:
    """Memvalidasi citra sebelum deteksi.

    Resize (letterbox) dan normalisasi 0-1 dilakukan otomatis oleh YOLOv8
    pada saat inferensi menggunakan imgsz yang sama dengan saat pelatihan.
    """

    def __init__(self, id: str, targetSize: tuple = (640, 640)):
        self.id = id
        self.targetSize = targetSize

    def preprocessing(self, citra: CitraKakao) -> np.ndarray:
        """Memastikan citra sudah terbaca dan valid."""
        if citra.imageFile is not None:
            return citra.imageFile
        return citra.loadImage()

    def normalize(self, image: np.ndarray) -> np.ndarray:
        """Normalisasi nilai piksel ke 0-1."""
        return image.astype(np.float32) / 255.0


# =========================================================
# YOLOV8 DETECTOR
# =========================================================
class YOLOv8Detector:
    """Menjalankan deteksi menggunakan YOLOv8.

    Inferensi dilindungi lock karena satu instance model dipakai bersama oleh
    beberapa thread Flask (gambar, video, dan kamera realtime).
    """

    def __init__(
        self,
        modelPath: str,
        confidenceThreshold: float = 0.5,
        imageSize: int = 640,
    ):
        self.modelPath = modelPath
        self.confidenceThreshold = confidenceThreshold
        self.imageSize = imageSize
        self._model = YOLO(str(modelPath))
        self._lock = threading.Lock()

    @property
    def class_names(self) -> dict:
        """Nama kelas pada model."""
        return {
            class_id: normalize_class_name(name)
            for class_id, name in self._model.names.items()
        }

    def _predict(self, image_source):
        with self._lock:
            return self._model.predict(
                source=image_source,
                conf=self.confidenceThreshold,
                imgsz=self.imageSize,
                save=False,
                verbose=False,
            )[0]

    def _parse(self, raw_result) -> list:
        detections = []
        for box in raw_result.boxes:
            class_id = int(box.cls[0])
            class_name = normalize_class_name(self._model.names[class_id])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                Detection(
                    boundingBox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    className=class_name,
                    confidence=confidence,
                )
            )
        return detections

    def detect(self, image_source):
        """Mendeteksi objek pada satu citra (path, atau array BGR)."""
        raw_result = self._predict(image_source)
        return self._parse(raw_result), raw_result

    def detectFrame(self, frame: np.ndarray) -> list:
        """Mendeteksi objek pada satu frame (array BGR). Tanpa tracking."""
        return self._parse(self._predict(frame))

    def filterDetection(self, detections: list, allowed_classes=None) -> list:
        """Menyaring kelas yang digunakan sistem."""
        if not allowed_classes:
            return detections
        allowed = {normalize_class_name(name) for name in allowed_classes}
        return [
            detection
            for detection in detections
            if normalize_class_name(detection.className) in allowed
        ]


# =========================================================
# HASIL DETEKSI
# =========================================================
@dataclass
class HasilDeteksi:
    """Ringkasan hasil deteksi."""

    gambarHasil: str
    hasil: str
    confidence: float
    waktu: datetime
    detections: list = field(default_factory=list)

    def tampilkanHasil(self) -> dict:
        """Mengubah hasil ke format template."""
        return {
            "gambar_hasil": self.gambarHasil,
            "hasil": self.hasil,
            "confidence": round(self.confidence, 1),
            "waktu": self.waktu.strftime("%d %b %Y, %H:%M"),
            "deteksi": [
                {
                    "kelas": item.getClass(),
                    "confidence": round(item.getConfidence() * 100, 1),
                    "bbox": item.boundingBox.getCoordinates(),
                }
                for item in self.detections
            ],
        }


# =========================================================
# RIWAYAT DETEKSI
# =========================================================
class RiwayatDeteksi:
    """Menyimpan riwayat dalam file JSON.

    Lock hanya berlaku di dalam satu proses (cukup untuk `python app.py`).
    """

    _lock = threading.Lock()

    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def ambilSemua(self) -> list:
        """Mengambil seluruh riwayat."""
        if not self.filepath.exists():
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return []

    def _tulis(self, data: list) -> None:
        """Menulis atomik: tulis ke file sementara lalu ganti file asli."""
        temp = self.filepath.with_suffix(".json.tmp")
        with open(temp, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temp, self.filepath)

    def simpan(self, record: dict) -> None:
        """Menyimpan satu riwayat."""
        with self._lock:
            data = self.ambilSemua()
            data.append(record)
            self._tulis(data)

    def hapus(self, record_id: str) -> bool:
        """Menghapus riwayat berdasarkan ID."""
        with self._lock:
            data = self.ambilSemua()
            if not any(record.get("id") == record_id for record in data):
                return False
            self._tulis([r for r in data if r.get("id") != record_id])
            return True


# =========================================================
# VIDEO (unggahan) - inferensi YOLOv8 per frame, tanpa tracking
# =========================================================
class VideoTidakValid(ValueError):
    """Error untuk video yang tidak valid."""


@dataclass
class HasilKelasVideo:
    """Ringkasan satu kelas pada video.

    maksPerFrame      : jumlah objek kelas tersebut terbanyak dalam SATU frame.
    frameTerdeteksi   : banyak frame (yang diproses) yang memuat kelas tersebut.
    detection         : deteksi dengan confidence tertinggi untuk kelas tersebut.

    Tanpa tracking, objek yang sama di frame berbeda tidak dapat dikenali,
    sehingga jumlah objek unik tidak dapat dihitung. Karena itu jumlah yang
    dilaporkan adalah maksimum per frame, bukan total objek unik.
    """

    className: str
    maksPerFrame: int
    frameTerdeteksi: int
    detection: Detection


class VideoProcessor:
    """Memproses video unggahan frame demi frame menggunakan YOLOv8."""

    def __init__(
        self,
        detector: YOLOv8Detector,
        colors: dict,
        labels: dict,
        frameStride: int = 1,
        maxSide: int = 1280,
        maxDurationSec: float = 60.0,
    ):
        self.detector = detector
        self.colors = {normalize_class_name(n): c for n, c in colors.items()}
        self.labels = {normalize_class_name(n): lb for n, lb in labels.items()}
        self.frameStride = max(1, int(frameStride))
        self.maxSide = maxSide
        self.maxDurationSec = float(maxDurationSec)

    # -----------------------------------------------------
    # UTILITAS VIDEO
    # -----------------------------------------------------
    @staticmethod
    def _hexToBgr(hex_color: str) -> tuple:
        """Mengubah warna HEX ke BGR."""
        value = hex_color.lstrip("#")
        return (int(value[4:6], 16), int(value[2:4], 16), int(value[0:2], 16))

    def _resizeJikaPerlu(self, frame: np.ndarray) -> np.ndarray:
        """Membatasi ukuran frame video."""
        height, width = frame.shape[:2]
        sisi = max(height, width)
        if self.maxSide and sisi > self.maxSide:
            skala = self.maxSide / sisi
            frame = cv2.resize(
                frame,
                (int(width * skala), int(height * skala)),
                interpolation=cv2.INTER_AREA,
            )
        return frame

    def _gambar(self, frame: np.ndarray, kotak: list) -> None:
        """Menggambar bounding box, nama kelas, dan confidence."""
        sisi_kecil = min(frame.shape[:2])
        tebal = max(2, int(round(sisi_kecil / 300)))
        skala = max(0.5, sisi_kecil / 900)
        tebal_teks = max(1, tebal - 1)
        font = cv2.FONT_HERSHEY_SIMPLEX
        for x1, y1, x2, y2, teks, warna in kotak:
            cv2.rectangle(frame, (x1, y1), (x2, y2), warna, tebal)
            (tw, th), base = cv2.getTextSize(teks, font, skala, tebal_teks)
            text_y = max(y1, th + base + 2)
            cv2.rectangle(
                frame,
                (x1, text_y - th - base - 2),
                (x1 + tw + 4, text_y),
                warna,
                -1,
            )
            cv2.putText(
                frame,
                teks,
                (x1 + 2, text_y - base - 1),
                font,
                skala,
                (255, 255, 255),
                tebal_teks,
                cv2.LINE_AA,
            )

    def _deteksiFrame(self, frame: np.ndarray, stats: dict) -> list:
        """Menjalankan YOLOv8 pada satu frame dan memperbarui statistik kelas."""
        kotak = []
        per_frame = Counter()
        for det in self.detector.detectFrame(frame):
            nama = det.className
            if nama not in self.labels:
                continue
            per_frame[nama] += 1
            stat = stats.setdefault(
                nama, {"maks": 0, "frame": 0, "terbaik": None}
            )
            if stat["terbaik"] is None or det.confidence > stat["terbaik"].confidence:
                stat["terbaik"] = det
            x1, y1, x2, y2 = det.boundingBox.getCoordinates()
            teks = f"{self.labels[nama]} {det.confidence * 100:.1f}%"
            kotak.append(
                (int(x1), int(y1), int(x2), int(y2), teks,
                 self._hexToBgr(self.colors[nama]))
            )
        for nama, jumlah in per_frame.items():
            stats[nama]["frame"] += 1
            stats[nama]["maks"] = max(stats[nama]["maks"], jumlah)
        return kotak

    def _konversiH264(self, source: Path, destination: Path) -> bool:
        """Mengonversi video ke H.264 agar dapat diputar di browser."""
        ffmpeg = cari_ffmpeg()
        if not ffmpeg:
            return False
        command = [
            ffmpeg, "-y", "-loglevel", "error", "-i", str(source),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
            str(destination),
        ]
        try:
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
            )
        except OSError:
            return False
        return (
            result.returncode == 0
            and destination.exists()
            and destination.stat().st_size > 0
        )

    # -----------------------------------------------------
    # PROSES UTAMA
    # -----------------------------------------------------
    def proses(self, inputPath, outputPath) -> tuple:
        """Memproses video; mengembalikan (list[HasilKelasVideo], info)."""
        input_path = Path(inputPath)
        output_path = Path(outputPath)
        temp_path = output_path.with_name(output_path.stem + "_tmp.mp4")

        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise VideoTidakValid("Video tidak dapat dibuka. Pastikan file video valid.")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps != fps or fps < 1 or fps > 240:
            fps = 25.0

        total_frame = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frame > 0 and total_frame / fps > self.maxDurationSec:
            cap.release()
            raise VideoTidakValid(
                f"Durasi video melebihi {int(self.maxDurationSec)} detik."
            )

        stats: dict = {}
        kotak: list = []
        writer = None
        index_frame = 0
        frame_diproses = 0

        try:
            while True:
                berhasil, frame = cap.read()
                if not berhasil:
                    break
                if index_frame / fps > self.maxDurationSec:
                    raise VideoTidakValid(
                        f"Durasi video melebihi {int(self.maxDurationSec)} detik."
                    )
                frame = self._resizeJikaPerlu(frame)
                if writer is None:
                    height, width = frame.shape[:2]
                    writer = cv2.VideoWriter(
                        str(temp_path),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        fps,
                        (width, height),
                    )
                    if not writer.isOpened():
                        raise RuntimeError("VideoWriter gagal dibuka.")
                if index_frame % self.frameStride == 0:
                    kotak = self._deteksiFrame(frame, stats)
                    frame_diproses += 1
                self._gambar(frame, kotak)
                writer.write(frame)
                index_frame += 1
        except Exception:
            cap.release()
            if writer is not None:
                writer.release()
                writer = None
            if temp_path.exists():
                temp_path.unlink()
            raise
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        if index_frame == 0:
            if temp_path.exists():
                temp_path.unlink()
            raise VideoTidakValid("Video kosong atau tidak memiliki frame.")

        h264 = self._konversiH264(temp_path, output_path)
        if h264:
            if temp_path.exists():
                temp_path.unlink()
        else:
            if output_path.exists():
                output_path.unlink()
            temp_path.replace(output_path)

        hasil = [
            HasilKelasVideo(
                className=nama,
                maksPerFrame=stat["maks"],
                frameTerdeteksi=stat["frame"],
                detection=stat["terbaik"],
            )
            for nama, stat in stats.items()
            if stat["terbaik"] is not None
        ]
        info = {
            "durasi": round(index_frame / fps, 1),
            "fps": round(fps, 1),
            "frame_total": index_frame,
            "frame_diproses": frame_diproses,
            "stride": self.frameStride,
            "h264": h264,
        }
        return hasil, info
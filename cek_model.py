from pathlib import Path
from ultralytics import YOLO

m = YOLO("models/best.pt")
print("Nama kelas model:", m.names)

# Ambil gambar upload terbaru secara otomatis
files = sorted(Path("static/uploads").glob("*.*"), key=lambda p: p.stat().st_mtime)
gambar = [f for f in files if f.suffix.lower() in {".jpg", ".jpeg", ".png"}]
if not gambar:
    raise SystemExit("Tidak ada gambar di static/uploads")

terbaru = gambar[-1]
print("Gambar yang dicek:", terbaru.name)

r = m.predict(str(terbaru), conf=0.05, imgsz=640, verbose=False)[0]
print("Jumlah deteksi (conf >= 0.05):", len(r.boxes))
for b in r.boxes:
    print(m.names[int(b.cls[0])], round(float(b.conf[0]), 3))
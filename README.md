# Deteksi Kakao — Web App (Flask)

Web untuk mengunggah foto buah kakao dan mendeteksi kondisinya
(Sehat, busuk buah, kepik pengisap, penggerek buah) menggunakan model
YOLOv8 hasil training, lengkap dengan popup saran pengendalian sesuai
hasil deteksi.

## Struktur folder

```
kakao_deteksi_web/
├── app.py                    # server Flask, inference, data saran pengendalian
├── requirements.txt
├── models/
│   └── best.pt                # <-- taruh model kamu di sini (belum disertakan)
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   ├── img/                    # taruh foto latar kamu sendiri di sini (opsional)
│   ├── uploads/                 # gambar asli yang diunggah user (auto dibuat)
│   └── results/                  # gambar hasil deteksi (auto dibuat)
└── templates/
    ├── base.html               # navbar (Home / Klasifikasi / Info)
    ├── home.html                # landing page
    ├── klasifikasi.html         # upload + hasil deteksi + popup saran pengendalian
    └── info.html                 # kartu penjelasan tiap kelas
```

## Halaman

- **Home** (`/`) — judul penelitian dan tombol menuju halaman deteksi.
- **Klasifikasi** (`/klasifikasi`) — form unggah gambar. Setelah submit,
  hasil deteksi (gambar dengan bounding box, ringkasan jumlah per kelas,
  dan tombol **Saran Pengendalian**) muncul di halaman yang sama.
- **Info** (`/info`) — kartu penjelasan ciri-ciri tiap kelas.

## Fitur saran pengendalian

Setelah deteksi, tombol **"Saran Pengendalian"** hanya muncul kalau ada
objek terdeteksi. Diklik akan membuka popup berisi daftar langkah
penanganan untuk tiap hama/penyakit yang ditemukan pada gambar tersebut.
Isi saran ada di `app.py` pada dictionary `CLASS_SARAN` — silakan
disesuaikan/dikonsultasikan lagi dengan pembimbing atau literatur
pertanian sebelum dipakai sebagai rujukan resmi di skripsi.

## Cara menjalankan

1. **Salin model hasil training** dari Colab/Drive ke `models/best.pt`.

2. **(Opsional) Ganti latar hero** — saat ini pakai gradient hijau polos
   (bukan foto, untuk menghindari isu hak cipta foto stok). Kalau mau
   pakai foto kakao sendiri, taruh di `static/img/hero.jpg` lalu tambahkan
   di `style.css` pada class `.hero`:
   ```css
   .hero {
     background-image: linear-gradient(rgba(20,40,20,0.55), rgba(20,40,20,0.75)),
                        url("../img/hero.jpg");
     background-size: cover;
     background-position: center;
   }
   ```

3. **Buat virtual environment** (opsional tapi disarankan):
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Jalankan server:**
   ```bash
   python app.py
   ```

6. Buka browser ke `http://127.0.0.1:5000`

## Catatan

- Batas ukuran upload: 16MB (`MAX_CONTENT_LENGTH` di `app.py`).
- Ambang confidence deteksi default `0.5` — ubah di `app.py` pada
  `model.predict(..., conf=0.5, ...)` kalau ingin lebih sensitif/ketat.
- Untuk deploy (bukan sekadar demo lokal), jangan pakai `app.run(debug=True)`.
  Gunakan WSGI server seperti `gunicorn`:
  ```bash
  gunicorn -w 2 -b 0.0.0.0:8000 app:app
  ```
- Nama kelas di model kamu harus persis sama dengan key di `CLASS_ORDER`,
  `CLASS_LABEL`, `CLASS_COLORS`, `CLASS_DESKRIPSI`, dan `CLASS_SARAN`
  (dalam `app.py`) — yaitu `"Sehat"`, `"busuk buah"`, `"kepik pengisap"`,
  `"penggerek buah"`, sesuai `data.yaml` dataset kamu.

## Input video

Halaman **Klasifikasi** menerima gambar (JPG/PNG, maks. 16 MB) maupun video
(MP4/AVI/MOV/MKV, maks. 200 MB, durasi maks. 60 detik).

- Video dianalisis frame demi frame dengan model yang sama (confidence 0.5),
  ditambah tracking ByteTrack sehingga **satu buah dihitung satu kali**
  ("Jumlah Objek Unik"), bukan sekali per frame.
- Deteksi dijalankan tiap 3 frame (`VIDEO_FRAME_STRIDE` di `app.py`); frame di
  antaranya memakai kotak terakhir sehingga durasi video hasil sama dengan aslinya.
- Objek yang hanya muncul sesaat (< `VIDEO_MIN_HITS` frame terproses) dianggap
  noise dan tidak dihitung. Kelas akhir tiap objek ditentukan lewat voting
  seluruh kemunculannya.
- Video hasil dikonversi ke H.264 lewat `imageio-ffmpeg` agar bisa diputar di
  browser. Tanpa ffmpeg, video tetap dibuat tetapi mungkin tidak bisa diputar.
- Riwayat menyimpan video hasil; menghapus riwayat ikut menghapus file video.
- Untuk deploy dengan gunicorn, naikkan timeout karena proses video memakan
  waktu: `gunicorn -w 1 --timeout 300 -b 0.0.0.0:8000 app:app`

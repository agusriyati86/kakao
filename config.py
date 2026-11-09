"""
config.py
Konfigurasi model dan data referensi kelas kakao.
"""
import os


def _env_int(name: str, default: int) -> int:
    """Membaca environment variable bertipe integer dengan nilai cadangan."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# =========================================================
# KONFIGURASI LINGKUNGAN
# =========================================================
# "production" mewajibkan SECRET_KEY dari environment variable.
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

# =========================================================
# KONFIGURASI MODEL (tidak diubah)
# =========================================================
IMAGE_SIZE = 640
CONFIDENCE_THRESHOLD = 0.50

# =========================================================
# KONFIGURASI FILE
# =========================================================
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "mkv"}
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_VIDEO_BYTES = _env_int("MAX_VIDEO_MB", 200) * 1024 * 1024

# =========================================================
# KONFIGURASI VIDEO UNGGAHAN
# =========================================================
# Batas durasi ini hanya melindungi server dari beban berlebih pada unggah
# video. Nilai awal tetap 60 detik (sama seperti kode sebelumnya) dan dapat
# diubah lewat environment variable setelah pengujian pada hosting yang dipakai.
VIDEO_MAX_DURATION = _env_int("VIDEO_MAX_DURATION", 60)
VIDEO_FRAME_STRIDE = 1
VIDEO_MAX_SIDE = 1280

# =========================================================
# KONFIGURASI KAMERA REALTIME (browser -> server)
# =========================================================
# Frame diperkecil di browser sebelum dikirim agar bandwidth dan CPU hemat.
# Sisi terpanjang disamakan dengan IMAGE_SIZE karena model memproses 640 px.
REALTIME_SEND_MAX_SIDE = IMAGE_SIZE
REALTIME_JPEG_QUALITY = 0.7
REALTIME_FPS_OPTIONS = [2, 5, 10]
REALTIME_DEFAULT_FPS = 5
MAX_FRAME_BYTES = 2 * 1024 * 1024
# Foto dari kamera (untuk disimpan ke riwayat) memakai resolusi lebih tinggi.
PHOTO_CAPTURE_MAX_SIDE = 1920
PHOTO_JPEG_QUALITY = 0.92

# =========================================================
# DATA KELAS
# =========================================================
CLASS_DATA = {
    "sehat": {
        "nama": "Buah Kakao Sehat",
        "label": "Buah Sehat",
        "kategori": "Normal",
        "nama_ilmiah": "Normal",
        "gambar": "sehat.png",
        "posisi": "center 40%",
        "warna": "#3F5C3E",
        "ciri": [
            "Buah tidak menunjukkan gejala serangan hama maupun penyakit.",
            "Permukaan kulit buah tidak menunjukkan bercak, lubang gerekan, atau bekas tusukan.",
            "Buah memiliki kondisi fisik yang normal tanpa menunjukkan gejala kerusakan.",
        ],
        "saran": [
            "Tidak diperlukan tindakan pengendalian khusus untuk buah ini.",
            "Pertahankan kesehatan tanaman dengan pemupukan berimbang dan penyiraman yang cukup.",
            "Lakukan pemangkasan rutin untuk menjaga sirkulasi udara dan cahaya matahari yang optimal.",
            "Tetap lakukan pemantauan berkala agar gejala serangan hama atau penyakit dapat dideteksi sejak dini.",
        ],
    },
    "busuk buah": {
        "nama": "Busuk Buah",
        "label": "Busuk Buah",
        "kategori": "Penyakit",
        "nama_ilmiah": "Phytophthora palmivora",
        "gambar": "busuk.jpeg",
        "posisi": "center 40%",
        "warna": "#7A2E2E",
        "ciri": [
            (
                "Buah yang terinfeksi menunjukkan gejala busuk basah "
                "berwarna cokelat kehitaman dengan batas yang tegas. "
                "Infeksi dapat dimulai dari ujung, pangkal, maupun bagian tengah buah."
            ),
            (
                "Bercak berwarna cokelat berkembang dengan cepat sehingga "
                "dalam beberapa hari seluruh permukaan buah dapat menjadi "
                "busuk, basah, dan berwarna cokelat kehitaman."
            ),
            (
                "Pada kondisi lembap, permukaan buah dapat ditumbuhi serbuk "
                "berwarna putih yang merupakan spora Phytophthora palmivora "
                "dan dapat bercampur dengan jamur sekunder."
            ),
        ],
        "saran": [
            (
                "Melakukan sanitasi dengan memetik seluruh buah yang busuk "
                "saat pemangkasan atau panen, serta mengumpulkan buah yang "
                "jatuh untuk kemudian dikubur dengan kedalaman minimal 30 cm."
            ),
            (
                "Melakukan pemangkasan tanaman kakao dan pohon pelindung "
                "untuk mengurangi kelembapan kebun."
            ),
            (
                "Menyemprotkan jamur Trichoderma spp. pada buah kakao sehat "
                "sebagai tindakan preventif dengan dosis 2 kg/ha biakan padat "
                "dan volume semprot 500 l/ha."
            ),
            ("Melakukan aplikasi MS untuk meningkatkan APH " "dan vigor tanaman."),
            (
                "Menanam varietas atau klon yang toleran, seperti DRC 16, "
                "atau klon berproduksi tinggi seperti ICCRI 03, ICCRI 04, "
                "BL 50, maupun klon unggul lokal."
            ),
        ],
    },
    "penggerek buah": {
        "nama": "Penggerek Buah",
        "label": "Penggerek Buah",
        "kategori": "Hama",
        "nama_ilmiah": "PBK / Conopomorpha cramerella",
        "gambar": "penggerek.jpg",
        "posisi": "center 40%",
        "warna": "#8C4A2F",
        "ciri": [
            (
                "Buah yang terserang menunjukkan gejala masak awal "
                "dengan warna yang tidak merata berupa belang kuning dan hijau."
            ),
            (
                "Pada permukaan kulit buah terdapat lubang gerekan kecil, "
                "sedangkan bekas gerekan larva dapat terlihat ketika buah dibelah."
            ),
            (
                "Larva yang masuk ke dalam buah kakao memakan bagian plasenta "
                "sehingga menyebabkan biji tidak terbentuk secara sempurna."
            ),
            (
                "Biji kakao berukuran kecil, tidak bernas, berwarna kehitaman, "
                "dan saling melekat satu dengan lainnya."
            ),
        ],
        "saran": [
            (
                "Melakukan pemangkasan pemeliharaan secara berkala 3–4 kali "
                "dalam setahun untuk mengurangi kelembapan dan meningkatkan "
                "masuknya cahaya matahari ke lahan pertanaman."
            ),
            (
                "Melakukan pemupukan berimbang N, P, dan K dengan dosis sesuai "
                "anjuran atau menggunakan pupuk organik yang ditaburkan di "
                "sekeliling tanaman sekitar 50 cm dari tanaman."
            ),
            (
                "Melakukan panen sering dengan interval 4–7 hari sekali yang "
                "diikuti dengan sanitasi. Buah yang dipanen dibawa ke tempat "
                "penampungan hasil, kemudian segera dibelah dan diambil bijinya."
            ),
            (
                "Melakukan sanitasi kebun dengan mengambil semua buah yang "
                "terserang PBK dari pohon, sisa buah yang jatuh atau tercecer, "
                "serta mengumpulkan serasah daun di bawah pohon."
            ),
            (
                "Melakukan penyarungan buah menggunakan kantong plastik pada "
                "buah muda berukuran 8–15 cm. Dasar kantong dibiarkan terbuka "
                "sebagai ventilasi untuk mengatur kelembapan buah."
            ),
            (
                "Memanfaatkan semut hitam sebagai musuh alami imago PBK. "
                "Sarang dapat dibuat dari lipatan daun kelapa atau daun kakao "
                "yang digantungkan pada cabang."
            ),
            (
                "Melakukan aplikasi MS APH dengan cara infus akar "
                "untuk meningkatkan vigor tanaman."
            ),
            (
                "Melakukan peremajaan atau rehabilitasi kebun yang sudah rusak "
                "dengan menggunakan klon kakao yang toleran terhadap PBK."
            ),
            (
                "Menggunakan insektisida sebagai alternatif terakhir pada "
                "kondisi eksplosi secara bijaksana dan sesuai dengan izin "
                "serta rekomendasi yang berlaku."
            ),
        ],
    },
    "kepik pengisap": {
        "nama": "Kepik Pengisap",
        "label": "Kepik Pengisap",
        "kategori": "Hama",
        "nama_ilmiah": "Helopeltis sp.",
        "gambar": "kepik.png",
        "posisi": "center 40%",
        "warna": "#C08A34",
        "ciri": [
            (
                "Pada permukaan buah terdapat bercak bekas tusukan "
                "berwarna cokelat kehitaman."
            ),
            (
                "Serangan pada buah muda berukuran sekitar 8 cm dapat "
                "menyebabkan buah menjadi kering dan mati."
            ),
            (
                "Buah yang masih dapat berkembang setelah terserang "
                "menunjukkan permukaan kulit yang retak dan berkerut."
            ),
            (
                "Serangan pada pucuk menyebabkan pucuk layu dan mati, "
                "sedangkan ranting menjadi kering dan meranggas."
            ),
        ],
        "saran": [
            (
                "Memanfaatkan semut hitam (Dolichoderus thoracicus). "
                "Populasinya dapat ditingkatkan dengan pemasangan sarang buatan "
                "dari daun kakao kering atau daun kelapa."
            ),
            (
                "Memanfaatkan APH Beauveria bassiana dengan dosis "
                "1–1,5 kg biakan padat/ha atau 50–100 g spora/ha "
                "dengan volume semprot 500 l/ha."
            ),
            (
                "Melakukan aplikasi MS dengan cara infus akar "
                "untuk meningkatkan vigor tanaman."
            ),
            (
                "Melakukan penyemprotan pestisida nabati berupa ekstrak "
                "daun mimba, tembakau, babadotan, sirsak, dan bahan "
                "nabati lainnya dengan konsentrasi 2,5–5%."
            ),
            (
                "Penyemprotan insektisida kimia digunakan sebagai pilihan "
                "terakhir apabila intensitas serangan Helopeltis sp. berat "
                "dan harus menggunakan produk yang terdaftar."
            ),
        ],
    },
}
# =========================================================
# DATA TURUNAN
# =========================================================
CLASS_ORDER = [
    "penggerek buah",
    "kepik pengisap",
    "busuk buah",
    "sehat",
]
CLASS_LABEL = {key: data["label"] for key, data in CLASS_DATA.items()}
CLASS_COLORS = {key: data["warna"] for key, data in CLASS_DATA.items()}
CLASS_SARAN = {key: data["saran"] for key, data in CLASS_DATA.items()}
INFO_KELAS = [
    {
        "key": key,
        "nama": data["nama"],
        "kategori": data["kategori"],
        "nama_ilmiah": data["nama_ilmiah"],
        "gambar": data["gambar"],
        "posisi": data["posisi"],
        "ciri": data["ciri"],
    }
    for key, data in CLASS_DATA.items()
]
# =========================================================
# SUMBER SARAN
# =========================================================
SARAN_SUMBER = (
    "Maryani, Y., & Daniati, C. (2019). "
    "Buku Saku Hama dan Penyakit Tanaman Kakao. "
    "Direktorat Perlindungan Perkebunan, "
    "Direktorat Jenderal Perkebunan, "
    "Kementerian Pertanian."
)
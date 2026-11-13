"""OtoFix - Core Engine (logika bisnis sesuai PRD). Murni Python, bisa diuji tanpa UI."""
from dataclasses import dataclass, field
from math import radians, sin, cos, asin, sqrt

MAX_JARAK_KM = 10
KATEGORI = {
    "ban_bocor": "Ban bocor", "aki_soak": "Aki soak", "bensin_habis": "Bensin habis",
    "mesin_overheat": "Mesin overheat / mati", "kelistrikan": "Kelistrikan",
    "rem_blong": "Rem bermasalah", "bodi_rusak": "Bodi / kecelakaan ringan",
    "rantai_putus": "Rantai / CVT putus", "lainnya": "Lainnya",
}


def rupiah(n):
    return "Rp" + f"{n:,.0f}".replace(",", ".")


NAMA_KATEGORI = {**KATEGORI, "derek": "Derek kendaraan"}  # untuk tampilan pesanan (derek bukan kategori kerusakan)
LAYANAN = {"panggilan": "Mekanik Panggilan", "derek": "Derek Kendaraan"}
BIAYA_DEREK = 200000  # derek hanya untuk mobil, selalu layanan tersendiri (tidak digabung dengan kategori kerusakan)
# Biaya jasa mekanik panggilan (motor, mobil). 'lainnya' sengaja TIDAK ada: harga disepakati lewat chat.
JASA = {
    "ban_bocor": (40000, 75000), "aki_soak": (60000, 100000), "bensin_habis": (25000, 25000),
    "mesin_overheat": (90000, 150000), "kelistrikan": (70000, 120000), "rem_blong": (80000, 150000),
    "bodi_rusak": (100000, 175000), "rantai_putus": (60000, 150000),
}


def hitung_layanan(jenis_kendaraan, kategori_kerusakan, jarak_km, jam_kejadian, layanan="panggilan"):
    """Blok keputusan: Jangkauan -> Layanan/Kerusakan -> Ongkos -> Tarif malam.
    layanan='derek' (khusus mobil) berdiri sendiri; kategori 'lainnya' tidak memiliki estimasi harga."""
    jenis_kendaraan = jenis_kendaraan.lower()
    if jenis_kendaraan not in ("motor", "mobil"):
        raise ValueError("jenis_kendaraan harus 'motor' atau 'mobil'")
    if layanan not in LAYANAN:
        raise ValueError("layanan harus 'panggilan' atau 'derek'")
    if layanan == "derek" and jenis_kendaraan == "motor":
        raise ValueError("Layanan derek hanya tersedia untuk mobil")
    if not 0 <= jam_kejadian <= 23:
        raise ValueError("jam_kejadian harus 0-23")
    motor = jenis_kendaraan == "motor"
    malam = jam_kejadian >= 22 or jam_kejadian < 5

    if jarak_km > MAX_JARAK_KM:                                   # Blok 1
        return {"status_layanan": "Di Luar Jangkauan", "terjangkau": False}

    if layanan == "derek":                                        # Blok 2
        biaya_jasa = BIAYA_DEREK
    elif kategori_kerusakan in JASA:
        biaya_jasa = JASA[kategori_kerusakan][0 if motor else 1]
    else:                                                         # 'lainnya' -> tanpa estimasi
        return {"status_layanan": "Terjangkau", "terjangkau": True, "layanan": layanan,
                "jenis_layanan": LAYANAN[layanan], "estimasi": False, "biaya_jasa": None, "ongkos_panggil": None,
                "tarif_malam": malam, "biaya_total": None}

    if jarak_km <= 3:                                             # Blok 3
        ongkos_panggil = 15000
    elif jarak_km <= 7:
        ongkos_panggil = 25000
    else:
        ongkos_panggil = 40000

    subtotal = biaya_jasa + ongkos_panggil                        # Blok 4
    biaya_total = subtotal * 1.25 if malam else float(subtotal)
    return {"status_layanan": "Terjangkau", "terjangkau": True, "layanan": layanan,
            "jenis_layanan": LAYANAN[layanan], "estimasi": True, "biaya_jasa": biaya_jasa,
            "ongkos_panggil": ongkos_panggil, "tarif_malam": malam, "biaya_total": biaya_total}


def biaya_efektif(hasil):
    """Angka biaya yang berlaku: harga akhir hasil kesepakatan (jika ada), atau estimasi; None = belum ditentukan."""
    return hasil.get("harga_akhir") or (hasil.get("biaya_total") if hasil.get("estimasi", True) else None)


def teks_biaya(hasil):
    n = biaya_efektif(hasil)
    return rupiah(n) if n else "Disepakati via chat"


def jarak_haversine(lat1, lon1, lat2, lon2):
    """Jarak GPS dua koordinat (km)."""
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


# ---- Diagnosa AI (lihat ai.py: LLM bila ada API key, kalau tidak analisis offline) ----
def diagnosa_ai(keluhan, kendaraan="motor"):
    """Kompatibilitas lama: (kategori, saran) memakai analisis offline."""
    from ai import analisis_offline
    r = analisis_offline(keluhan, kendaraan)
    return r["kategori"], r["saran"]


# ---- Penugasan cerdas ----
@dataclass
class Mekanik:
    nama: str
    lat: float
    lon: float


@dataclass
class Pesanan:
    nama_pengguna: str
    jenis_kendaraan: str
    kategori: str
    analisis_ai: str
    lat: float
    lon: float
    jam: int
    hasil: dict
    waktu: str
    antrean: list = field(default_factory=list)   # mekanik terdekat -> terjauh
    status: str = "Mencari mekanik"
    mekanik: str = ""

    @property
    def mekanik_saat_ini(self):
        return self.antrean[0] if self.antrean else None

    def terima(self):
        self.status, self.mekanik = "Mekanik menuju lokasi", self.antrean[0].nama

    def tolak(self):
        """Pesanan otomatis dilempar ke mekanik berikutnya dalam jangkauan."""
        self.antrean.pop(0)
        if not self.antrean:
            self.status = "Tidak ada mekanik tersedia"


def antrean_mekanik(daftar, lat, lon):
    hasil = [(jarak_haversine(lat, lon, m.lat, m.lon), m) for m in daftar]
    return [m for d, m in sorted(hasil, key=lambda x: x[0]) if d <= MAX_JARAK_KM]

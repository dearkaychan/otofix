"""OtoFix - penyimpanan akun & pesanan (SQLite). Dibagi oleh aplikasi Pengguna dan Mitra.
Di produksi, ganti modul ini dengan backend/API (FastAPI, Firebase, dsb.)."""
import sqlite3, hashlib, hmac, os, json, time
from datetime import datetime
from engine import jarak_haversine, MAX_JARAK_KM

# Di APK folder aplikasi read-only; Flet menyediakan folder tulis lewat FLET_APP_STORAGE_DATA.
_DIR = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("OTOFIX_DB") or os.path.join(_DIR, "otofix.db")
BASE_LAT, BASE_LON = -7.5666, 110.8167  # simulasi pusat kota Surakarta

AKTIF = ("Mencari mekanik", "Mekanik menuju lokasi")


def _c():
    # timeout: dua aplikasi (pengguna & mitra) menulis ke file yang sama
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _hash(pw, salt=None):
    salt = salt or os.urandom(16)
    return salt.hex() + ":" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000).hex()


def _cek(pw, simpan):
    return hmac.compare_digest(_hash(pw, bytes.fromhex(simpan.split(":")[0])), simpan)


def init():
    with _c() as c:
        c.execute("pragma journal_mode=wal")
        c.executescript("""
        create table if not exists akun(id integer primary key autoincrement, peran text, nama text,
            email text unique, telp text, pw text);
        create table if not exists pesanan(id integer primary key autoincrement, user_id int, data text,
            antrean text, status text, mekanik_id int, waktu text);
        create table if not exists chat(id integer primary key autoincrement, pesanan_id int, dari_id int,
            teks text, waktu text, dibaca int default 0);
        create table if not exists rating(id integer primary key autoincrement, pesanan_id int, dari_id int, untuk_id int,
            dari_peran text, bintang int, komentar text, waktu text, unique(pesanan_id, dari_id));""")
        kolom = {r["name"] for r in c.execute("pragma table_info(akun)")}
        for k, tipe in (("foto", "text"), ("lat", "real"), ("lon", "real"), ("aktif_pada", "real"), ("alamat", "text"),
                            ("kend_jenis", "text"), ("kend_merek", "text"), ("kend_model", "text"), ("kend_tahun", "int"), ("kend_plat", "text"),
                            ("live_lat", "real"), ("live_lon", "real"), ("live_pada", "real")):  # migrasi DB lama
            if k not in kolom:
                c.execute(f"alter table akun add column {k} {tipe}")
        kp = {r["name"] for r in c.execute("pragma table_info(pesanan)")}
        if "ditolak" not in kp:
            c.execute("alter table pesanan add column ditolak text default '[]'")
        if not c.execute("select 1 from akun where peran='mitra'").fetchone():
            for n in ("Pak Joko", "Mas Dimas", "Pak Eko"):  # mitra demo, sandi: mitra123
                c.execute("insert into akun(peran,nama,email,telp,pw) values('mitra',?,?,?,?)",
                          (n, n.split()[1].lower() + "@otofix.id", "0812000000", _hash("mitra123")))


def _koordinat_valid(lat, lon):
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def daftar(peran, nama, email, telp, pw, lat=None, lon=None, alamat=""):
    """Mitra WAJIB menyertakan lokasi bengkel (lat, lon); dipakai untuk aturan radius 10 km."""
    nama, email = nama.strip(), email.strip().lower()
    if peran == "mitra" and not _koordinat_valid(lat, lon): return False, "Pilih lokasi bengkel terlebih dahulu."
    if not nama: return False, "Nama wajib diisi."
    if "@" not in email or "." not in email.split("@")[-1]: return False, "Format email belum benar."
    if len(pw) < 6: return False, "Kata sandi minimal 6 karakter."
    try:
        with _c() as c:
            c.execute("insert into akun(peran,nama,email,telp,pw,lat,lon,alamat) values(?,?,?,?,?,?,?,?)",
                      (peran, nama, email, telp.strip(), _hash(pw), lat, lon, (alamat or "").strip() or None))
        return True, None
    except sqlite3.IntegrityError:
        return False, "Email sudah terdaftar. Silakan masuk."


def masuk(peran, email, pw):
    with _c() as c:
        r = c.execute("select * from akun where email=? and peran=?", (email.strip().lower(), peran)).fetchone()
    return dict(r) if r and _cek(pw, r["pw"]) else None


def akun(i):
    with _c() as c:
        r = c.execute("select * from akun where id=?", (i,)).fetchone()
    return dict(r) if r else None


def ubah_password(i, lama, baru):
    """Ganti kata sandi: WAJIB memasukkan kata sandi lama yang benar."""
    a = akun(i)
    if not a: return False, "Akun tidak ditemukan."
    if not lama or not _cek(lama, a["pw"]): return False, "Kata sandi lama salah."
    if len(baru or "") < 6: return False, "Kata sandi baru minimal 6 karakter."
    if baru == lama: return False, "Kata sandi baru harus berbeda dari yang lama."
    with _c() as c: c.execute("update akun set pw=? where id=?", (_hash(baru), i))
    return True, None


def simpan_kendaraan(i, jenis, merek, model, tahun=None, plat=""):
    """Kendaraan utama pengguna (dipakai otomatis saat memesan). Bisa diubah kapan saja."""
    merek, model = (merek or "").strip(), (model or "").strip()
    if jenis not in ("motor", "mobil"): return False, "Pilih jenis kendaraan: motor atau mobil."
    if not merek or not model: return False, "Pilih atau isi merek dan model kendaraan."
    try: tahun = int(tahun) if str(tahun or "").strip() else None
    except ValueError: return False, "Tahun harus berupa angka."
    if tahun is not None and not 1950 <= tahun <= datetime.now().year + 1: return False, "Tahun kendaraan tidak valid."
    with _c() as c:
        c.execute("update akun set kend_jenis=?, kend_merek=?, kend_model=?, kend_tahun=?, kend_plat=? where id=?",
                  (jenis, merek, model, tahun, (plat or "").strip().upper() or None, i))
    return True, None


def kendaraan(i):
    a = akun(i)
    if not a or not a.get("kend_jenis"): return None
    return dict(jenis=a["kend_jenis"], merek=a["kend_merek"], model=a["kend_model"], tahun=a["kend_tahun"], plat=a["kend_plat"])


def label_kendaraan(k, dengan_plat=False):
    if not k: return ""
    t = f"{k['merek']} {k['model']}" + (f" ({k['tahun']})" if k.get("tahun") else "")
    return t + (f" · {k['plat']}" if dengan_plat and k.get("plat") else "")


def ubah_profil(i, nama, telp):
    with _c() as c: c.execute("update akun set nama=?, telp=? where id=?", (nama.strip(), telp.strip(), i))


def foto_dari_file(path):
    """Baca gambar -> JPEG 256x256 (jika Pillow ada) -> base64 untuk disimpan di DB."""
    import base64, io
    with open(path, "rb") as f:
        raw = f.read()
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        buf = io.BytesIO()
        ImageOps.fit(im, (256, 256)).save(buf, "JPEG", quality=82)
        raw = buf.getvalue()
    except ImportError:
        if len(raw) > 1_500_000:
            raise ValueError("Foto terlalu besar (maksimal 1,5 MB).")
    except Exception:
        raise ValueError("File yang dipilih bukan gambar yang valid.")
    return base64.b64encode(raw).decode()


def ubah_foto(i, b64):
    with _c() as c: c.execute("update akun set foto=? where id=?", (b64, i))


def set_lokasi(i, lat, lon, alamat=None):
    """Simpan/ubah lokasi (bengkel untuk mitra). alamat=None -> alamat lama dipertahankan."""
    if not _koordinat_valid(lat, lon): raise ValueError("Koordinat tidak valid.")
    with _c() as c:
        c.execute("update akun set lat=?, lon=? where id=?", (lat, lon, i))
        if alamat is not None: c.execute("update akun set alamat=? where id=?", ((alamat or "").strip() or None, i))


def lokasi_diatur(i):
    a = akun(i)
    return bool(a) and a.get("lat") is not None and a.get("lon") is not None


ONLINE_DETIK = 20  # mitra dianggap online bila aplikasinya mengirim sinyal dalam 20 detik terakhir


def heartbeat(i):
    """Dipanggil berkala oleh aplikasi mitra yang sedang terbuka."""
    with _c() as c: c.execute("update akun set aktif_pada=? where id=?", (time.time(), i))


def offline(i):
    with _c() as c: c.execute("update akun set aktif_pada=null where id=?", (i,))


def id_online():
    with _c() as c:
        return {r["id"] for r in c.execute("select id from akun where peran='mitra' and aktif_pada > ?", (time.time() - ONLINE_DETIK,))}


def bengkel_dalam_radius(lat, lon):
    """Semua bengkel mitra dalam radius 10 km (online maupun offline), terdekat dulu."""
    return [m for m in mitra_terdekat(lat, lon) if m[0] <= MAX_JARAK_KM]


def antrean(lat, lon):
    """Bengkel yang TERSEDIA untuk pesanan: dalam radius 10 km DAN online (aplikasinya terbuka), terdekat dulu.
    Tidak ada cadangan ke bengkel offline atau di luar radius: bila kosong, pesanan tidak boleh dibuat/dialihkan."""
    on = id_online()
    return [m for m in bengkel_dalam_radius(lat, lon) if m[1] in on]


def pos_akun(i):
    """Lokasi terakhir akun (GPS asli bila pernah tercatat), kalau belum ada -> posisi simulasi."""
    a = akun(i)
    if a and a.get("lat") is not None and a.get("lon") is not None:
        return a["lat"], a["lon"]
    return pos_mitra(i)


def pos_mitra(i):
    """Posisi simulasi mitra: selalu di kisaran +-5 km dari pusat kota, siapa pun id-nya
    (versi lama memakai 0.012*id sehingga mitra baru terlempar di luar radius 10 km)."""
    return BASE_LAT + 0.012 * (((i - 1) % 7) - 3), BASE_LON


def mitra_terdekat(lat, lon):
    with _c() as c: rows = c.execute("select id,nama from akun where peran='mitra'").fetchall()
    return sorted((jarak_haversine(lat, lon, *pos_akun(r["id"])), r["id"], r["nama"]) for r in rows)


def _p(r):
    if r is None: return None
    d = json.loads(r["data"]); d.update(id=r["id"], user_id=r["user_id"], antrean=json.loads(r["antrean"]), ditolak=json.loads(r["ditolak"] or "[]"),
                                        status=r["status"], mekanik_id=r["mekanik_id"], waktu=r["waktu"]); return d


def buat_pesanan(user_id, data, antrean):
    st = "Mencari mekanik" if antrean else "Tidak ada bengkel terdekat"
    with _c() as c:
        return c.execute("insert into pesanan(user_id,data,antrean,status,waktu) values(?,?,?,?,?)",
                         (user_id, json.dumps(data), json.dumps(antrean), st, datetime.now().strftime("%d/%m %H:%M"))).lastrowid


def pesanan(i):
    with _c() as c: return _p(c.execute("select * from pesanan where id=?", (i,)).fetchone())


def pesanan_user(uid):
    with _c() as c: return [_p(r) for r in c.execute("select * from pesanan where user_id=? order by id desc", (uid,))]


def pesanan_aktif_user(uid):
    return next((p for p in pesanan_user(uid) if p["status"] in AKTIF), None)


def penawaran(p):
    """Mitra yang SAAT INI ditawari pesanan: mitra online terdekat (dalam radius) yang belum menolak.
    Dihitung ulang setiap kali, jadi bila mitra ganti akun / keluar / ada yang baru online,
    pesanan otomatis berpindah. None = belum ada mitra online yang memenuhi."""
    if p["status"] != "Mencari mekanik":
        return None
    on = id_online()
    for jarak, mid, _ in mitra_terdekat(p["lat"], p["lon"]):
        if jarak <= MAX_JARAK_KM and mid in on and mid not in p["ditolak"]:
            return mid
    return None


def radar(mid):  # pesanan yang sedang ditawarkan ke mekanik ini
    with _c() as c: rows = [_p(r) for r in c.execute("select * from pesanan where status='Mencari mekanik' order by id desc")]
    return [p for p in rows if penawaran(p) == mid]


def tugas(mid):
    with _c() as c: return [_p(r) for r in c.execute("select * from pesanan where mekanik_id=? and status='Mekanik menuju lokasi' order by id desc", (mid,))]


def riwayat_mitra(mid):
    with _c() as c: return [_p(r) for r in c.execute("select * from pesanan where mekanik_id=? and status='Selesai' order by id desc", (mid,))]


def ubah_status(pid, status, mekanik_id=None):
    """Terima pesanan hanya berhasil bila masih ditawarkan ke mekanik tsb (hindari balapan/ganda)."""
    with _c() as c:
        if status == "Mekanik menuju lokasi":
            cur = c.execute("update pesanan set status=?, mekanik_id=? where id=? and status='Mencari mekanik'",
                            (status, mekanik_id, pid))
            return cur.rowcount > 0
        cur = c.execute("update pesanan set status=? where id=? and status not in ('Selesai','Dibatalkan')", (status, pid))
        return cur.rowcount > 0


def batal(pid):
    """Pengguna membatalkan pesanan yang masih aktif."""
    with _c() as c:
        cur = c.execute("update pesanan set status='Dibatalkan' where id=? and status in ('Mencari mekanik','Mekanik menuju lokasi')", (pid,))
        return cur.rowcount > 0


def tolak(pid, mid):
    """Mitra menolak: pesanan diteruskan ke mitra online berikutnya. Bila semua mitra dalam radius sudah menolak -> habis."""
    p = pesanan(pid)
    if not p or p["status"] != "Mencari mekanik": return
    d = p["ditolak"] + ([mid] if mid not in p["ditolak"] else [])
    semua = [m[1] for m in mitra_terdekat(p["lat"], p["lon"]) if m[0] <= MAX_JARAK_KM]
    habis = all(x in d for x in semua)
    with _c() as c:
        c.execute("update pesanan set ditolak=?, status=? where id=?",
                  (json.dumps(d), "Ditolak" if habis else "Mencari mekanik", pid))


# ── Rating dua arah ────────────────────────────────────────────────────────────
# Pengguna menilai mekanik  (dari_peran='pengguna') -> hanya dilihat PENGGUNA yang pesanannya ditangani mekanik itu
#                                                    (dan mekanik yang bersangkutan).
# Mekanik menilai pengguna  (dari_peran='mitra')    -> hanya dilihat MEKANIK/aplikasi mitra yang mendapat pelanggan itu.
# Aplikasi pengguna tidak pernah memanggil rating_pelanggan(), sehingga pengguna tidak bisa melihat rating dirinya.

def beri_rating(pid, dari_id, bintang, komentar=""):
    p = pesanan(pid)
    if not p or p["status"] != "Selesai": return False, "Pesanan belum selesai."
    try: bintang = int(bintang)
    except (TypeError, ValueError): bintang = 0
    if not 1 <= bintang <= 5: return False, "Pilih 1 sampai 5 bintang."
    if dari_id == p["user_id"] and p["mekanik_id"]: untuk, peran = p["mekanik_id"], "pengguna"
    elif dari_id == p["mekanik_id"]: untuk, peran = p["user_id"], "mitra"
    else: return False, "Anda tidak terlibat dalam pesanan ini."
    try:
        with _c() as c:
            c.execute("insert into rating(pesanan_id,dari_id,untuk_id,dari_peran,bintang,komentar,waktu) values(?,?,?,?,?,?,?)",
                      (pid, dari_id, untuk, peran, bintang, (komentar or "").strip()[:300], datetime.now().strftime("%d/%m %H:%M")))
        return True, None
    except sqlite3.IntegrityError:
        return False, "Anda sudah memberi rating untuk pesanan ini."


def rating_oleh(pid, dari_id):
    """Rating yang sudah diberikan akun ini pada pesanan tsb (atau None)."""
    with _c() as c:
        r = c.execute("select bintang, komentar from rating where pesanan_id=? and dari_id=?", (pid, dari_id)).fetchone()
    return dict(r) if r else None


def _ringkasan(untuk_id, peran, limit=3):
    with _c() as c:
        rows = [dict(r) for r in c.execute(
            "select bintang, komentar, waktu from rating where untuk_id=? and dari_peran=? order by id desc", (untuk_id, peran))]
    n = len(rows)
    return dict(rata=round(sum(r["bintang"] for r in rows) / n, 1) if n else None, jumlah=n,
                ulasan=[r for r in rows if r["komentar"]][:limit])


def rating_mekanik(mid):
    """Rating mekanik dari para pengguna (boleh dilihat pengguna yang mendapat mekanik ini)."""
    return _ringkasan(mid, "pengguna")


def rating_pelanggan(uid):
    """Rating pelanggan dari para mekanik (HANYA untuk aplikasi mitra)."""
    return _ringkasan(uid, "mitra")


# ── Harga kesepakatan (untuk kategori 'Lainnya' tanpa estimasi) ────────────────
def set_harga_akhir(pid, nilai):
    try: nilai = int(nilai)
    except (TypeError, ValueError): return False
    if not 0 < nilai <= 100_000_000: return False
    with _c() as c:
        r = c.execute("select data from pesanan where id=?", (pid,)).fetchone()
        if not r: return False
        d = json.loads(r["data"]); d.setdefault("hasil", {})["harga_akhir"] = nilai
        c.execute("update pesanan set data=? where id=?", (json.dumps(d), pid))
    return True


def harga(p):
    """Angka harga yang berlaku untuk pesanan (kesepakatan/estimasi), None bila belum ditentukan."""
    from engine import biaya_efektif
    return biaya_efektif(p["hasil"])


# ── Chat pengguna <-> mekanik (hanya selama mekanik menuju lokasi; setelah itu hanya bisa dibaca) ──
def _peserta(p, i):
    return bool(p) and i in (p["user_id"], p["mekanik_id"])


def kirim_chat(pid, dari_id, teks):
    teks = (teks or "").strip()[:500]
    p = pesanan(pid)
    if not _peserta(p, dari_id): return False, "Anda tidak terlibat dalam pesanan ini."
    if not teks: return False, "Pesan kosong."
    if p["status"] != "Mekanik menuju lokasi": return False, "Chat hanya aktif saat mekanik menuju lokasi."
    with _c() as c:
        c.execute("insert into chat(pesanan_id,dari_id,teks,waktu) values(?,?,?,?)", (pid, dari_id, teks, datetime.now().strftime("%H:%M")))
    return True, None


def chat_pesanan(pid, untuk_id):
    if not _peserta(pesanan(pid), untuk_id): return []
    with _c() as c:
        return [dict(r) for r in c.execute("select id, dari_id, teks, waktu from chat where pesanan_id=? order by id", (pid,))]


def chat_belum_dibaca(pid, untuk_id):
    if not _peserta(pesanan(pid), untuk_id): return 0
    with _c() as c:
        return c.execute("select count(*) from chat where pesanan_id=? and dari_id!=? and dibaca=0", (pid, untuk_id)).fetchone()[0]


def chat_tandai_dibaca(pid, untuk_id):
    with _c() as c:
        c.execute("update chat set dibaca=1 where pesanan_id=? and dari_id!=?", (pid, untuk_id))


# ── Pelacakan langsung posisi mekanik ──────────────────────────────────────────
LIVE_BASI_DETIK = 60  # posisi lebih tua dari ini dianggap tidak aktif


def set_live(i, lat, lon):
    """Dipanggil aplikasi mitra tiap beberapa detik selama ada pesanan aktif."""
    with _c() as c: c.execute("update akun set live_lat=?, live_lon=?, live_pada=? where id=?", (lat, lon, time.time(), i))


def hapus_live(i):
    with _c() as c: c.execute("update akun set live_lat=null, live_lon=null, live_pada=null where id=?", (i,))


def lokasi_mekanik(pid, untuk_user_id):
    """Posisi terkini mekanik untuk pesanan ini. HANYA untuk pengguna pemilik pesanan dan hanya selagi
    mekanik menuju lokasi. -> dict(lat, lon, umur) atau None."""
    p = pesanan(pid)
    if not p or p["user_id"] != untuk_user_id or p["status"] != "Mekanik menuju lokasi" or not p["mekanik_id"]:
        return None
    a = akun(p["mekanik_id"])
    if not a or a.get("live_lat") is None or a.get("live_pada") is None:
        return None
    umur = time.time() - a["live_pada"]
    return dict(lat=a["live_lat"], lon=a["live_lon"], umur=umur) if umur <= LIVE_BASI_DETIK else None

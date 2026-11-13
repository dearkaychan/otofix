"""Smoke test tanpa GUI: menjalankan alur utama kedua aplikasi dengan Page tiruan.
Jalankan:  python test_smoke.py"""
import os, tempfile
_tmp = tempfile.mkdtemp()
os.environ["OTOFIX_DB"] = os.path.join(_tmp, "test.db")
os.environ["OTOFIX_OFFLINE"] = "1"          # tanpa GPS/internet saat tes
import flet as ft
import db, engine, lokasi, ui, peta, app_pengguna, app_mitra

app_pengguna.JEDA = 0
db.ONLINE_DETIK = 10 ** 6      # sinyal online tidak kedaluwarsa selama tes berjalan (db.offline() tetap berlaku)
ui.JEDA_SEGARKAN = 0
ft.FilePicker.pick_files = lambda self, **k: None   # dialog file tidak bisa dibuka tanpa GUI
BOLEH = {"cari_lokasi", "kerja", "proses_cari", "_cari_alamat", "_ambil_gps"}      # thread yang dijalankan sinkron di tes


class Store(dict):
    def set(self, k, v): self[k] = v
    def remove(self, k): self.pop(k, None)


class Win: width = height = 0


class FakePage:
    def __init__(self):
        self.controls, self.opened, self.overlay, self.client_storage, self.window = [], [], [], Store(), Win()
        self.navigation_bar, self.bgcolor, self.url = None, None, None
    def add(self, *c): self.controls += c
    def update(self, *a): pass
    def open(self, c): self.opened.append(c)
    def close(self, c): self.opened = [x for x in self.opened if x is not c]
    def launch_url(self, u): self.url = u
    def run_thread(self, fn):
        if getattr(fn, "__name__", "") in BOLEH: fn()


walk = ui.walk
def tombol(root, teks):
    for c in walk(root):
        if isinstance(c, (ft.FilledButton, ft.OutlinedButton, ft.TextButton, ft.CupertinoDialogAction)) and getattr(c, "text", None) == teks:
            return c
    raise AssertionError(f"tombol '{teks}' tidak ditemukan")
def screen(page): return page.controls[0].content.controls[0].content.content   # SafeArea -> Stack -> AnimatedSwitcher -> Container -> isi
def klik(c): c.on_click(None)
def ok(msg): print("✓", msg)
def tab(pg, i): pg.nav.klik(i)
def teks_semua(root): return [c.value for c in walk(root) if isinstance(c, ft.Text) and c.value]


def isi(root, label, val):
    for c in walk(root):
        if isinstance(c, ft.TextField) and c.label == label:
            c.value = val; return
    raise AssertionError(label)


# ── engine & lokasi ──
assert engine.hitung_layanan("motor", "ban_bocor", 2, 12)["biaya_total"] == 55000
assert engine.hitung_layanan("motor", "ban_bocor", 11, 12)["terjangkau"] is False
assert engine.diagnosa_ai("ban saya bocor kena paku")[0] == "ban_bocor"
w = lokasi.sekarang(); assert "·" in w["label"] and 0 <= w["jam"] <= 23 and lokasi.eta_menit(2) >= 3
ok("engine, jam sekarang, estimasi tiba")

# ── daftar pengguna ──
pg = FakePage(); app_pengguna.main(pg); a = screen(pg)
next(c for c in walk(a) if isinstance(c, ui.Segmen)).on_change(type("E", (), {"data": "1"})())
isi(a, "Nama lengkap", "Kaysan Uji"); isi(a, "No. HP", "0811"); isi(a, "Email", "kaysan@uji.id"); isi(a, "Kata sandi", "rahasia1")
klik(tombol(a, "Buat Akun"))
assert len(pg.nav.tiles) == 3 and pg.nav.kontrol.visible
ok("pengguna: daftar -> masuk")

# ── beranda: tanpa slider simulasi, lokasi + jam tampil otomatis ──
b = screen(pg)
assert not any(isinstance(c, ft.Slider) for c in walk(b)), "slider simulasi masih ada"
t = teks_semua(b)
assert "Lokasi perkiraan" in t or "GPS aktif" in t, t
assert any("·" in x and ":" in x for x in t), "jam sekarang tidak tampil"
assert any("Surakarta" in x for x in t)
assert tombol(b, "Cari Mekanik Terdekat").disabled is False
ok("beranda: lokasi & jam otomatis, tanpa slider simulasi")

# efek masuk bertahap menyalakan semua kartu
fx = [c for c in walk(b) if getattr(c, "data", None) == "fx"]
assert fx and all(c.opacity == 1 for c in fx)
ok(f"efek: {len(fx)} kartu muncul bertahap")

# ── mitra Pak Joko (id 1, posisi simulasi paling JAUH) membuka aplikasinya -> online ──
pm = FakePage(); app_mitra.main(pm); m = screen(pm)
isi(m, "Email", "joko@otofix.id"); isi(m, "Kata sandi", "mitra123"); klik(tombol(m, "Masuk"))
assert 1 in db.id_online() and pm.nav.kontrol.visible
ok("mitra: login -> status online")

# ── cari mekanik: halaman animasi -> hasil -> pesan ──
klik(tombol(b, "Cari Mekanik Terdekat"))   # jalankan proses_cari sinkron (JEDA=0)
h = screen(pg)
assert "Mekanik Ditemukan" in teks_semua(h) and pg.nav.kontrol.visible is False
ok("pencarian: halaman animasi lalu hasil 'Mekanik Ditemukan'")
klik(tombol(h, "Pesan Sekarang"))
uid = pg.client_storage["otofix_pengguna"]
p = db.pesanan_user(uid)[0]
assert p["status"] == "Mencari mekanik" and p["antrean"] and p["lokasi"], p
assert db.penawaran(p) == 1, "mitra online harus yang ditawari"
ok(f"pesanan #{p['id']}: ditawarkan ke mitra yang sedang online (id {db.penawaran(p)})")
st = screen(pg); assert any(isinstance(c, ft.Container) and str(c.data).startswith("pulse:") for c in walk(st))
ok("status: radar berdenyut saat mencari mekanik")

# ── foto profil pengguna ──
from PIL import Image
img = os.path.join(_tmp, "f.png"); Image.new("RGB", (900, 600), "#ff8800").save(img)
b64 = db.foto_dari_file(img); assert len(b64) < 40000
tab(pg, 2); pf = screen(pg)
klik(tombol(pf, "Ubah foto"))
ev = type("Ev", (), {"files": [type("F", (), {"path": img})()]})()
ui._PICKER[id(pg)].on_result(ev)
assert db.akun(uid)["foto"], "foto tidak tersimpan"
assert any(isinstance(c, ft.Image) for c in walk(screen(pg))), "avatar foto tidak tampil"
ok("pengguna: ganti foto profil (dikecilkan 256px, tersimpan, tampil)")

# ── mitra: login mekanik pertama di antrean ──
tab(pm, 1); tab(pm, 0)  # radar dimuat ulang setelah pesanan masuk
assert any(isinstance(c, ft.FilledButton) and c.text == "Terima" for c in walk(screen(pm)))

# ── GANTI AKUN di app mitra: Pak Joko keluar, Pak Eko (id 3) masuk -> pesanan berpindah otomatis ──
tab(pm, 2); klik(tombol(screen(pm), "Keluar")); klik(tombol(pm.opened[-1], "Keluar"))
assert 1 not in db.id_online() and db.penawaran(db.pesanan(p["id"])) is None
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
assert "Menunggu mekanik online…" in teks_semua(screen(pg))
m2 = screen(pm); isi(m2, "Email", "eko@otofix.id"); isi(m2, "Kata sandi", "mitra123"); klik(tombol(m2, "Masuk"))
mid = 3
assert db.penawaran(db.pesanan(p["id"])) == mid
assert any(isinstance(c, ft.FilledButton) and c.text == "Terima" for c in walk(screen(pm))), "pesanan tidak muncul di akun baru"
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
assert "Menawarkan pesanan ke Pak Eko…" in teks_semua(screen(pg))
ok("ganti akun mitra: pesanan pindah otomatis ke akun baru & status pengguna ikut berubah")
r = screen(pm)
peta_ada = [c for c in walk(r) if type(c).__name__ == "Map"] if peta.ADA else []
assert peta.ADA and peta_ada, "peta tidak tampil di kartu pesanan mitra"
kotak = next(c for c in walk(r) if isinstance(c, ft.Container) and c.height == peta.KECIL)
penutup = next(c for c in walk(kotak) if isinstance(c, ft.Container) and c.expand is True and c.on_click)
klik(penutup); assert kotak.height == peta.BESAR
ok("mitra: peta lokasi pemesan tampil kecil, membesar saat ditekan")
klik(next(c for c in walk(r) if isinstance(c, ft.Container) and c.width == 34 and c.on_click)); assert kotak.height == peta.KECIL
ok("mitra: peta bisa dikecilkan lagi")
klik(tombol(r, "Rute di Google Maps"))
assert pm.url == f"https://www.google.com/maps/dir/?api=1&destination={p['lat']},{p['lon']}&travelmode=driving", pm.url
assert "cartocdn" not in peta.TILE and "{z}" in peta.TILE
ok("mitra: tombol Rute membuka Google Maps ke lokasi pemesan")
assert any("Surakarta" in x for x in teks_semua(r)), "alamat pemesan tidak tampil"

# foto mitra
ft_m = db.foto_dari_file(img); db.ubah_foto(mid, ft_m)
tab(pm, 2); klik(tombol(screen(pm), "Ubah foto"))
ui._PICKER[id(pm)].on_result(type("Ev", (), {"files": [type("F", (), {"path": img})()]})())
assert db.akun(mid)["foto"]
ok("mitra: ganti foto profil")
tab(pm, 0)
klik(tombol(screen(pm), "Terima"))
assert db.pesanan(p["id"])["status"] == "Mekanik menuju lokasi"
assert db.ubah_status(p["id"], "Mekanik menuju lokasi", 99) is False
ok("mitra: Terima berhasil, tidak bisa diterima dua kali")

klik(tombol(screen(pm), "Tandai Selesai")); klik(tombol(pm.opened[-1], "Selesai"))
assert db.pesanan(p["id"])["status"] == "Selesai"
tab(pm, 1); assert any("Rp" in x for x in teks_semua(screen(pm)))
ok("mitra: selesai + tab pendapatan")

# ── foto salah & lokasi mitra ──
bad = os.path.join(_tmp, "x.png"); open(bad, "wb").write(b"bukan gambar")
try: db.foto_dari_file(bad); raise SystemExit("harusnya ValueError")
except ValueError: pass
db.set_lokasi(mid, -7.57, 110.82); assert db.pos_akun(mid) == (-7.57, 110.82)
ok("db: file bukan gambar ditolak, lokasi GPS mitra tersimpan")

db.offline(3)
assert 3 not in db.id_online() and db.antrean(db.BASE_LAT, db.BASE_LON) == [] and len(db.bengkel_dalam_radius(db.BASE_LAT, db.BASE_LON)) == 3
ok("db: tanpa mitra online -> TIDAK ada cadangan ke bengkel offline (antrean kosong)")
pid2 = db.buat_pesanan(uid, dict(p), p["antrean"])
for m_ in p["antrean"]: db.tolak(pid2, m_)
assert db.pesanan(pid2)["status"] == "Ditolak"
pid3 = db.buat_pesanan(uid, dict(p), p["antrean"]); assert db.batal(pid3)
ok("db: tolak berantai & batal")
for i in (0, 1, 2): tab(pg, i)
klik(next(c for c in walk((tab(pg, 1), screen(pg))[1]) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
ok("pengguna: semua layar & detail status terbangun")

# ══ Lokasi bengkel mitra: wajib saat daftar, bisa diedit, aturan 10 km tetap ══
from flet.core.map.map import MapLatitudeLongitude as _LL
def ketuk_peta(root, lat, lon):
    mp = next(c for c in walk(root) if type(c).__name__ == "Map" and c.on_tap)
    mp.on_tap(type("E", (), {"coordinates": _LL(lat, lon)})())

assert db.daftar("mitra", "Tanpa Lokasi", "tl@x.id", "", "abcdef")[0] is False
pn = FakePage(); app_mitra.main(pn); a = screen(pn)
next(c for c in walk(a) if isinstance(c, ui.Segmen)).on_change(type("E", (), {"data": "1"})())
assert tombol(a, "Buat Akun").disabled is True
assert all(c.disabled for c in walk(a) if isinstance(c, ft.TextField) and c.label in ("Email", "Kata sandi", "Nama mekanik / bengkel", "No. HP"))
assert any("Pilih lokasi bengkel terlebih dahulu" in x for x in teks_semua(a))
klik(tombol(a, "Buat Akun"))   # dipaksa meski terkunci -> ditolak
assert db.masuk("mitra", "bengkel@baru.id", "rahasia1") is None
ok("daftar mitra: kolom akun terkunci sampai lokasi bengkel dipilih")

ketuk_peta(a, -7.575, 110.83)
assert tombol(a, "Buat Akun").disabled is False
assert all(not c.disabled for c in walk(a) if isinstance(c, ft.TextField) and c.label in ("Email", "Kata sandi"))
isi(a, "Nama mekanik / bengkel", "Bengkel Baru"); isi(a, "No. HP", "0899"); isi(a, "Email", "bengkel@baru.id"); isi(a, "Kata sandi", "rahasia1")
isi(a, "Alamat / patokan bengkel", "Jl. Slamet Riyadi 1")
klik(tombol(a, "Buat Akun"))
bid = db.masuk("mitra", "bengkel@baru.id", "rahasia1")["id"]
akun_b = db.akun(bid)
assert abs(akun_b["lat"] + 7.575) < 1e-6 and akun_b["alamat"] == "Jl. Slamet Riyadi 1" and bid in db.id_online()
ok("daftar mitra: lokasi dipilih di peta -> akun dibuat dengan lokasi & alamat bengkel")

# aturan 10 km: bengkel di luar radius tidak dipilih sistem
db.set_lokasi(bid, db.BASE_LAT + 0.2, db.BASE_LON)       # +-22 km dari pusat kota
assert engine.jarak_haversine(db.BASE_LAT, db.BASE_LON, *db.pos_akun(bid)) > 10
assert bid not in [m[1] for m in db.antrean(db.BASE_LAT, db.BASE_LON)]
ok("radius: bengkel > 10 km dari pemesan tidak ikut dipilih (walau online)")

# edit lewat Profil -> pindah ke dekat pemesan -> terpilih lagi
tab(pn, 2); prof = screen(pn)
ketuk_peta(prof, -7.57, 110.82)
klik(tombol(prof, "Simpan Lokasi"))
assert db.pos_akun(bid) == (-7.57, 110.82) and bid in [m[1] for m in db.antrean(db.BASE_LAT, db.BASE_LON)]
ok("profil mitra: lokasi bengkel bisa diubah dan langsung dipakai untuk radius")

# akun lama tanpa lokasi -> peringatan di radar
pj = FakePage(); app_mitra.main(pj); a = screen(pj)
isi(a, "Email", "joko@otofix.id"); isi(a, "Kata sandi", "mitra123"); klik(tombol(a, "Masuk"))
assert any("Lokasi bengkel belum diatur" in x for x in teks_semua(screen(pj)))
ok("mitra lama tanpa lokasi: ada peringatan untuk mengatur lokasi bengkel")

# ══ Rating dua arah ══
def bintang(root, n):
    ks = [c for c in walk(root) if isinstance(c, ft.Container) and c.data == "bintang"]
    assert len(ks) == 5; ks[n - 1].on_click(None)

# 1) mekanik (Pak Eko, id 3) menilai pelanggan lewat tab Pendapatan
assert db.pesanan(p["id"])["status"] == "Selesai" and db.pesanan(p["id"])["mekanik_id"] == 3
tab(pm, 1); klik(tombol(screen(pm), "Beri rating"))
sheet = pm.opened[-1]
bintang(sheet, 4); isi(sheet, "Komentar (opsional)", "Ramah dan tepat waktu")
klik(tombol(sheet, "Kirim Rating"))
r_pel = db.rating_pelanggan(uid)
assert r_pel["rata"] == 4.0 and r_pel["ulasan"][0]["komentar"] == "Ramah dan tepat waktu"
assert db.beri_rating(p["id"], 3, 5)[0] is False   # tidak bisa dua kali
ok("rating: mekanik menilai pelanggan (bintang + komentar), tidak bisa menilai dua kali")

# 2) pesanan baru dari pelanggan yang sama -> mekanik yang dapat bisa melihat rating pelanggan
for i in (1, bid): db.offline(i)
db.heartbeat(3)
pid4 = db.buat_pesanan(uid, dict(p), [1, 2, 3])
assert db.penawaran(db.pesanan(pid4)) == 3
tab(pm, 1); tab(pm, 0); t_radar = teks_semua(screen(pm))
assert "Rating pelanggan" in t_radar and any("Ramah dan tepat waktu" in x for x in t_radar) and any("(1 ulasan)" in x for x in t_radar)
ok("rating: mekanik yang mendapat pelanggan itu melihat rating & ulasan pelanggan")

# 3) pengguna menilai mekanik dari detail pesanan yang selesai
tab(pg, 1)
item_lama = [c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16][-1]
klik(item_lama); st_sel = screen(pg)
assert any("Beri rating untuk Pak Eko" in x for x in teks_semua(st_sel))
bintang(st_sel, 5); isi(st_sel, "Komentar (opsional)", "Cepat sampai")
klik(tombol(st_sel, "Kirim Rating"))
assert db.rating_mekanik(3)["rata"] == 5.0
t_sel = teks_semua(screen(pg))
assert any("Rating Anda untuk mekanik" in x for x in t_sel) and any("(1 ulasan)" in x for x in t_sel)
ok("rating: pengguna menilai mekanik; rating mekanik tampil di halaman pesanan pengguna")

# 4) privasi: pengguna tidak pernah melihat rating dirinya (rating dari mekanik)
for i in (0, 1, 2):
    tab(pg, i)
    assert not any("Rating pelanggan" in x for x in teks_semua(screen(pg)))
assert "rating_pelanggan" not in open("app_pengguna.py").read() and "rating_mekanik" not in open("app_mitra.py").read().replace("db.rating_mekanik(row", "").replace("db.rating_mekanik(S", "")
tab(pm, 2); assert any("RATING ANDA" in x for x in teks_semua(screen(pm)))
ok("privasi: pengguna tak bisa melihat rating dirinya; mekanik melihat rating miliknya di Profil")

# ══ Mode terang / gelap ══
TERANG = {"#FFFFFF", "#F2F2F7", "#EFEFF4", "#E5E5EA", "#E6FFFFFF"}
TEKS_TERANG = {"#1C1C1E", "#6C6C70"}
def bersih_dari_terang(root, nama):
    for c in walk(root):
        if isinstance(c, ft.Container) and c.bgcolor in TERANG: raise AssertionError(f"{nama}: latar terang tersisa {c.bgcolor}")
        if isinstance(c, ft.Text) and c.color in TEKS_TERANG: raise AssertionError(f"{nama}: teks gelap di mode gelap: {c.value}")

tab(pg, 2)
seg = [c for c in walk(screen(pg)) if isinstance(c, ui.Segmen)][-1]
seg.on_change(type("E", (), {"data": "1"})())
assert ui.MODE == "gelap" and pg.bgcolor == "#000000" and pg.theme_mode == ft.ThemeMode.DARK
assert pg.client_storage["otofix_pengguna_tema"] == "gelap"
for i, nm in enumerate(("beranda", "pesanan", "profil")):
    tab(pg, i); bersih_dari_terang(screen(pg), "pengguna/" + nm)
assert pg.nav.dalam.bgcolor not in TERANG
ok("mode gelap (pengguna): latar hitam, tidak ada panel/teks terang yang tersisa di 3 tab")

for i, nm in enumerate(("radar", "pendapatan", "profil")):
    tab(pm, i); bersih_dari_terang(screen(pm), "mitra/" + nm)
tab(pm, 2)
[c for c in walk(screen(pm)) if isinstance(c, ui.Segmen)][-1].on_change(type("E", (), {"data": "0"})())
assert ui.MODE == "terang" and pm.client_storage["otofix_mitra_tema"] == "terang"
ok("mode gelap (mitra) bersih; pilihan terang/gelap berfungsi di Profil mitra")

# tema tersimpan dipakai saat aplikasi dibuka lagi
pt = FakePage(); pt.client_storage["otofix_pengguna_tema"] = "gelap"; app_pengguna.main(pt)
assert ui.MODE == "gelap" and pt.bgcolor == "#000000"
bersih_dari_terang(screen(pt), "login-gelap")
ui.terapkan_tema("terang")
ok("tema pilihan tersimpan & dipakai saat aplikasi dibuka lagi (termasuk layar login)")

# ══════════════ FITUR BARU (9 permintaan) ══════════════
import ai, ai_ui, kendaraan_db
ai_ui.MIN_DETIK = 0

def walk_vis(c, vis=True):
    v = vis and getattr(c, "visible", True) is not False
    yield c, v
    for a in ("controls", "content", "actions", "destinations"):
        x = getattr(c, a, None)
        if x is None: continue
        for y in (x if isinstance(x, (list, tuple)) else [x]):
            if isinstance(y, ft.Control): yield from walk_vis(y, v)

def teks_terlihat(root, sub):
    return any(isinstance(c, ft.Text) and c.value and sub in c.value and v for c, v in walk_vis(root))

def ubin(root, label):   # kotak pilihan kategori (ikon + label)
    for c in walk(root):
        if isinstance(c, ft.Container) and c.on_click and any(isinstance(x, ft.Text) and x.value == label for x in walk(c)) and c.height == 78:
            return c
    raise AssertionError("ubin " + label)

def batalkan_semua(user):
    for q in db.pesanan_user(user):
        if q["status"] in db.AKTIF: db.batal(q["id"])

batalkan_semua(uid); db.heartbeat(1); db.heartbeat(3)

# ── 2) header lebih lega & simetris ──
hd = ui.header("Halo, Uji", "Butuh bantuan kendaraan?")
assert hd.padding.left == hd.padding.right == 20 and hd.padding.top >= 24 and ui.label_seksi("x").padding.left == 20
ok("header: jarak kiri = kanan = 20 (sejajar label seksi), atas 28")

# ── 6) ganti kata sandi dengan verifikasi sandi lama ──
tab(pg, 2); pf = screen(pg)
assert teks_terlihat(pf, "KEAMANAN")
isi(pf, "Kata sandi baru", "baru12345"); isi(pf, "Ulangi kata sandi baru", "baru12345")
klik(tombol(pf, "Ubah Kata Sandi")); assert teks_terlihat(pf, "Masukkan kata sandi lama terlebih dahulu")
isi(pf, "Kata sandi lama", "salahsekali"); klik(tombol(pf, "Ubah Kata Sandi")); assert teks_terlihat(pf, "Kata sandi lama salah")
isi(pf, "Ulangi kata sandi baru", "beda1234"); isi(pf, "Kata sandi lama", "rahasia1"); klik(tombol(pf, "Ubah Kata Sandi"))
assert teks_terlihat(pf, "Konfirmasi kata sandi baru tidak sama")
isi(pf, "Ulangi kata sandi baru", "baru12345"); klik(tombol(pf, "Ubah Kata Sandi"))
assert db.masuk("pengguna", "kaysan@uji.id", "baru12345") and db.masuk("pengguna", "kaysan@uji.id", "rahasia1") is None
ok("kata sandi pengguna: wajib sandi lama; salah/kosong/beda konfirmasi ditolak; berhasil bila benar")
tab(pm, 2); pfm = screen(pm)
isi(pfm, "Kata sandi lama", "mitra123"); isi(pfm, "Kata sandi baru", "sandibaru1"); isi(pfm, "Ulangi kata sandi baru", "sandibaru1")
klik(tombol(pfm, "Ubah Kata Sandi"))
assert db.masuk("mitra", "eko@otofix.id", "sandibaru1") and db.masuk("mitra", "eko@otofix.id", "mitra123") is None
ok("kata sandi mitra: ganti dengan verifikasi sandi lama")

# ── 9) kendaraan tersimpan + database + pencarian ──
assert kendaraan_db.jumlah() > 600 and len(kendaraan_db.merek("motor")) >= 15 and len(kendaraan_db.merek("mobil")) >= 30
assert ("Honda", "Vario 160") in kendaraan_db.cari("motor", "vaio 160") and ("Toyota", "Avanza") in kendaraan_db.cari("mobil", "avanza")
assert kendaraan_db.cari("mobil", "zzzzqq") == []
tab(pg, 2); pf = screen(pg)
klik(tombol(pf, "Tambah Kendaraan")); pk = screen(pg)
assert pg.nav.kontrol.visible is False and teks_terlihat(pk, "Kendaraan Saya")
cari = next(c for c in walk(pk) if isinstance(c, ft.TextField) and (c.label or "").startswith("Cari merek"))
cari.value = "vario"; cari.on_change(None)
assert teks_terlihat(pk, "Vario 160") and not teks_terlihat(pk, "Avanza")
next(c for c in walk(pk) if isinstance(c, ft.Container) and c.on_click and any(isinstance(x, ft.Text) and x.value == "Vario 160" for x in walk(c))).on_click(None)
isi(pk, "Tahun (opsional)", "2022"); isi(pk, "Plat nomor (opsional)", "ad 1234 xx")
klik(tombol(pk, "Simpan"))
kv = db.kendaraan(uid)
assert (kv["jenis"], kv["merek"], kv["model"], kv["tahun"], kv["plat"]) == ("motor", "Honda", "Vario 160", 2022, "AD 1234 XX")
assert pg.nav.kontrol.visible is True and teks_terlihat(screen(pg), "Honda Vario 160 (2022)")
ok("kendaraan: cari 'vario' -> pilih Honda Vario 160 -> tahun & plat -> tersimpan & tampil di profil")
# validasi & manual
klik(tombol(screen(pg), "Ubah")); pk = screen(pg)
klik(tombol(pk, "Tidak ketemu? Isi manual"))
isi(pk, "Merek", "Merek Langka"); isi(pk, "Model / tipe", "X-1"); isi(pk, "Tahun (opsional)", "1800"); klik(tombol(pk, "Simpan"))
assert teks_terlihat(pk, "Tahun kendaraan tidak valid") and db.kendaraan(uid)["model"] == "Vario 160"
isi(pk, "Tahun (opsional)", "2020"); klik(tombol(pk, "Simpan"))
assert db.kendaraan(uid)["merek"] == "Merek Langka"
db.simpan_kendaraan(uid, "motor", "Honda", "Vario 160", 2022, "AD 1234 XX")
ok("kendaraan: isi manual jika tak ketemu, tahun tidak valid ditolak, bisa diubah kapan saja")

# ── 8) derek terpisah & tidak tersedia untuk motor ──
tab(pg, 0); b = screen(pg)
seg_l = next(c for c in walk(b) if isinstance(c, ui.Segmen) and any(isinstance(x, ft.Text) and x.value == "Derek" for x in walk(c)))
assert not [1 for c, v in walk_vis(b) if c is seg_l and v], "opsi derek tampil untuk motor"
assert not teks_terlihat(b, "Derek kendaraan") and not teks_terlihat(b, "Layanan derek".upper())
ok("derek: tidak ditampilkan untuk motor")

# ── 5) AI: validasi, animasi, hasil, akurasi (offline) ──
panel_btn = tombol(b, "Analisis dengan AI")
klik(panel_btn)
kol_ai = next(c for c in walk(b) if isinstance(c, ft.TextField) and c.label == "Ceritakan gejalanya")
assert kol_ai.error_text, "keluhan kosong harus diberi pesan"
kol_ai.value = "ban belakang kempes kena paku"; klik(panel_btn)
assert teks_terlihat(b, "Ban bocor") and teks_terlihat(b, "Keyakinan") and teks_terlihat(b, "Sumber: Analisis offline")
box = next(c for c in walk(b) if isinstance(c, ft.Container) and c.opacity is not None and c.animate_offset is not None and c.data != "fx")
assert box.opacity == 1 and panel_btn.text == "Analisis ulang" and not panel_btn.disabled
assert any(isinstance(c, ft.ProgressBar) is False and isinstance(c, ft.Container) and c.animate is not None and c.width and c.width > 100 for c in walk(b)), "bar keyakinan harus terisi (beranimasi)"
ok("AI: validasi kosong, animasi loading->hasil, kategori Ban bocor + bar keyakinan terisi")
kol_ai.value = "ada bunyi aneh dari bawah"; klik(panel_btn)
assert teks_terlihat(b, "Estimasi harga tidak ditampilkan") and teks_terlihat(b, "Lainnya")
ok("AI -> 'Lainnya': peringatan estimasi harga muncul otomatis")
# LLM (respons palsu) dipakai bila ada API key
os.environ["ANTHROPIC_API_KEY"] = "tes"
ai._post = lambda url, h, bd, to: {"content": [{"type": "text", "text": '{"kategori":"mesin_overheat","keyakinan":0.88,"ringkasan":"Mesin terlalu panas.","saran":"Bawa coolant.","tindakan":["Matikan mesin"],"perlu_derek":false}'}]}
kol_ai.value = "mesin saya"; klik(panel_btn)
assert teks_terlihat(b, "Sumber: Claude AI") and teks_terlihat(b, "Mesin terlalu panas.") and teks_terlihat(b, "88%")
del os.environ["ANTHROPIC_API_KEY"]
ok("AI: memakai API LLM bila ada key (Claude), hasil JSON dipetakan ke kategori")

# ── 7) kategori Lainnya: peringatan + tanpa estimasi ──
klik(ubin(b, "Ban bocor")); assert not teks_terlihat(b, "Kategori Lainnya tidak menampilkan estimasi harga")
klik(ubin(b, "Lainnya"));   assert teks_terlihat(b, "Kategori Lainnya tidak menampilkan estimasi harga")
ok("kategori Lainnya: peringatan 'tanpa estimasi harga, harga via chat' tampil")
klik(tombol(b, "Cari Mekanik Terdekat")); h = screen(pg)
assert teks_terlihat(h, "Mekanik Ditemukan") and teks_terlihat(h, "Disepakati via chat") and teks_terlihat(h, "Estimasi harga tidak ditampilkan")
assert not teks_terlihat(h, "Total") and not teks_terlihat(h, "Biaya jasa")
klik(tombol(h, "Pesan Sekarang"))
pL = db.pesanan_user(uid)[0]
assert pL["hasil"]["estimasi"] is False and pL["hasil"]["biaya_total"] is None and db.harga(pL) is None and pL["kend_label"].startswith("Honda Vario 160")
ok("pesan 'Lainnya': tanpa estimasi, data kendaraan ikut tersimpan di pesanan")

# ── 1) chat setelah mendapat montir ──
st = screen(pg)
assert not [1 for c in walk(st) if isinstance(c, ft.FilledButton) and (c.text or "").startswith("Chat dengan mekanik")], "chat tidak boleh ada sebelum dapat montir"
db.heartbeat(3); db.ubah_status(pL["id"], "Mekanik menuju lokasi", 3)
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
st = screen(pg); assert teks_terlihat(st, "Harga belum ditentukan")
klik(tombol(st, "Chat dengan mekanik")); ch = screen(pg)
assert pg.nav.kontrol.visible is False and teks_terlihat(ch, "Pak Eko") and teks_terlihat(ch, "Belum ada pesan") and teks_terlihat(ch, "Harga belum ditentukan")
isi(ch, "Tulis pesan…", "Halo pak, mobil saya mogok di depan toko"); next(c for c in walk(ch) if isinstance(c, ft.Container) and c.width == 46 and c.on_click).on_click(None)
assert [m["teks"] for m in db.chat_pesanan(pL["id"], uid)] == ["Halo pak, mobil saya mogok di depan toko"] and teks_terlihat(ch, "Halo pak, mobil saya mogok")
ok("chat: tombol chat baru muncul setelah dapat montir; pengguna bisa kirim pesan (gelembung tampil)")
assert db.chat_belum_dibaca(pL["id"], 3) == 1
tab(pm, 0); card = screen(pm)
btn_chat = next(c for c in walk(card) if isinstance(c, ft.FilledButton) and (c.text or "").startswith("Chat dengan pemesan"))
assert btn_chat.text == "Chat dengan pemesan (1)" and teks_terlihat(card, "Via chat")
klik(btn_chat); cm = screen(pm)
assert teks_terlihat(cm, "Halo pak, mobil saya mogok") and teks_terlihat(cm, "sepakati harga") and pm.nav.kontrol.visible is False
isi(cm, "Tulis pesan…", "Siap, 15 menit lagi saya sampai. Biaya sekitar 175 ribu ya."); next(c for c in walk(cm) if isinstance(c, ft.Container) and c.width == 46 and c.on_click).on_click(None)
assert db.chat_belum_dibaca(pL["id"], 3) == 0 and db.chat_belum_dibaca(pL["id"], uid) == 1
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
assert any((c.text or "") == "Chat dengan mekanik (1)" for c in walk(screen(pg)) if isinstance(c, ft.FilledButton))
klik(tombol(screen(pg), "Chat dengan mekanik (1)")); assert teks_terlihat(screen(pg), "175 ribu") and db.chat_belum_dibaca(pL["id"], uid) == 0
ok("chat dua arah: pesan balasan montir, penanda belum dibaca, banner harga via chat")

# harga kesepakatan saat selesai (kategori Lainnya)
tab(pm, 0); klik(tombol(screen(pm), "Tandai Selesai")); klik(tombol(pm.opened[-1], "Selesai"))
dlg = pm.opened[-1]; isi(dlg, "Harga (Rp)", "175.000"); klik(tombol(dlg, "Simpan & Selesai"))
assert db.pesanan(pL["id"])["status"] == "Selesai" and db.harga(db.pesanan(pL["id"])) == 175000
tab(pm, 1); assert teks_terlihat(screen(pm), "Rp175.000")
assert db.kirim_chat(pL["id"], uid, "masih bisa?")[0] is False
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
assert teks_terlihat(screen(pg), "Rp175.000"); klik(tombol(screen(pg), "Lihat riwayat chat"))
assert teks_terlihat(screen(pg), "Chat ditutup")
ok("harga kesepakatan dicatat saat selesai (pendapatan mitra & status pengguna); chat ditutup setelah selesai")

# ── 8) derek untuk mobil (layanan terpisah) ──
db.simpan_kendaraan(uid, "mobil", "Toyota", "Avanza", 2019, "AD 1 A")
tab(pg, 0); b = screen(pg)
seg_l = next(c for c in walk(b) if isinstance(c, ui.Segmen) and any(isinstance(x, ft.Text) and x.value == "Derek" for x in walk(c)))
assert [1 for c, v in walk_vis(b) if c is seg_l and v], "opsi derek harus tampil untuk mobil"
seg_l.on_change(type("E", (), {"data": "1"})())
assert teks_terlihat(b, "Biaya jasa derek") and not teks_terlihat(b, "Apa kendalanya?".upper()) and tombol(b, "Cari Derek Terdekat")
klik(tombol(b, "Cari Derek Terdekat")); h = screen(pg)
assert teks_terlihat(h, "Derek Kendaraan") and teks_terlihat(h, "Total") and any("Rp" in x for x in teks_semua(h))
klik(tombol(h, "Pesan Sekarang")); pD = db.pesanan_user(uid)[0]
assert pD["kategori"] == "derek" and pD["hasil"]["jenis_layanan"] == "Derek Kendaraan" and pD["hasil"]["biaya_jasa"] == 200000
db.batal(pD["id"])
ok("derek: layanan tersendiri khusus mobil (Rp200.000 + ongkos), tidak bercampur kategori kerusakan")
# AI menyarankan derek untuk mobil
tab(pg, 0); b = screen(pg)
assert tombol(b, "Cari Derek Terdekat")   # pilihan layanan terakhir (derek) diingat; kembali ke mekanik panggilan
next(c for c in walk(b) if isinstance(c, ui.Segmen) and any(isinstance(x, ft.Text) and x.value == "Derek" for x in walk(c))).on_change(type("E", (), {"data": "0"})())
next(c for c in walk(b) if isinstance(c, ft.TextField) and c.label == "Ceritakan gejalanya").value = "rem blong pedal dalam"
klik(tombol(b, "Analisis dengan AI")); assert teks_terlihat(b, "Layanan derek disarankan")
klik(tombol(b, "Pakai layanan Derek")); assert tombol(b, "Cari Derek Terdekat")
ok("AI: saran layanan derek untuk mobil + tombol langsung pindah ke Derek")

# ── 4) penolakan terlihat di layar pengguna ──
batalkan_semua(uid); db.heartbeat(1); db.heartbeat(3)
semua = [m[1] for m in db.mitra_terdekat(db.BASE_LAT, db.BASE_LON) if m[0] <= 10]
pidR = db.buat_pesanan(uid, dict(nama="Kaysan", kendaraan="mobil", kend_label="Toyota Avanza", layanan="panggilan", kategori="ban_bocor", analisis="x",
                                 lat=db.BASE_LAT, lon=db.BASE_LON, lokasi="Surakarta", jarak=1.0,
                                 hasil=engine.hitung_layanan("mobil", "ban_bocor", 1.0, 12)), semua)
pertama = db.penawaran(db.pesanan(pidR)); db.tolak(pidR, pertama)
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
s1 = screen(pg); nama1 = db.akun(pertama)["nama"]
assert teks_terlihat(s1, "Pesanan ditolak") and teks_terlihat(s1, f"ditolak oleh {nama1}") and teks_terlihat(s1, "mencari mekanik lain")
for mid_ in semua: db.tolak(pidR, mid_)
assert db.pesanan(pidR)["status"] == "Ditolak"
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
s2 = screen(pg); assert teks_terlihat(s2, "Pesanan Anda ditolak oleh semua bengkel terdekat.") and tombol(s2, "Cari Lagi")
ok("penolakan: layar pengguna menulis 'ditolak oleh <montir>'; bila semua menolak -> status Ditolak + tombol Cari Lagi")

# ── 3) tidak ada bengkel terdekat ──
semua_m = [m[1] for m in db.mitra_terdekat(0, 0)]
lama = {i: db.pos_akun(i) for i in semua_m}
for i in semua_m: db.set_lokasi(i, db.BASE_LAT + 0.5, db.BASE_LON)     # semua bengkel > 50 km
tab(pg, 0); b = screen(pg); klik(tombol(b, "Cari Derek Terdekat" if tombol(b, "Cari Derek Terdekat") else "Cari Mekanik Terdekat"))
h = screen(pg)
assert teks_terlihat(h, "Tidak ada bengkel terdekat") and not teks_terlihat(h, "Pesan Sekarang") and not teks_terlihat(h, "Di Luar Jangkauan")
for i, (la, lo) in lama.items(): db.set_lokasi(i, la, lo)
ok("tidak ada bengkel dalam 10 km: layar menulis 'Tidak ada bengkel terdekat'")

# ── mode gelap tetap bersih di layar-layar baru ──
ui.terapkan_tema("gelap", pg)
db.simpan_kendaraan(uid, "mobil", "Toyota", "Avanza", 2019, "AD 1 A")
tab(pg, 0); b = screen(pg)
next(c for c in walk(b) if isinstance(c, ft.TextField) and c.label == "Ceritakan gejalanya").value = "rem blong"
klik(tombol(b, "Analisis dengan AI"))
bersih_dari_terang(screen(pg), "gelap/beranda+AI+derek")
tab(pg, 2); bersih_dari_terang(screen(pg), "gelap/profil")
klik(tombol(screen(pg), "Ubah")); bersih_dari_terang(screen(pg), "gelap/pilih-kendaraan"); klik(tombol(screen(pg), "Batal"))
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
tab(pg, 1); items = [c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16]
klik(next(c for c in items if any(isinstance(x, ft.Text) and x.value == "Lainnya" for x in walk(c))))
klik(tombol(screen(pg), "Lihat riwayat chat")); bersih_dari_terang(screen(pg), "gelap/chat")
ui.terapkan_tema("terang", pg)
ok("mode gelap: beranda+AI, profil (sandi & kendaraan), pilih kendaraan, chat bersih dari panel/teks terang")

# ── BUG: tab bar (Radar/Pendapatan/Profil) hilang di aplikasi mitra setelah membuka chat / menyelesaikan pesanan ──
batalkan_semua(uid); db.heartbeat(3)
pidB = db.buat_pesanan(uid, dict(nama="Kaysan", kendaraan="mobil", kend_label="Toyota Avanza", layanan="panggilan", kategori="ban_bocor",
                                 analisis="x", lat=db.BASE_LAT, lon=db.BASE_LON, lokasi="Surakarta", jarak=1.0,
                                 hasil=engine.hitung_layanan("mobil", "ban_bocor", 1.0, 12)), [3])
db.ubah_status(pidB, "Mekanik menuju lokasi", 3)
tab(pm, 0); assert pm.nav.kontrol.visible is True
klik(next(c for c in walk(screen(pm)) if isinstance(c, ft.FilledButton) and (c.text or "").startswith("Chat dengan pemesan")))
assert pm.nav.kontrol.visible is False                       # chat memang menyembunyikan tab bar
next(c for c in walk(screen(pm)) if isinstance(c, ft.IconButton) and c.icon == ft.Icons.ARROW_BACK_IOS_NEW).on_click(None)
assert pm.nav.kontrol.visible is True, "tab bar mitra tidak kembali setelah keluar dari chat"
klik(tombol(screen(pm), "Tandai Selesai")); klik(tombol(pm.opened[-1], "Selesai"))
assert db.pesanan(pidB)["status"] == "Selesai" and pm.nav.kontrol.visible is True and len(pm.nav.tiles) == 3
for i in (0, 1, 2):
    tab(pm, i); assert pm.nav.kontrol.visible is True
ok("mitra: tab bar tetap/kembali tampil setelah chat dan setelah pesanan diselesaikan")

# ══ Bengkel offline tidak boleh dijadikan pengganti + tarik-untuk-refresh ══
def tombol_cari(root):
    return next(c for c in walk(root) if isinstance(c, ft.FilledButton) and (c.text or "").startswith("Cari "))

batalkan_semua(uid)
sebelum = len(db.pesanan_user(uid))
for i in [m[1] for m in db.mitra_terdekat(0, 0)]: db.offline(i)              # semua bengkel offline
tab(pg, 0); b = screen(pg); klik(tombol_cari(b)); h = screen(pg)
t_h = teks_semua(h)
assert teks_terlihat(h, "Tidak ada bengkel tersedia") and teks_terlihat(h, "sedang tidak online") and teks_terlihat(h, "tidak akan dialihkan")
assert not teks_terlihat(h, "Mekanik Ditemukan") and not any("Pak Eko" in x or "Pak Joko" in x or "Mas Dimas" in x for x in t_h)
assert not [1 for c in walk(h) if isinstance(c, ft.FilledButton) and c.text == "Pesan Sekarang"]
assert len(db.pesanan_user(uid)) == sebelum, "tidak boleh ada pesanan yang dibuat"
ok("bengkel offline: layar 'Tidak ada bengkel tersedia' + peringatan, tidak dialihkan ke bengkel lain, tidak ada pesanan dibuat")
db.heartbeat(3); klik(tombol(h, "Coba Lagi")); assert teks_terlihat(screen(pg), "Mekanik Ditemukan") and teks_terlihat(screen(pg), "Pak Eko")
ok("'Coba Lagi' langsung menemukan bengkel begitu ada yang online")

# bengkel jauh (> 10 km) juga tidak dipakai walau online
for i in [m[1] for m in db.mitra_terdekat(0, 0)]: db.heartbeat(i)
lama2 = {i: db.pos_akun(i) for i in [m[1] for m in db.mitra_terdekat(0, 0)]}
for i in lama2: db.set_lokasi(i, db.BASE_LAT + 0.5, db.BASE_LON)
tab(pg, 0); klik(tombol_cari(screen(pg))); h = screen(pg)
assert teks_terlihat(h, "Tidak ada bengkel terdekat") and teks_terlihat(h, "tidak akan dialihkan") and not teks_terlihat(h, "Mekanik Ditemukan")
for i, (la, lo) in lama2.items(): db.set_lokasi(i, la, lo)
ok("bengkel online tapi > 10 km: 'Tidak ada bengkel terdekat' + peringatan, tidak dialihkan")

# pesanan yang menunggu tanpa bengkel online: peringatan, bukan dialihkan
for i in [m[1] for m in db.mitra_terdekat(0, 0)]: db.offline(i)
pidW = db.buat_pesanan(uid, dict(nama="Kaysan", kendaraan="mobil", kend_label="", layanan="panggilan", kategori="ban_bocor", analisis="x",
                                 lat=db.BASE_LAT, lon=db.BASE_LON, lokasi="Surakarta", jarak=1.0,
                                 hasil=engine.hitung_layanan("mobil", "ban_bocor", 1.0, 12)), [1, 2, 3])
assert db.penawaran(db.pesanan(pidW)) is None
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
assert teks_terlihat(screen(pg), "Belum ada bengkel online di sekitar Anda") and teks_terlihat(screen(pg), "Menunggu mekanik online")
db.batal(pidW)
ok("pesanan menunggu tanpa bengkel online: ada peringatan, tidak dilempar ke bengkel offline")

# ── tarik ke bawah untuk memuat ulang ──
class Ev:
    def __init__(self, t, pixels=0, overscroll=None): self.event_type, self.pixels, self.overscroll = t, pixels, overscroll

def kolom_scroll(root):
    return next(c for c in walk(root) if isinstance(c, ft.Column) and c.on_scroll)

for i in [m[1] for m in db.mitra_terdekat(0, 0)]: db.heartbeat(i)
tab(pg, 0); b = screen(pg); kol = kolom_scroll(b)
assert kol.scroll == ft.ScrollMode.ALWAYS and kol.controls[0].height == 0
# tarikan pendek tidak memicu
kol.on_scroll(Ev("update", -20)); assert screen(pg) is b
# data berubah di server saat layar terbuka -> tarik ke bawah (iOS/macOS: posisi gulir negatif) -> termuat
pidP = db.buat_pesanan(uid, dict(nama="Kaysan", kendaraan="mobil", kend_label="", layanan="panggilan", kategori="ban_bocor", analisis="x",
                                 lat=db.BASE_LAT, lon=db.BASE_LON, lokasi="Surakarta", jarak=1.0,
                                 hasil=engine.hitung_layanan("mobil", "ban_bocor", 1.0, 12)), [1, 2, 3])
assert not teks_terlihat(b, "Pesanan sedang berjalan")
kol.on_scroll(Ev("update", -90))
b2 = screen(pg); assert b2 is not b and teks_terlihat(b2, "Pesanan sedang berjalan") and any("Surakarta" in x for x in teks_semua(b2))
db.batal(pidP)
ok("tarik ke bawah di Beranda pengguna: data & lokasi dimuat ulang (indikator 'Memuat ulang…')")
# platform clamping (Android/Windows): notifikasi overscroll yang diakumulasi
b = screen(pg); kol = kolom_scroll(b)
for _ in range(3): kol.on_scroll(Ev("overscroll", 0, -30))
assert screen(pg) is not b
ok("tarik ke bawah (Android/Windows via overscroll): memicu refresh setelah melewati ambang")
# mitra: radar dimuat ulang
tab(pm, 0); r = screen(pm); kol = kolom_scroll(r)
assert not [1 for c in walk(r) if isinstance(c, ft.FilledButton) and c.text == "Terima"]
db.heartbeat(3); db.set_lokasi(3, db.BASE_LAT, db.BASE_LON)
pidM = db.buat_pesanan(uid, dict(nama="Kaysan", kendaraan="mobil", kend_label="", layanan="panggilan", kategori="ban_bocor", analisis="x",
                                 lat=db.BASE_LAT, lon=db.BASE_LON, lokasi="Surakarta", jarak=1.0,
                                 hasil=engine.hitung_layanan("mobil", "ban_bocor", 1.0, 12)), [3])
kol.on_scroll(Ev("update", -100))
assert [1 for c in walk(screen(pm)) if isinstance(c, ft.FilledButton) and c.text == "Terima"]
db.batal(pidM)
ok("tarik ke bawah di Radar mitra: permintaan baru langsung muncul")
tab(pg, 1); assert kolom_scroll(screen(pg)); tab(pm, 1); assert kolom_scroll(screen(pm))
ok("tarik-untuk-refresh juga aktif di Pesanan (pengguna) dan Pendapatan (mitra)")

# ── segmented control responsif (tidak terpotong di layar HP) ──
db.simpan_kendaraan(uid, "mobil", "Toyota", "Avanza", 2019, "AD 1 A"); tab(pg, 0)
for sg in [c for c in walk(screen(pg)) if isinstance(c, ui.Segmen)]:
    assert sg.expand is True and sg.border_radius >= 12 and all(x.expand is True for x in sg.tiles) and sg.width is None
sg = next(c for c in walk(screen(pg)) if isinstance(c, ui.Segmen) and any(isinstance(x, ft.Text) and x.value == "Derek" for x in walk(c)))
baris_induk = next(c for c in walk(screen(pg)) if isinstance(c, ft.Row) and sg in c.controls)
assert baris_induk.alignment == ft.MainAxisAlignment.CENTER
ok("segmented 'Jenis layanan': selebar kartu, 2 segmen sama lebar, sudut membulat, isi di tengah (responsif di HP)")

# ══ Pelacakan langsung posisi mekanik + telepon di chat room ══
import lokasi as _lok
assert _lok.telp_uri("0813-4567-8901") == "tel:+6281345678901" and _lok.telp_uri("+62 812 000 0000") == "tel:+628120000000"
assert _lok.telp_uri("0811") is None and _lok.telp_uri("") is None and _lok.telp_uri("abc") is None

batalkan_semua(uid); db.heartbeat(3)
db.ubah_profil(uid, "Kaysan Uji", "0813-4567-8901")
db.set_lokasi(3, db.BASE_LAT - 0.02, db.BASE_LON)                  # bengkel Pak Eko +-2,2 km dari pelanggan
pidT = db.buat_pesanan(uid, dict(nama="Kaysan", kendaraan="mobil", kend_label="Toyota Avanza", layanan="panggilan", kategori="ban_bocor",
                                 analisis="x", lat=db.BASE_LAT, lon=db.BASE_LON, lokasi="Surakarta", jarak=2.2,
                                 hasil=engine.hitung_layanan("mobil", "ban_bocor", 2.2, 12)), [3])
assert db.ubah_status(pidT, "Mekanik menuju lokasi", 3)
assert db.lokasi_mekanik(pidT, uid) is None                         # belum ada sinyal
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
st = screen(pg)
assert teks_terlihat(st, "Posisi mekanik") and teks_terlihat(st, "LANGSUNG") and teks_terlihat(st, "Menunggu sinyal lokasi mekanik")
ok("pelacakan: kartu 'Posisi mekanik' muncul begitu pesanan disetujui (menunggu sinyal)")

# mitra mulai membagikan posisi (tanpa GPS -> simulasi bergerak dari bengkel menuju pelanggan)
tab(pm, 0); assert teks_terlihat(screen(pm), "Posisi Anda dibagikan langsung ke pemesan")
jarak_ke = lambda: engine.jarak_haversine(db.BASE_LAT, db.BASE_LON, db.lokasi_mekanik(pidT, uid)["lat"], db.lokasi_mekanik(pidT, uid)["lon"])
pm.bagikan_lokasi(); j1 = jarak_ke()
assert 1.5 < j1 < 2.3 and pg.lacak.mk_pos is None
pg.lacak.perbarui()
assert pg.lacak.mk_pos is not None and teks_terlihat(pg.lacak.kontrol, "Pak Eko berjarak") and teks_terlihat(pg.lacak.kontrol, "tiba ±") \
    and teks_terlihat(pg.lacak.kontrol, "Diperbarui") and len(pg.lacak.lapis.markers) == 2
ok("pelacakan: mekanik membagikan posisi -> pengguna melihat jarak, perkiraan tiba, dan 2 penanda di peta")

# posisi bergerak mendekat secara real time
urut = [j1]
for _ in range(4):
    pm.bagikan_lokasi(); pg.lacak.perbarui(); urut.append(jarak_ke())
assert all(a > b for a, b in zip(urut, urut[1:])), urut
pos_lama = pg.lacak.mk_pos
pm.bagikan_lokasi(); pg.lacak.perbarui(); assert pg.lacak.mk_pos != pos_lama
for _ in range(12): pm.bagikan_lokasi()
pg.lacak.perbarui(); assert teks_terlihat(pg.lacak.kontrol, "Mekanik sudah tiba di lokasi Anda") and jarak_ke() < 0.01
ok(f"pelacakan: posisi bergerak mendekat ({urut[0]:.2f} -> {urut[-1]:.2f} km) lalu 'Mekanik sudah tiba'")

# kontrol akses & kedaluwarsa
assert db.lokasi_mekanik(pidT, uid + 999) is None
with db._c() as cx: cx.execute("update akun set live_pada=? where id=3", (__import__("time").time() - 500,))
assert db.lokasi_mekanik(pidT, uid) is None
pm.bagikan_lokasi(); assert db.lokasi_mekanik(pidT, uid) is not None
ok("pelacakan: hanya pemilik pesanan yang bisa melihat; sinyal basi (>60 dtk) diabaikan")

# ── telepon di chat room ──
db.kirim_chat(pidT, uid, "Pak, saya di depan toko")
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.FilledButton) and (c.text or "").startswith("Chat dengan mekanik"))); ch = screen(pg)
tel = next(c for c, v in walk_vis(ch) if isinstance(c, ft.IconButton) and c.icon == ft.Icons.CALL and v)
pg.url = None; tel.on_click(None)
dlg = pg.opened[-1]; assert isinstance(dlg, ft.CupertinoAlertDialog) and "Pak Eko" in dlg.title.value and pg.url is None
klik(tombol(dlg, "Telepon")); assert pg.url == "tel:+62812000000"
ok("telepon (pengguna): ikon telepon di chat room -> konfirmasi -> membuka dialer tel:+62812000000")
tab(pm, 0); klik(next(c for c in walk(screen(pm)) if isinstance(c, ft.FilledButton) and (c.text or "").startswith("Chat dengan pemesan"))); cm = screen(pm)
telm = next(c for c, v in walk_vis(cm) if isinstance(c, ft.IconButton) and c.icon == ft.Icons.CALL and v)
pm.url = None; telm.on_click(None); klik(tombol(pm.opened[-1], "Telepon")); assert pm.url == "tel:+6281345678901"
ok("telepon (mitra): menelepon pemesan dari chat room -> tel:+6281345678901")

# nomor belum diisi -> pemberitahuan, tidak menelepon
db.ubah_profil(3, "Pak Eko", "")
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.FilledButton) and (c.text or "").startswith("Chat dengan mekanik")))
pg.url = None; next(c for c, v in walk_vis(screen(pg)) if isinstance(c, ft.IconButton) and c.icon == ft.Icons.CALL and v).on_click(None)
assert pg.url is None and isinstance(pg.opened[-1], ft.SnackBar) and "belum diisi" in pg.opened[-1].content.value
db.ubah_profil(3, "Pak Eko", "0812000000")
ok("telepon: nomor lawan belum diisi -> pemberitahuan, tidak ada panggilan")

# setelah pesanan selesai: tombol telepon hilang, posisi tidak lagi dibagikan
db.ubah_status(pidT, "Selesai"); pm.bagikan_lokasi()
assert db.lokasi_mekanik(pidT, uid) is None and db.akun(3)["live_lat"] is None
tab(pg, 1); klik(next(c for c in walk(screen(pg)) if isinstance(c, ft.Container) and c.on_click and c.border_radius == 16))
assert not teks_terlihat(screen(pg), "Posisi mekanik")
klik(tombol(screen(pg), "Lihat riwayat chat"))
assert not [1 for c, v in walk_vis(screen(pg)) if isinstance(c, ft.IconButton) and c.icon == ft.Icons.CALL and v]
ok("setelah selesai: tombol telepon & pelacakan hilang, posisi mekanik dihapus (privasi)")

print("\nSEMUA TES LULUS")

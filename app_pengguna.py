"""OtoFix Pengguna - aplikasi untuk pengendara (UI gaya iOS)."""
import time
import flet as ft
import db
import ui
import lokasi
from chat_ui import Chat
from ai_ui import PanelAI
from kendaraan_ui import PilihKendaraan
from peta import PetaLacak
from engine import KATEGORI, NAMA_KATEGORI, BIAYA_DEREK, hitung_layanan, rupiah, teks_biaya, biaya_efektif, MAX_JARAK_KM
from ui import TW, M, PENGGUNA as T

IKON = dict(
    ban_bocor="TIRE_REPAIR", aki_soak="BATTERY_ALERT", bensin_habis="LOCAL_GAS_STATION",
    mesin_overheat="THERMOSTAT", kelistrikan="BOLT", rem_blong="WARNING_AMBER",
    bodi_rusak="CAR_CRASH", rantai_putus="LINK_OFF", lainnya="MORE_HORIZ", derek="LOCAL_SHIPPING",
)
KEY = "otofix_pengguna"
KEY_TEMA = KEY + "_tema"
JEDA = 1.3  # detik per langkah animasi pencarian
PUTIH70 = ui.alpha("white", 0.75)
TEKS_LAINNYA = ("Kategori Lainnya tidak menampilkan estimasi harga. Harga ditentukan lewat chat antara Anda dan montir "
                "setelah pesanan diterima.")


def main(page: ft.Page):
    db.init()
    ui.setup(page, "OtoFix", page.client_storage.get(KEY_TEMA))
    host = ui.layar()
    S = {"u": None, "kat": "ban_bocor", "kend": "motor", "layanan": "panggilan", "ai": "", "tok": 0, "tab": 0,
         "loc": None, "hero": None, "tolak_seen": {}}
    pelacak = lokasi.Pelacak(page)
    bar_nav = page.nav = ui.NavFlotan(T, lambda i: pindah(i))
    page.add(ft.SafeArea(ft.Stack([host, bar_nav.kontrol], expand=True), expand=True))

    def tampil(c):
        ui.tampil(page, host, c)

    def snack(t):
        ui.snack(page, t)

    def nav(terlihat):
        bar_nav.tampil(terlihat)

    # ── Masuk / keluar / navigasi ──────────────────────────────────────────
    def login():
        tampil(ui.auth(page, "pengguna", "OtoFix", "Bantuan kendaraan darurat, langsung ke lokasi Anda.", T, masuk))

    def masuk(row):
        S["u"] = row
        page.client_storage.set(KEY, row["id"])
        bar_nav.atur([
            (ft.Icons.HOME_OUTLINED, ft.Icons.HOME_ROUNDED, "Beranda"),
            (ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG, "Pesanan"),
            (ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON, "Profil"),
        ])
        pindah(0)

    def keluar():
        S.update(u=None, tok=S["tok"] + 1)
        page.client_storage.remove(KEY)
        bar_nav.tampil(False)
        login()

    def pindah(i):
        S["tok"] += 1  # menghentikan semua thread pemantau/animasi lama
        S["tab"] = i
        ui.tema_gelap(page, False)
        nav(True)
        bar_nav.pilih(i)
        [beranda, riwayat, profil][i]()

    def ganti_tema(mode):
        page.client_storage.set(KEY_TEMA, mode)
        ui.terapkan_tema(mode, page)
        bar_nav.tema_ulang()
        profil()

    # ── Kendaraan tersimpan ────────────────────────────────────────────────
    def kendaraan_form(kembali):
        S["tok"] += 1
        nav(False)

        def simpan_k(jenis, merek, model, tahun, plat):
            ok, msg = db.simpan_kendaraan(S["u"]["id"], jenis, merek, model, tahun, plat)
            if ok:
                S["u"] = db.akun(S["u"]["id"])
                S["kend"] = jenis
                if jenis == "motor":
                    S["layanan"] = "panggilan"
                snack("Kendaraan tersimpan")
                kembali()
            return ok, msg
        tampil(PilihKendaraan(page, T, db.kendaraan(S["u"]["id"]), simpan_k, kembali).kontrol)

    def kartu_kendaraan(kembali, kompak=False):
        kv = db.kendaraan(S["u"]["id"])
        if not kv:
            return ui.kartu(
                ft.Row([ui.ikon_bulat(ft.Icons.DIRECTIONS_CAR_OUTLINED, T),
                        ft.Column([ft.Text("Belum ada kendaraan tersimpan", size=15, weight=TW.W_600, color=ui.LABEL),
                                   ft.Text("Simpan sekali, dipakai otomatis untuk pesanan berikutnya.", size=12, color=ui.SECONDARY)],
                                  spacing=2, expand=True)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([ui.tombol("Tambah Kendaraan", ft.Icons.ADD, lambda e: kendaraan_form(kembali), T)]))
        return ui.kartu(ft.Row([
            ui.ikon_bulat(ft.Icons.TWO_WHEELER if kv["jenis"] == "motor" else ft.Icons.DIRECTIONS_CAR, T, 44),
            ft.Column([ft.Text(db.label_kendaraan(kv), size=16, weight=TW.W_700, color=ui.LABEL),
                       ft.Text(("Plat " + kv["plat"] + " · " if kv["plat"] else "") + kv["jenis"].title(), size=13, color=ui.SECONDARY)],
                      spacing=2, expand=True),
            ft.TextButton("Ubah", on_click=lambda e: kendaraan_form(kembali), style=ft.ButtonStyle(color=T["aksen"]))],
            spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    # ── Profil ─────────────────────────────────────────────────────────────
    def profil():
        def segarkan():
            S["u"] = db.akun(S["u"]["id"])
            profil()
        tampil(ui.profil(page, S["u"], T, simpan, keluar, "Akun pengendara", segarkan,
                         ekstra=[ui.label_seksi("Kendaraan saya"), kartu_kendaraan(lambda: pindah(2))],
                         mode_tema=ui.MODE, saat_tema=ganti_tema))

    def simpan(nama, telp):
        db.ubah_profil(S["u"]["id"], nama, telp)
        S["u"] = db.akun(S["u"]["id"])
        snack("Profil tersimpan")
        profil()

    # ── Lokasi ─────────────────────────────────────────────────────────────
    def cari_lokasi():
        tok = S["tok"]
        lat, lon, ok = pelacak.posisi()
        S["loc"] = dict(lat=lat, lon=lon, akurat=ok, nama=lokasi.nama_tempat(lat, lon, ok))
        if S["tok"] == tok and S["hero"]:
            S["hero"]()
            try:
                page.update()
            except Exception:
                pass

    def jam_berjalan(tok):
        while S["tok"] == tok and S["tab"] == 0:
            time.sleep(20)
            if S["tok"] == tok and S["hero"]:
                S["hero"]()
                try:
                    page.update()
                except Exception:
                    pass

    # ── Beranda ────────────────────────────────────────────────────────────
    def beranda():
        aktif = db.pesanan_aktif_user(S["u"]["id"])
        kv = db.kendaraan(S["u"]["id"])
        if kv:
            S["kend"] = kv["jenis"]
        if S["kend"] == "motor":
            S["layanan"] = "panggilan"  # derek tidak tersedia untuk motor

        tbl_cari = ui.tombol("Cari Derek Terdekat" if S["layanan"] == "derek" else "Cari Mekanik Terdekat", ft.Icons.SEARCH, None, T)

        # blok-blok yang tampil/sembunyi sesuai pilihan (tanpa membangun ulang layar)
        peringatan_lainnya = ui.peringatan(TEKS_LAINNYA, "Estimasi harga tidak ditampilkan", ft.Icons.INFO_OUTLINE)
        peringatan_lainnya.visible = S["kat"] == "lainnya"
        kat, set_kat = ui.pilihan([(k, IKON[k], v) for k, v in KATEGORI.items()], S["kat"], lambda k: pilih_kat(k, ""), T)

        def pilih_kat(k, ringkas):
            S.update(kat=k, ai=ringkas)
            peringatan_lainnya.visible = k == "lainnya"
            try:
                peringatan_lainnya.update()
            except Exception:
                pass

        seg_layanan = ui.segmented([("panggilan", "Mekanik Panggilan", ft.Icons.BUILD), ("derek", "Derek", ft.Icons.LOCAL_SHIPPING)],
                                   S["layanan"], lambda k: ganti_layanan(k), T)

        def ke_derek():
            if S["kend"] != "mobil":
                return
            seg_layanan.selected_index = 1
            ganti_layanan("derek")

        def saat_hasil_ai(r):
            S["kat"] = r["kategori"]
            S["ai"] = f"{r['ringkasan']} {r['saran']}"
            set_kat(r["kategori"])
            peringatan_lainnya.visible = r["kategori"] == "lainnya"
            try:
                peringatan_lainnya.update()
            except Exception:
                pass
        panel_ai = PanelAI(page, T, lambda: S["kend"], saat_hasil_ai, ke_derek if S["kend"] == "mobil" else None)

        blok_panggilan = ft.Column([ui.label_seksi("Apa kendalanya?"), ui.kartu(kat), peringatan_lainnya,
                                    ui.label_seksi("Tidak yakin? Tanya AI"), panel_ai.kontrol], spacing=GAP_BLOK,
                                   visible=S["layanan"] == "panggilan")
        blok_derek = ft.Column([ui.label_seksi("Layanan derek"), ui.kartu(
            ft.Row([ui.ikon_bulat(ft.Icons.LOCAL_SHIPPING, T), ft.Text("Derek kendaraan", size=16, weight=TW.W_700, color=ui.LABEL, expand=True)],
                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text("Kendaraan Anda diderek ke bengkel mitra terdekat. Layanan ini berdiri sendiri, terpisah dari mekanik panggilan, "
                    "dan hanya tersedia untuk mobil.", size=14, color=ui.SECONDARY),
            ui.baris("Biaya jasa derek", rupiah(BIAYA_DEREK)),
            ft.Text("Ditambah ongkos panggil sesuai jarak (Rp15.000–Rp40.000). Tarif malam ×1,25 berlaku pukul 22.00–05.00.",
                    size=12, color=ui.SECONDARY))], spacing=GAP_BLOK, visible=S["layanan"] == "derek")
        blok_layanan = ft.Column([ui.label_seksi("Jenis layanan"), ft.Row([seg_layanan], alignment=ft.MainAxisAlignment.CENTER)],
                                 spacing=GAP_BLOK, visible=S["kend"] == "mobil")

        def ganti_layanan(k):
            S["layanan"] = k
            blok_panggilan.visible, blok_derek.visible = k == "panggilan", k == "derek"
            tbl_cari.text = "Cari Derek Terdekat" if k == "derek" else "Cari Mekanik Terdekat"
            page.update()

        # kendaraan: tersimpan -> kartu; belum -> pilihan cepat Motor/Mobil
        def ganti_kend(k):
            S["kend"] = k
            blok_layanan.visible = k == "mobil"
            if k == "motor" and S["layanan"] == "derek":
                seg_layanan.selected_index = 0
                ganti_layanan("panggilan")
            panel_ai.saat_derek = ke_derek if k == "mobil" else None
            page.update()
        if kv:
            blok_kend = kartu_kendaraan(lambda: pindah(0))
        else:
            blok_kend = ft.Column([
                ft.Row([ui.segmented([("motor", "Motor", ft.Icons.TWO_WHEELER), ("mobil", "Mobil", ft.Icons.DIRECTIONS_CAR)],
                                     S["kend"], ganti_kend, T)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([ft.TextButton("Simpan merek & model kendaraan saya", icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                      on_click=lambda e: kendaraan_form(lambda: pindah(0)), style=ft.ButtonStyle(color=T["aksen"]))],
                       alignment=ft.MainAxisAlignment.CENTER)], spacing=4)

        # Hero lokasi + jam sungguhan
        t_lokasi = ft.Text("", size=18, weight=TW.W_700, color="white", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        t_jam = ft.Text("", size=14, color=PUTIH70)
        t_chip = ft.Text("", size=11, weight=TW.W_600, color="white")
        tbl_perbarui = ft.TextButton("Perbarui", icon=ft.Icons.REFRESH, style=ft.ButtonStyle(color="white"))

        def isi_hero():
            l = S["loc"]
            t_lokasi.value = l["nama"] if l else "Mencari lokasi Anda…"
            t_chip.value = ("GPS aktif" if l["akurat"] else "Lokasi perkiraan") if l else "Mencari…"
            t_jam.value = lokasi.sekarang()["label"]
            tbl_cari.disabled = l is None
            tbl_perbarui.disabled = l is None
        S["hero"] = isi_hero
        isi_hero()

        def perbarui(e):
            S["loc"] = None
            isi_hero()
            page.update()
            page.run_thread(cari_lokasi)
        tbl_perbarui.on_click = perbarui
        tbl_cari.on_click = lambda e: cari_mulai()

        hero = ui.hero(
            T,
            ft.Row([ft.Icon(ft.Icons.MY_LOCATION, size=16, color=PUTIH70),
                    ft.Text("LOKASI ANDA", size=12, weight=TW.W_600, color=PUTIH70, expand=True),
                    ft.Container(padding=ft.padding.symmetric(horizontal=10, vertical=3), border_radius=12,
                                 bgcolor=ui.alpha("white", 0.22), content=t_chip)],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            t_lokasi,
            ft.Row([ft.Icon(ft.Icons.ACCESS_TIME, size=16, color=PUTIH70), ft.Container(t_jam, expand=True), tbl_perbarui],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6))

        banner = []
        if aktif:
            banner = [ft.Container(on_click=lambda e: status(aktif["id"]), content=ui.kartu(
                ft.Row([ui.ikon_bulat(ft.Icons.TWO_WHEELER if aktif["kendaraan"] == "motor" else ft.Icons.DIRECTIONS_CAR, T),
                        ft.Column([ft.Text("Pesanan sedang berjalan", size=15, weight=TW.W_600, color=ui.LABEL),
                                   ui.badge_status(aktif["status"])], spacing=4, expand=True),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ui.SEPARATOR)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER)))]

        def segarkan():
            S["loc"] = None          # lokasi & jam diambil ulang, data pesanan aktif dimuat ulang
            S["tok"] += 1
            beranda()

        tampil(ui.dengan_bar(
            ui.halaman(
                ui.header(f"Halo, {S['u']['nama'].split()[0]}", "Butuh bantuan kendaraan?",
                          ui.avatar(S["u"], T, 22, on_click=lambda e: pindah(2))),
                ui.body(
                    hero, *banner,
                    ui.label_seksi("Kendaraan"), blok_kend,
                    blok_layanan, blok_panggilan, blok_derek,
                ), bawah=ui.NAV_H + 70, segarkan=segarkan),
            tbl_cari, nav=True))

        if S["loc"] is None:
            page.run_thread(cari_lokasi)
        tok = S["tok"]
        page.run_thread(lambda: jam_berjalan(tok))

    # ── Pencarian mekanik (halaman imersif) ────────────────────────────────
    def cari_mulai():
        l = S["loc"]
        if not l:
            return snack("Lokasi belum siap, tunggu sebentar.")
        if db.pesanan_aktif_user(S["u"]["id"]):
            return snack("Anda masih punya pesanan aktif.")
        if S["layanan"] == "derek" and S["kend"] != "mobil":
            S["layanan"] = "panggilan"  # pengaman: derek hanya untuk mobil
        derek = S["layanan"] == "derek"
        S["tok"] += 1
        tok = S["tok"]
        mt = db.mitra_terdekat(l["lat"], l["lon"])
        dalam = db.antrean(l["lat"], l["lon"])  # hanya bengkel online dalam radius; tanpa cadangan ke yang lain
        ada_bengkel = bool(db.bengkel_dalam_radius(l["lat"], l["lon"]))
        langkah = ["Memastikan lokasi Anda…", f"Memindai bengkel dalam radius {MAX_JARAK_KM} km…",
                   f"Ditemukan {len(dalam)} mekanik online di sekitar Anda" if dalam else
                   ("Tidak ada bengkel yang tersedia saat ini" if ada_bengkel else "Tidak ada bengkel terdekat"),
                   "Menghitung estimasi biaya…" if dalam else "Memeriksa kembali…"]
        nav(False)
        ui.tema_gelap(page, True)
        teks = ft.AnimatedSwitcher(ft.Text(langkah[0], key="0", size=16, color=PUTIH70, text_align=ft.TextAlign.CENTER),
                                   transition=ft.AnimatedSwitcherTransition.FADE, duration=350)
        batal = dict(tombol=ui.alpha("white", 0.2), fg="white")
        tampil(ft.Container(expand=True, gradient=ft.LinearGradient(
            begin=ft.alignment.top_center, end=ft.alignment.bottom_center, colors=[ui.BLUE, ui.GELAP]),
            content=ft.Column([
                ft.Container(expand=True, alignment=ft.alignment.center, content=ft.Column([
                    ui.radar(ft.Icons.LOCAL_SHIPPING if derek else ft.Icons.SEARCH, "white", 260, True, "white", ui.BLUE),
                    ft.Text("Mencari derek terdekat" if derek else "Mencari mekanik terdekat", size=24, weight=TW.W_800, color="white"),
                    teks,
                    ft.Container(width=180, content=ft.ProgressBar(color="white", bgcolor=ui.alpha("white", 0.25),
                                                                    bar_height=4, border_radius=2)),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, spacing=16)),
                ft.Container(padding=M, content=ft.Row([ui.tombol("Batalkan", ft.Icons.CLOSE, lambda e: pindah(0), batal)])),
            ], spacing=0)))

        def proses_cari():
            for i, t in enumerate(langkah):
                if S["tok"] != tok:
                    return
                if i:
                    teks.content = ft.Text(t, key=str(i), size=16, color=PUTIH70, text_align=ft.TextAlign.CENTER)
                    try:
                        teks.update()
                    except Exception:
                        pass
                time.sleep(JEDA)
            if S["tok"] == tok:
                hasil_cari(l, dalam, mt)
        page.run_thread(proses_cari)

    def hasil_cari(l, dalam, mt):
        ui.tema_gelap(page, False)
        derek = S["layanan"] == "derek"
        if not dalam:  # tidak ada bengkel TERSEDIA: jangan alihkan ke bengkel lain
            semua = db.bengkel_dalam_radius(l["lat"], l["lon"])
            ada = bool(semua)
            tampil(ui.dengan_bar(ui.halaman(
                ui.header("Tidak ada bengkel tersedia" if ada else "Tidak ada bengkel terdekat"),
                ui.body(
                    ui.kartu(
                        ft.Row([ft.Icon(ft.Icons.STOREFRONT if ada else ft.Icons.WRONG_LOCATION, size=56, color=ui.RED)],
                                alignment=ft.MainAxisAlignment.CENTER),
                        ft.Text((f"Ada {len(semua)} bengkel di sekitar Anda, tetapi saat ini semuanya sedang tidak online."
                                 if ada else f"Tidak ada bengkel mitra dalam radius {MAX_JARAK_KM} km dari lokasi Anda."),
                                text_align=ft.TextAlign.CENTER, color=ui.SECONDARY, size=15), pad=24),
                    ui.peringatan("Pesanan tidak akan dialihkan ke bengkel lain yang berada di luar jangkauan atau sedang offline. "
                                  + ("Coba lagi beberapa saat." if ada else "Coba lagi dari lokasi lain."),
                                  "Peringatan", ft.Icons.WARNING_AMBER_ROUNDED, ui.RED, ui.RED_TINT)), nav=False),
                ui.tombol("Kembali", None, lambda e: pindah(0), T, False),
                ui.tombol("Coba Lagi", ft.Icons.REFRESH, lambda e: cari_mulai(), T)))
            nav(False)
            return
        jarak = dalam[0][0]
        h = hitung_layanan(S["kend"], S["kat"], jarak, lokasi.sekarang()["jam"], S["layanan"])
        mk = db.akun(dalam[0][1])
        kv = db.kendaraan(S["u"]["id"])
        kat_nama = NAMA_KATEGORI["derek" if derek else S["kat"]]

        def pesan(e):
            if db.pesanan_aktif_user(S["u"]["id"]):
                return snack("Anda masih punya pesanan aktif.")
            if not db.antrean(l["lat"], l["lon"]):  # bengkel baru saja offline
                snack("Bengkel di sekitar Anda baru saja offline.")
                return hasil_cari(l, [], mt)
            data = dict(nama=S["u"]["nama"], kendaraan=S["kend"], kend_label=db.label_kendaraan(kv, True), layanan=S["layanan"],
                        kategori="derek" if derek else S["kat"],
                        analisis=("Layanan derek dipilih pengguna." if derek else (S["ai"] or "Dipilih manual oleh pengguna.")),
                        lat=l["lat"], lon=l["lon"], lokasi=l["nama"], jarak=round(jarak, 1), hasil=h)
            oid = db.buat_pesanan(S["u"]["id"], data, [m[1] for m in mt if m[0] <= MAX_JARAK_KM])
            S["tolak_seen"][oid] = 0
            status(oid)

        rincian = [ui.baris("Layanan", h["jenis_layanan"]), ui.baris("Kendala", kat_nama)]
        if kv:
            rincian.append(ui.baris("Kendaraan", db.label_kendaraan(kv)))
        rincian += [ui.baris("Lokasi", l["nama"]), ui.baris("Waktu", lokasi.sekarang()["label"]), ui.pemisah()]
        if h["estimasi"]:
            rincian += [ui.baris("Biaya jasa", rupiah(h["biaya_jasa"])), ui.baris("Ongkos panggil", rupiah(h["ongkos_panggil"])),
                        ui.baris("Tarif malam ×1,25", "Berlaku" if h["tarif_malam"] else "Tidak"), ui.pemisah(),
                        ui.baris("Total", rupiah(h["biaya_total"]), True, ui.BLUE)]
        else:
            rincian.append(ui.baris("Harga", "Disepakati via chat", True, ui.ORANGE))

        tampil(ui.dengan_bar(
            ui.halaman(
                ui.header("Mekanik Ditemukan", f"{len(dalam)} mekanik tersedia dalam radius {MAX_JARAK_KM} km"),
                ui.body(
                    ui.kartu(ft.Row([
                        ui.avatar(mk, T, 26),
                        ft.Column([ft.Text(mk["nama"], size=17, weight=TW.W_700, color=ui.LABEL),
                                   ui.rating_ringkas(db.rating_mekanik(mk["id"])),
                                   ft.Text(f"{jarak:.1f} km dari Anda · tiba ± {lokasi.eta_menit(jarak)} menit", size=13, color=ui.SECONDARY),
                                   *([ft.Text(mk["alamat"], size=12, color=ui.SECONDARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)]
                                     if mk.get("alamat") else [])],
                                  spacing=2, expand=True),
                        ui.badge("Online" if dalam[0][1] in db.id_online() else "Terdekat", ui.GREEN, ui.GREEN_TINT)],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)),
                    *([ui.peringatan(TEKS_LAINNYA, "Estimasi harga tidak ditampilkan", ft.Icons.INFO_OUTLINE)] if not h["estimasi"] else []),
                    ui.label_seksi("Rincian"),
                    ui.kartu(*rincian),
                ), nav=False),
            ui.tombol("Kembali", None, lambda e: pindah(0), T, False),
            ui.tombol("Pesan Sekarang", ft.Icons.CHECK_CIRCLE, pesan, T)))
        nav(False)

    # ── Chat dengan mekanik ────────────────────────────────────────────────
    def buka_chat(oid):
        S["tok"] += 1
        tok = S["tok"]
        p = db.pesanan(oid)
        mk = db.akun(p["mekanik_id"]) if p and p["mekanik_id"] else None
        if not mk:
            return status(oid)
        nav(False)
        tanpa_harga = p["hasil"].get("estimasi") is False and not p["hasil"].get("harga_akhir")
        banner = ui.peringatan("Harga belum ditentukan. Sepakati harga dengan montir lewat chat ini.", None, ft.Icons.PAYMENTS_OUTLINED) \
            if tanpa_harga else None
        c = Chat(page, T, S["u"]["id"], oid, mk["nama"], f"Montir · {NAMA_KATEGORI.get(p['kategori'], p['kategori'])}",
                 lambda: status(oid), lawan=mk, banner=banner, telp=mk.get("telp"))
        S["chat"] = c
        tampil(c.kontrol)
        page.run_thread(lambda: c.polling(lambda: S["tok"] == tok))

    # ── Status pesanan (auto-refresh) ──────────────────────────────────────
    def status(oid):
        S["tok"] += 1
        tok = S["tok"]
        ui.tema_gelap(page, False)
        nav(True)
        p = db.pesanan(oid)
        if not p:
            return pindah(1)
        uid = S["u"]["id"]
        st = p["status"]
        mencari = st == "Mencari mekanik"
        ikon = {"Mencari mekanik": ft.Icons.RADAR, "Mekanik menuju lokasi": ft.Icons.TWO_WHEELER,
                "Selesai": ft.Icons.CHECK_CIRCLE, "Dibatalkan": ft.Icons.CANCEL, "Ditolak": ft.Icons.BLOCK}.get(st, ft.Icons.ERROR_OUTLINE)
        warna = ui.STATUS_WARNA.get(st, (ui.SECONDARY, None))[0]
        mk = db.akun(p["mekanik_id"]) if p["mekanik_id"] else None
        tawar = db.penawaran(p) if mencari else None  # mitra online yang sedang ditawari (berubah otomatis)
        ditawari = db.akun(tawar) if tawar else None
        penolak = [a["nama"] for a in (db.akun(i) for i in p["ditolak"]) if a]
        belum = db.chat_belum_dibaca(oid, uid)
        info = {"Mencari mekanik": f"Menawarkan pesanan ke {ditawari['nama']}…" if ditawari else "Menunggu mekanik online…",
                "Mekanik menuju lokasi": f"{mk['nama']} sedang menuju lokasi Anda" if mk else "",
                "Selesai": "Terima kasih sudah memakai OtoFix!", "Dibatalkan": "Pesanan ini telah dibatalkan.",
                "Ditolak": "Pesanan Anda ditolak oleh semua bengkel terdekat.",
                "Tidak ada bengkel terdekat": "Tidak ada bengkel terdekat.",
                "Tidak ada mekanik tersedia": "Tidak ada bengkel terdekat."}.get(st, "")

        # pemberitahuan bila ada mekanik yang baru menolak
        lihat = S["tolak_seen"].setdefault(oid, len(p["ditolak"]))
        if len(p["ditolak"]) > lihat:
            S["tolak_seen"][oid] = len(p["ditolak"])
            snack(f"{penolak[-1]} menolak pesanan Anda." + (" Mencari mekanik lain…" if mencari else ""))

        def batalkan():
            db.batal(oid)
            snack("Pesanan dibatalkan")
            status(oid)

        kembali = S["tab"] if S["tab"] in (0, 1) else 0
        h = p["hasil"]
        rows = [ui.baris("Layanan", h["jenis_layanan"]), ui.baris("Kendala", NAMA_KATEGORI.get(p["kategori"], p["kategori"]))]
        if p.get("kend_label"):
            rows.append(ui.baris("Kendaraan", p["kend_label"]))
        rows += [ui.baris("Lokasi", p.get("lokasi") or "-"), ui.baris("Waktu", p["waktu"]), ui.pemisah(),
                 ui.baris("Total" if biaya_efektif(h) else "Harga", teks_biaya(h), True, ui.BLUE if biaya_efektif(h) else ui.ORANGE)]
        kartu_tolak = []
        if penolak and st in ("Mencari mekanik", "Ditolak"):
            kartu_tolak = [ui.peringatan(
                f"Pesanan Anda ditolak oleh {', '.join(penolak)}." + (" Sedang mencari mekanik lain…" if mencari else ""),
                "Pesanan ditolak", ft.Icons.CANCEL, ui.RED, ui.RED_TINT)]
        kartu_mk = []
        if mk:
            kartu_mk = [ui.kartu(ft.Row([
                ui.avatar(mk, T, 26),
                ft.Column([ft.Text(mk["nama"], size=17, weight=TW.W_700, color=ui.LABEL),
                           ft.Text(mk["telp"] or "Nomor belum diisi", size=13, color=ui.SECONDARY),
                           ui.rating_ringkas(db.rating_mekanik(mk["id"]))], spacing=2, expand=True),
                ui.badge("Mekanik Anda", ui.BLUE, ui.BLUE_TINT)], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12))]
        lacak = None
        if mk and st == "Mekanik menuju lokasi":   # pelacakan langsung posisi mekanik
            lacak = page.lacak = PetaLacak(page, T, p["lat"], p["lon"], mk["nama"], oid, uid)
        tombol_chat = []
        if mk and (st == "Mekanik menuju lokasi" or (st == "Selesai" and db.chat_pesanan(oid, uid))):
            tombol_chat = [ft.Row([ui.tombol(("Chat dengan mekanik" if st != "Selesai" else "Lihat riwayat chat")
                                             + (f" ({belum})" if belum else ""), ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                                             lambda e: buka_chat(oid), T)])]
        peringatan_harga = [ui.peringatan(
            "Harga belum ditentukan. Sepakati harga dengan montir lewat chat.", None, ft.Icons.PAYMENTS_OUTLINED)] \
            if (h.get("estimasi") is False and not h.get("harga_akhir") and st in ("Mencari mekanik", "Mekanik menuju lokasi")) else []
        ulasan = ui.daftar_ulasan(db.rating_mekanik(mk["id"]), "Ulasan untuk mekanik ini") if mk else None
        kartu_ulasan = [ui.kartu(ulasan)] if ulasan else []
        kartu_rating = []
        if mk and st == "Selesai":
            sudah = db.rating_oleh(oid, uid)

            def kirim_rating(bintang, komentar):
                ok, msg = db.beri_rating(oid, uid, bintang, komentar)
                snack("Terima kasih atas penilaian Anda" if ok else msg)
                status(oid)
            kartu_rating = [ui.kartu(ui.rating_diberikan(sudah, "Rating Anda untuk mekanik") if sudah else
                                     ui.form_rating(T, kirim_rating, f"Beri rating untuk {mk['nama']}"))]
        aksi = [ft.Row([ui.tombol("Batalkan Pesanan", ft.Icons.CLOSE, lambda e: ui.konfirmasi(
            page, "Batalkan pesanan?", "Mekanik tidak akan diberi tahu lagi.", "Batalkan", batalkan, True, "Tidak"),
            T, destruktif=True)])] if st in db.AKTIF else []
        if st in ("Ditolak", "Tidak ada bengkel terdekat"):
            aksi = [ft.Row([ui.tombol("Cari Lagi", ft.Icons.REFRESH, lambda e: pindah(0), T)])]

        tampil(ui.halaman(
            ui.header("Status Pesanan"),
            ui.body(
                ft.Container(alignment=ft.alignment.center, padding=ft.padding.symmetric(vertical=8), content=ui.radar(
                    ikon, warna, 220 if mencari else 140, mencari)),
                ft.Row([ui.badge_status(st)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text(info, color=ui.SECONDARY, text_align=ft.TextAlign.CENTER, size=15),
                *([ft.Row([ui.rating_ringkas(db.rating_mekanik(ditawari["id"]))], alignment=ft.MainAxisAlignment.CENTER)]
                  if ditawari else []),
                *([ui.peringatan("Belum ada bengkel online di sekitar Anda. Pesanan menunggu sampai ada yang tersedia; "
                                 "Anda juga bisa membatalkannya.", "Menunggu bengkel", ft.Icons.STOREFRONT)]
                  if mencari and not ditawari else []),
                *kartu_tolak, *peringatan_harga, *([lacak.kontrol] if lacak else []), *kartu_mk, *tombol_chat, *kartu_rating, *kartu_ulasan, ui.kartu(*rows), *aksi,
                ft.Row([ui.tombol("Kembali", ft.Icons.ARROW_BACK_IOS_NEW, lambda e: pindah(kembali), T, False)]),
            )))

        def pantau():
            while S["tok"] == tok and st in db.AKTIF:
                time.sleep(2)
                if S["tok"] != tok:
                    return
                if lacak:
                    lacak.perbarui()   # posisi mekanik bergerak secara langsung tanpa membangun ulang layar
                baru = db.pesanan(oid)
                if baru and (baru["status"] != st or baru["ditolak"] != p["ditolak"]
                             or (mencari and db.penawaran(baru) != tawar)
                             or db.chat_belum_dibaca(oid, uid) != belum):
                    status(oid)
                    return
        page.run_thread(pantau)

    # ── Riwayat pesanan ────────────────────────────────────────────────────
    def riwayat():
        ps = db.pesanan_user(S["u"]["id"])

        def item(p):
            return ft.Container(on_click=lambda e, pid=p["id"]: status(pid), border_radius=16, content=ui.kartu(
                ft.Row([ui.ikon_bulat(ui.I(IKON.get(p["kategori"], "BUILD")), T),
                        ft.Column([ft.Text(NAMA_KATEGORI.get(p["kategori"], p["kategori"]), weight=TW.W_600, size=15, color=ui.LABEL),
                                   ft.Text(p["waktu"], size=13, color=ui.SECONDARY)], spacing=2, expand=True),
                        ft.Column([ft.Text(teks_biaya(p["hasil"]), weight=TW.W_600, size=15, color=ui.LABEL),
                                   ui.badge_status(p["status"]),
                                   *([ft.Text("Belum dinilai", size=11, color=ui.ORANGE)]
                                     if p["status"] == "Selesai" and not db.rating_oleh(p["id"], S["u"]["id"]) else [])],
                                  spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)))

        tampil(ui.halaman(
            ui.header("Pesanan", "Riwayat dan status pesanan Anda"),
            ui.body(*([item(p) for p in ps] or
                      [ui.kosong(ft.Icons.RECEIPT_LONG_OUTLINED, "Belum ada pesanan", "Pesanan Anda akan muncul di sini.")])),
            segarkan=riwayat))

    # ── Auto-login ─────────────────────────────────────────────────────────
    uid = page.client_storage.get(KEY)
    row = db.akun(uid) if uid else None
    masuk(row) if row and row["peran"] == "pengguna" else login()


GAP_BLOK = 12

if __name__ == "__main__":
    ft.app(target=main)

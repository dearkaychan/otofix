"""OtoFix Mitra - aplikasi untuk mekanik/bengkel mitra (UI gaya iOS)."""
import re
import time
import flet as ft
import db
import ui
import lokasi
from peta import peta_lipat, PemilihLokasi
from chat_ui import Chat
from engine import NAMA_KATEGORI as KATEGORI, rupiah, biaya_efektif, MAX_JARAK_KM
from ui import TW, MITRA as T

KEY = "otofix_mitra"
KEY_TEMA = KEY + "_tema"
TAGLINE = "Terima pesanan, tiba lebih siap."
PUTIH70 = ui.alpha("white", 0.8)


def harga_pendek(h):
    n = biaya_efektif(h)
    return rupiah(n) if n else "Via chat"


def main(page: ft.Page):
    db.init()
    ui.setup(page, "OtoFix Mitra", page.client_storage.get(KEY_TEMA))
    host = ui.layar()
    S = {"u": None, "tab": 0, "sig": None, "tok": 0, "sesi": 0}
    pelacak = lokasi.Pelacak(page)
    bar_nav = page.nav = ui.NavFlotan(T, lambda i: pindah(i))
    page.add(ft.SafeArea(ft.Stack([host, bar_nav.kontrol], expand=True), expand=True))

    def tampil(c):
        ui.tampil(page, host, c)

    def snack(t):
        ui.snack(page, t)

    def login():
        tampil(ui.auth(page, "mitra", "OtoFix Mitra", TAGLINE, T, masuk, bengkel=PemilihLokasi(page, pelacak)))

    def masuk(row):
        S["u"] = row
        page.client_storage.set(KEY, row["id"])
        bar_nav.atur([
            (ft.Icons.RADAR_OUTLINED, ft.Icons.RADAR, "Radar"),
            (ft.Icons.PAID_OUTLINED, ft.Icons.PAID, "Pendapatan"),
            (ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON, "Profil"),
        ])
        bar_nav.tampil(True)
        S["sesi"] += 1
        db.heartbeat(row["id"])  # langsung online: pesanan baru diprioritaskan ke mitra yang sedang membuka aplikasi
        sesi = S["sesi"]
        page.run_thread(lambda: sinyal_online(sesi))
        pindah(0)

    def bagikan_sekali():
        """Membagikan posisi mekanik ke pemesan selama ada pesanan aktif. Memakai GPS perangkat bila ada;
        bila GPS tidak tersedia (mis. laptop) posisi disimulasikan bergerak dari bengkel menuju pemesan."""
        if not S["u"]:
            return
        mid = S["u"]["id"]
        tugas = db.tugas(mid)
        if not tugas:
            S["sim"] = None
            db.hapus_live(mid)
            return
        p = tugas[0]
        if S.get("gps_ok") is not False:
            lat, lon, ok = pelacak.posisi(timeout=4 if S.get("gps_ok") is None else 3)
            S["gps_ok"] = ok
            if ok:
                return db.set_live(mid, lat, lon)
        sim = S.get("sim")
        if not sim or sim["pid"] != p["id"]:
            awal = db.pos_akun(mid)
            sim = S["sim"] = dict(pid=p["id"], lat=awal[0], lon=awal[1],
                                  langkah=max(lokasi_jarak(awal, p) * 0.12, 0.05))  # tiba dalam ~9 langkah
        sim["lat"], sim["lon"] = lokasi.geser(sim["lat"], sim["lon"], p["lat"], p["lon"], sim["langkah"])
        db.set_live(mid, sim["lat"], sim["lon"])
    page.bagikan_lokasi = bagikan_sekali  # kait untuk pengujian

    def sinyal_online(sesi):
        """Tiap 3 detik selama aplikasi terbuka & akun masuk: tanda 'online' + bagikan posisi bila ada pesanan aktif."""
        while S["sesi"] == sesi and S["u"]:
            time.sleep(3)
            if S["sesi"] == sesi and S["u"]:
                db.heartbeat(S["u"]["id"])
                try:
                    bagikan_sekali()
                except Exception:
                    pass

    def keluar():
        db.offline(S["u"]["id"])
        S.update(u=None, tok=S["tok"] + 1, sesi=S["sesi"] + 1)
        page.client_storage.remove(KEY)
        bar_nav.tampil(False)
        login()

    def pindah(i):
        S["tok"] += 1
        S["tab"] = i
        bar_nav.tampil(True)  # chat menyembunyikan tab bar; setiap pindah tab harus memunculkannya lagi
        bar_nav.pilih(i)
        if i == 0:
            radar()
            tok = S["tok"]
            page.run_thread(lambda: pantau(tok))
        elif i == 1:
            pendapatan()
        else:
            profil()

    def ganti_tema(mode):
        page.client_storage.set(KEY_TEMA, mode)
        ui.terapkan_tema(mode, page)
        bar_nav.tema_ulang()
        profil()

    def refresh():
        {1: pendapatan, 2: profil}.get(S["tab"], radar)()

    def buka_rating(pid):
        """Mekanik menilai pelanggan setelah pekerjaan selesai (rating ini hanya terlihat oleh sesama mekanik)."""
        p = db.pesanan(pid)
        if not p or p["status"] != "Selesai":
            return
        if db.rating_oleh(pid, S["u"]["id"]):
            return snack("Pelanggan ini sudah Anda nilai.")
        sheet = ft.BottomSheet(
            ft.Container(padding=ft.padding.only(left=20, right=20, top=8, bottom=24), bgcolor=ui.SURFACE,
                         content=ft.Column([ui.form_rating(T, lambda b, k: kirim(b, k), f"Nilai pelanggan: {p['nama']}")],
                                           tight=True, scroll=ft.ScrollMode.AUTO)),
            show_drag_handle=True, bgcolor=ui.SURFACE, is_scroll_controlled=True)

        def kirim(bintang, komentar):
            ok, msg = db.beri_rating(pid, S["u"]["id"], bintang, komentar)
            page.close(sheet)
            snack("Rating pelanggan terkirim" if ok else msg)
            refresh()
        page.open(sheet)

    def profil():
        def segarkan():
            S["u"] = db.akun(S["u"]["id"])
            profil()
        row = S["u"]
        ada = db.lokasi_diatur(row["id"])
        lat, lon = db.pos_akun(row["id"])
        pk = PemilihLokasi(page, pelacak, lat if ada else None, lon if ada else None, row.get("alamat") or "", pusat=(lat, lon))

        def simpan_lokasi(e):
            if not pk.siap():
                return snack("Pilih lokasi bengkel dulu: ketuk peta atau pakai lokasi saya.")
            d = pk.data()
            db.set_lokasi(row["id"], d["lat"], d["lon"], d["alamat"])
            S["u"] = db.akun(row["id"])
            snack("Lokasi bengkel disimpan")
            profil()

        lokasi_card = [ui.label_seksi("Lokasi bengkel"), ui.kartu(
            ft.Text("Pesanan hanya ditawarkan jika pemesan berada dalam radius "
                    f"{MAX_JARAK_KM} km dari lokasi ini." + ("" if ada else " Lokasi belum diatur — saat ini memakai lokasi simulasi."),
                    size=13, color=ui.SECONDARY),
            pk.kontrol, ft.Row([ui.tombol("Simpan Lokasi", ft.Icons.CHECK, simpan_lokasi, T)]))]
        ring = db.rating_mekanik(row["id"])
        ulasan = ui.daftar_ulasan(ring, "Ulasan terbaru dari pengguna")
        rating_card = [ui.label_seksi("Rating Anda"), ui.kartu(
            ft.Row([ft.Text(f"{ring['rata']:.1f}".replace(".", ",") if ring["jumlah"] else "–", size=36, weight=TW.W_800, color=ui.LABEL),
                    ft.Column([ui.bintang_baris(ring["rata"], 20),
                               ft.Text(f"{ring['jumlah']} ulasan dari pengguna" if ring["jumlah"] else "Belum ada ulasan",
                                       size=13, color=ui.SECONDARY)], spacing=2)],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            *([ulasan] if ulasan else []))]
        tampil(ui.profil(page, row, T, simpan, keluar, "Mitra bengkel OtoFix", segarkan, ekstra=[*rating_card, *lokasi_card],
                         mode_tema=ui.MODE, saat_tema=ganti_tema))

    def simpan(nama, telp):
        db.ubah_profil(S["u"]["id"], nama, telp)
        S["u"] = db.akun(S["u"]["id"])
        snack("Profil tersimpan")
        profil()

    # ── Radar real-time ────────────────────────────────────────────────────
    def sig():
        mid = S["u"]["id"]
        return str([(p["id"], p["status"], db.chat_belum_dibaca(p["id"], mid)) for p in db.radar(mid) + db.tugas(mid)])

    def pantau(tok):
        while S["tok"] == tok and S["u"]:
            time.sleep(2)
            if S["tok"] == tok and S["u"] and sig() != S["sig"]:
                radar()

    def radar():
        mid = S["u"]["id"]
        S["sig"] = sig()
        pos_saya = db.pos_akun(mid)

        def titik_live():
            return ui.denyut(ft.Container(width=10, height=10, border_radius=5, bgcolor=ui.GREEN), 1, 0.3, besar=1.8, ms=900)

        def terima(pid):
            snack("Pesanan diterima. Segera menuju lokasi." if db.ubah_status(pid, "Mekanik menuju lokasi", mid)
                  else "Pesanan sudah tidak tersedia.")
            radar()

        def tolak(pid):
            db.tolak(pid, mid)
            snack("Pesanan ditolak, diteruskan ke mekanik lain.")
            radar()

        def selesai(pid):
            p = db.pesanan(pid)

            def lanjut():
                db.ubah_status(pid, "Selesai")
                snack("Pekerjaan selesai. Pendapatan tercatat.")
                radar()
                buka_rating(pid)

            def simpan_harga(v):
                angka = re.sub(r"\D", "", v or "")
                if angka and not db.set_harga_akhir(pid, angka):
                    snack("Harga tidak valid, dilewati.")
                lanjut()
            if p and p["hasil"].get("estimasi") is False and not p["hasil"].get("harga_akhir"):
                # kategori 'Lainnya': harga tidak punya estimasi, mintalah harga hasil chat agar pendapatan tercatat
                ui.input_dialog(page, "Harga yang disepakati", "Masukkan harga hasil kesepakatan dengan pelanggan (boleh dilewati).",
                                "Harga (Rp)", simpan_harga, "Simpan & Selesai", "Lewati", lanjut, angka=True)
            else:
                lanjut()

        def kartu_pesanan(p, baru):
            h = p["hasil"]
            pemesan = db.akun(p["user_id"]) or {"nama": p["nama"]}
            rat_pel = db.rating_pelanggan(p["user_id"])  # hanya terlihat di aplikasi mitra
            if baru:
                aksi = ft.Row([
                    ft.OutlinedButton("Tolak", icon=ft.Icons.CLOSE, height=48, expand=True,
                                      on_click=lambda e, pid=p["id"]: tolak(pid),
                                      style=ft.ButtonStyle(color=ui.RED, side=ft.BorderSide(1.2, ui.alpha(ui.RED, 0.45)),
                                                           shape=ft.RoundedRectangleBorder(radius=12))),
                    ui.tombol("Terima", ft.Icons.CHECK, lambda e, pid=p["id"]: terima(pid), T),
                ], spacing=10)
            else:
                belum = db.chat_belum_dibaca(p["id"], mid)
                aksi = ft.Column([
                    ft.Row([ui.tombol("Chat dengan pemesan" + (f" ({belum})" if belum else ""), ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                                      lambda e, pid=p["id"]: buka_chat(pid), T, False)]),
                    ft.Row([ui.tombol("Tandai Selesai", ft.Icons.DONE_ALL, lambda e, pid=p["id"]: ui.konfirmasi(
                        page, "Pekerjaan sudah selesai?", "Status pesanan akan menjadi Selesai.", "Selesai",
                        lambda: selesai(pid)), T)])], spacing=8)
            jarak_saya = lokasi_jarak(pos_saya, p)
            return ui.kartu(
                ft.Row([ui.avatar(pemesan, T, 22),
                        ft.Column([ft.Text(p["nama"], weight=TW.W_600, size=16, color=ui.LABEL),
                                   ft.Text(f"{p.get('kend_label') or p['kendaraan'].title()} · {p['waktu']}", size=13, color=ui.SECONDARY,
                                           max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                                  spacing=2, expand=True),
                        ft.Text(harga_pendek(h), size=17, weight=TW.W_700, color=ui.GREEN if biaya_efektif(h) else ui.ORANGE)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                ft.Container(padding=ft.padding.symmetric(horizontal=12, vertical=10), border_radius=12, bgcolor=ui.FILL,
                             content=ft.Column([
                                 ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINE, size=16, color=ui.SECONDARY),
                                         ft.Text("Rating pelanggan", size=13, color=ui.SECONDARY, expand=True),
                                         ui.rating_ringkas(rat_pel)], spacing=6),
                                 *([ft.Text("“" + rat_pel["ulasan"][0]["komentar"] + "”", size=13, color=ui.LABEL, italic=True)]
                                   if rat_pel["ulasan"] else [])], spacing=6)),
                peta_lipat(page, p["lat"], p["lon"], pos_saya),
                ft.Row([ft.Icon(ft.Icons.PLACE_OUTLINED, size=18, color=ui.SECONDARY),
                        ft.Text(p.get("lokasi") or f"{p['lat']:.4f}, {p['lon']:.4f}", size=14, color=ui.LABEL, expand=True,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{jarak_saya:.1f} km", size=13, weight=TW.W_600, color=ui.GREEN)], spacing=8),
                ft.Row([ft.Icon(ft.Icons.BUILD_CIRCLE_OUTLINED, size=18, color=ui.SECONDARY),
                        ft.Text(f"{KATEGORI[p['kategori']]} · {h['jenis_layanan']}", size=14, color=ui.LABEL, expand=True)], spacing=8),
                ft.Container(padding=12, border_radius=12, bgcolor=T["tint"], content=ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=ui.GREEN),
                    ft.Text(p["analisis"], size=13, color=ui.LABEL, expand=True)], spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START)),
                *([] if baru else [ft.Container(padding=ft.padding.symmetric(horizontal=12, vertical=8), border_radius=12, bgcolor=T["tint"],
                                                content=ft.Row([titik_live(), ft.Text("Posisi Anda dibagikan langsung ke pemesan", size=13,
                                                                                      color=ui.LABEL, expand=True)], spacing=10,
                                                               vertical_alignment=ft.CrossAxisAlignment.CENTER))]),
                aksi)

        masuk_, aktif = db.radar(mid), db.tugas(mid)
        riwayat_ = db.riwayat_mitra(mid)

        titik = ft.Container(width=10, height=10, border_radius=5, bgcolor="white")
        ui.denyut(titik, 1, 0.3, besar=1.8, ms=900)
        stat = lambda angka, ket: ft.Container(expand=True, padding=ft.padding.symmetric(vertical=10), border_radius=14,
                                               bgcolor=ui.alpha("white", 0.18), content=ft.Column([
            ft.Text(angka, size=20, weight=TW.W_800, color="white"), ft.Text(ket, size=12, color=PUTIH70)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0))
        hero = ui.hero(
            T,
            ft.Row([titik, ft.Text("ONLINE · menerima pesanan", size=12, weight=TW.W_600, color=PUTIH70)], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(f"Radius {MAX_JARAK_KM} km dari bengkel Anda", size=17, weight=TW.W_700, color="white"),
            ft.Row([stat(str(len(masuk_)), "Baru"), stat(str(len(aktif)), "Dikerjakan"), stat(f"{len(riwayat_)}", "Selesai")],
                   spacing=8))

        kosong_baru = ui.kosong(ft.Icons.RADAR, "Menunggu permintaan…", "Permintaan baru muncul otomatis.")
        kosong_aktif = ui.kosong(ft.Icons.ENGINEERING, "Belum ada tugas aktif", "Terima pesanan untuk memulai.")
        cnt = lambda n, w: ui.badge(str(n), w if n else ui.SECONDARY, T["tint"] if n else ui.FILL)

        tampil(ui.halaman(
            ui.header(f"Halo, {S['u']['nama'].split()[0]}", "Radar pesanan masuk",
                      ui.avatar(S["u"], T, 22, on_click=lambda e: pindah(2))),
            ui.body(hero, *([ui.kartu(ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ui.ORANGE, size=22),
                ft.Column([ft.Text("Lokasi bengkel belum diatur", size=15, weight=TW.W_600, color=ui.LABEL),
                           ft.Text("Pesanan dihitung dari lokasi simulasi. Atur lokasi bengkel agar jarak akurat.", size=13, color=ui.SECONDARY)],
                          spacing=2, expand=True),
                ft.TextButton("Atur", on_click=lambda e: pindah(2), style=ft.ButtonStyle(color=ui.GREEN))],
                vertical_alignment=ft.CrossAxisAlignment.CENTER))] if not db.lokasi_diatur(mid) else []), bawah=0),
            ui.label_seksi("Permintaan baru", cnt(len(masuk_), ui.ORANGE)),
            ui.body(*([kartu_pesanan(p, True) for p in masuk_] or [kosong_baru]), bawah=0),
            ui.label_seksi("Sedang dikerjakan", cnt(len(aktif), ui.GREEN)),
            ui.body(*([kartu_pesanan(p, False) for p in aktif] or [kosong_aktif])),
            segarkan=lambda: (db.heartbeat(mid), radar()),
        ))

    def buka_chat(pid):
        S["tok"] += 1
        tok = S["tok"]
        p = db.pesanan(pid)
        if not p:
            return pindah(0)
        bar_nav.tampil(False)
        tanpa_harga = p["hasil"].get("estimasi") is False and not p["hasil"].get("harga_akhir")
        banner = ui.peringatan("Kategori Lainnya tanpa estimasi: sepakati harga dengan pelanggan lewat chat ini.", None,
                               ft.Icons.PAYMENTS_OUTLINED) if tanpa_harga else None
        pemesan = db.akun(p["user_id"])
        c = Chat(page, T, S["u"]["id"], pid, p["nama"], f"Pemesan · {KATEGORI.get(p['kategori'], p['kategori'])}",
                 lambda: pindah(0), lawan=pemesan, banner=banner, telp=(pemesan or {}).get("telp"))
        tampil(c.kontrol)
        page.run_thread(lambda: c.polling(lambda: S["tok"] == tok))

    def lokasi_jarak(pos, p):
        from engine import jarak_haversine
        return jarak_haversine(pos[0], pos[1], p["lat"], p["lon"])

    # ── Pendapatan & riwayat ───────────────────────────────────────────────
    def pendapatan():
        ps = db.riwayat_mitra(S["u"]["id"])
        total = sum(db.harga(p) or 0 for p in ps)

        def item(p):
            r = db.rating_oleh(p["id"], S["u"]["id"])
            aksi = (ft.Row([ft.Icon(ft.Icons.STAR_ROUNDED, size=16, color=ui.STAR),
                            ft.Text(f"{r['bintang']} untuk pelanggan", size=12, color=ui.SECONDARY)], spacing=3, tight=True)
                    if r else ft.TextButton("Beri rating", icon=ft.Icons.STAR_BORDER_ROUNDED,
                                            on_click=lambda e, pid=p["id"]: buka_rating(pid),
                                            style=ft.ButtonStyle(color=ui.ORANGE, padding=0)))
            return ui.kartu(ft.Row([
                ft.Column([ft.Text(KATEGORI[p["kategori"]], weight=TW.W_600, size=15, color=ui.LABEL),
                           ft.Text(f"{p['nama']} · {p['waktu']}", size=13, color=ui.SECONDARY)], spacing=2, expand=True),
                ft.Column([ft.Text(harga_pendek(p["hasil"]), weight=TW.W_600, size=15, color=ui.GREEN), aksi],
                          spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER))

        tampil(ui.halaman(
            ui.header("Pendapatan", "Ringkasan pekerjaan selesai"),
            ui.body(
                ui.hero(T, ft.Text("TOTAL PENDAPATAN", size=12, weight=TW.W_600, color=PUTIH70),
                        ft.Text(rupiah(total), size=32, weight=TW.W_800, color="white"),
                        ft.Text(f"{len(ps)} pekerjaan selesai", size=13, color=PUTIH70),
                        ui.rating_ringkas(db.rating_mekanik(S["u"]["id"]), 14, "white", PUTIH70, "Belum ada rating dari pengguna")),
                ui.label_seksi("Riwayat"),
                *([item(p) for p in ps] or [ui.kosong(ft.Icons.PAID_OUTLINED, "Belum ada pekerjaan selesai",
                                                      "Pekerjaan yang selesai tampil di sini.")])),
            segarkan=pendapatan))

    # ── Auto-login ─────────────────────────────────────────────────────────
    uid = page.client_storage.get(KEY)
    row = db.akun(uid) if uid else None
    masuk(row) if row and row["peran"] == "mitra" else login()


if __name__ == "__main__":
    ft.app(target=main)

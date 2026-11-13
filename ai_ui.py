"""Panel 'Asisten AI' dengan animasi: chip contoh keluhan, loading bertahap, hasil muncul dengan bar keyakinan."""
import threading, time
import flet as ft
import ai
import ui
from engine import KATEGORI
from ui import TW

MIN_DETIK = 2.4      # minimal lama animasi 'berpikir' agar terasa natural (tes mengubahnya ke 0)
JEDA_LANGKAH = 0.9
LANGKAH = ["Membaca keluhan Anda…", "Mencocokkan dengan gejala kerusakan…", "Menyusun saran untuk montir…"]
CONTOH = ["Ban belakang kempes", "Mesin mati mendadak", "Starter cuma klik-klik", "Rem terasa blong", "Bensin habis"]
LEBAR_BAR = 220


class PanelAI:
    def __init__(self, page, tema, ambil_kendaraan, saat_hasil, saat_derek=None):
        self.page, self.tema, self.ambil_kendaraan, self.saat_hasil, self.saat_derek = page, tema, ambil_kendaraan, saat_hasil, saat_derek
        self.hasil, self.sibuk = None, False
        aksen = tema["aksen"]
        self.keluhan = ui.kolom("Ceritakan gejalanya", multiline=True, min_lines=2, max_lines=4,
                                hint_text="Contoh: mesin kletek lalu mati saat digas", on_change=self._ketik)
        self.tombol = ft.FilledButton("Analisis dengan AI", icon=ft.Icons.AUTO_AWESOME, height=46, expand=True, on_click=self.mulai,
                                      style=ft.ButtonStyle(bgcolor=aksen, color=tema.get("fg", "white"),
                                                           shape=ft.RoundedRectangleBorder(radius=12),
                                                           text_style=ft.TextStyle(size=15, weight=TW.W_600)))
        chips = [ft.Container(padding=ft.padding.symmetric(horizontal=12, vertical=7), border_radius=18, bgcolor=ui.FILL, ink=True,
                              on_click=lambda e, t=c: self._isi(t),
                              content=ft.Text(c, size=13, color=ui.LABEL)) for c in CONTOH]
        self.chips = ft.Row(chips, wrap=True, spacing=8, run_spacing=8)
        # loading
        self.spark = ui.denyut(ft.Container(width=44, height=44, border_radius=22, alignment=ft.alignment.center,
                                            gradient=ft.LinearGradient(colors=list(tema["grad"])),
                                            content=ft.Icon(ft.Icons.AUTO_AWESOME, color="white", size=24)), 1, 1, besar=1.18, ms=700)
        self.langkah = ft.AnimatedSwitcher(ft.Text(LANGKAH[0], key="0", size=15, weight=TW.W_600, color=ui.LABEL),
                                           transition=ft.AnimatedSwitcherTransition.FADE, duration=300)
        garis = [ui.denyut(ft.Container(height=10, border_radius=5, bgcolor=ui.FILL, width=w), 0.45, 1.0, besar=1.0, ms=800, tunda=0.2 * i)
                 for i, w in enumerate((260, 200, 140))]
        self.loading = ft.Container(visible=False, padding=ft.padding.symmetric(vertical=6), content=ft.Column([
            ft.Row([self.spark, ft.Column([ft.Text("AI sedang menganalisis", size=12, color=ui.SECONDARY), self.langkah], spacing=1, expand=True)],
                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER), *garis], spacing=8))
        # hasil
        self.hasil_box = ft.Container(visible=False, opacity=0, offset=ft.Offset(0, 0.06), animate_opacity=500,
                                      animate_offset=ft.Animation(550, ft.AnimationCurve.EASE_OUT_CUBIC))
        self.kontrol = ui.kartu(
            ft.Row([ft.Container(width=36, height=36, border_radius=18, alignment=ft.alignment.center,
                                 gradient=ft.LinearGradient(colors=list(tema["grad"])),
                                 content=ft.Icon(ft.Icons.AUTO_AWESOME, color="white", size=20)),
                    ft.Column([ft.Text("Asisten AI", size=16, weight=TW.W_700, color=ui.LABEL),
                               ft.Text("Ceritakan gejalanya, AI bantu menentukan kerusakan.", size=12, color=ui.SECONDARY)],
                              spacing=1, expand=True)], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.chips, self.keluhan, ft.Row([self.tombol]), self.loading, self.hasil_box)

    # ── interaksi ──
    def _isi(self, teks):
        self.keluhan.value, self.keluhan.error_text = teks, None
        self._upd(self.keluhan)

    def _ketik(self, e):
        if self.keluhan.error_text:
            self.keluhan.error_text = None
            self._upd(self.keluhan)

    def _upd(self, c):
        try:
            c.update()
        except Exception:
            pass

    def mulai(self, e=None):
        if self.sibuk:
            return
        teks = (self.keluhan.value or "").strip()
        if not teks:
            self.keluhan.error_text = "Tulis dulu gejalanya, atau pilih salah satu contoh di atas"
            return self._upd(self.keluhan)
        self.sibuk, self.hasil = True, None
        self.tombol.disabled, self.tombol.text = True, "Menganalisis…"
        self.hasil_box.visible, self.hasil_box.opacity, self.hasil_box.offset = False, 0, ft.Offset(0, 0.06)
        self.loading.visible = True
        for c in (self.tombol, self.hasil_box, self.loading):
            self._upd(c)
        self.spark._mulai()
        for g in self.loading.content.controls[1:]:
            g._mulai()
        kotak = {}

        def kerja():
            kotak["r"] = ai.analisis(teks, self.ambil_kendaraan())
        t = threading.Thread(target=kerja, daemon=True)
        t.start()
        awal, i = time.time(), 0
        while t.is_alive() or time.time() - awal < MIN_DETIK:  # animasi langkah berjalan sampai hasil siap
            i += 1
            self.langkah.content = ft.Text(LANGKAH[i % len(LANGKAH)], key=str(i), size=15, weight=TW.W_600, color=ui.LABEL)
            self._upd(self.langkah)
            time.sleep(JEDA_LANGKAH if MIN_DETIK else 0.01)
        t.join()
        self._tampil(kotak["r"])

    def _tampil(self, r):
        self.hasil = r
        self.saat_hasil(r)
        pct = int(round(r["keyakinan"] * 100))
        warna = ui.GREEN if pct >= 75 else ui.ORANGE if pct >= 50 else ui.RED
        isi = r.get("keyakinan", 0)
        bar = ft.Container(width=0, height=8, border_radius=4, bgcolor=warna, animate=ft.Animation(900, ft.AnimationCurve.EASE_OUT_CUBIC))
        chip = ft.Container(scale=0.6, animate_scale=ft.Animation(500, ft.AnimationCurve.EASE_OUT_BACK),
                            padding=ft.padding.symmetric(horizontal=12, vertical=7), border_radius=18, bgcolor=self.tema["tint"],
                            content=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=self.tema["aksen"]),
                                            ft.Text(KATEGORI[r["kategori"]], size=14, weight=TW.W_700, color=self.tema["aksen"])],
                                           spacing=6, tight=True))
        isi_kol = [
            ft.Row([chip], alignment=ft.MainAxisAlignment.START),
            ft.Row([ft.Text("Keyakinan", size=12, color=ui.SECONDARY),
                    ft.Container(width=LEBAR_BAR, height=8, border_radius=4, bgcolor=ui.FILL, content=ft.Row([bar])),
                    ft.Text(f"{pct}%", size=13, weight=TW.W_700, color=warna)], spacing=10,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(r["ringkasan"], size=14, weight=TW.W_600, color=ui.LABEL),
            ft.Text(r["saran"], size=13, color=ui.SECONDARY)]
        if r.get("tindakan"):
            isi_kol.append(ft.Column([ft.Text("Yang sebaiknya Anda lakukan", size=12, weight=TW.W_600, color=ui.SECONDARY),
                                      *[ft.Row([ft.Icon(ft.Icons.CHECK, size=15, color=ui.GREEN),
                                                ft.Text(t, size=13, color=ui.LABEL, expand=True)], spacing=6,
                                               vertical_alignment=ft.CrossAxisAlignment.START) for t in r["tindakan"]]], spacing=4))
        if r.get("perlu_derek") and self.saat_derek:
            isi_kol.append(ft.Container(padding=12, border_radius=12, bgcolor=ui.ORANGE_TINT, content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ui.ORANGE, size=20),
                        ft.Text("Kendaraan sebaiknya tidak dikendarai. Layanan derek disarankan.", size=13, color=ui.LABEL, expand=True)], spacing=8),
                ft.OutlinedButton("Pakai layanan Derek", icon=ft.Icons.LOCAL_SHIPPING, on_click=lambda e: self.saat_derek(),
                                  style=ft.ButtonStyle(color=ui.ORANGE, side=ft.BorderSide(1.2, ui.ORANGE),
                                                       shape=ft.RoundedRectangleBorder(radius=10)))], spacing=8)))
        isi_kol.append(ft.Text(f"Sumber: {r['sumber']}" + (f" · {r['catatan']}" if r.get("catatan") else ""), size=11, color=ui.SECONDARY))
        self.hasil_box.content = ft.Column(isi_kol, spacing=10)
        self.loading.visible = False
        self.hasil_box.visible = True
        self.tombol.disabled, self.tombol.text = False, "Analisis ulang"
        for c in (self.loading, self.hasil_box, self.tombol):
            self._upd(c)
        # animasi masuk: kartu naik + fade, chip 'pop', bar keyakinan terisi
        self.hasil_box.opacity, self.hasil_box.offset = 1, ft.Offset(0, 0)
        chip.scale = 1
        bar.width = max(6, LEBAR_BAR * isi)
        for c in (self.hasil_box, chip, bar):
            self._upd(c)
        self.sibuk = False

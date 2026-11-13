"""Layar 'Kendaraan Saya': pilih jenis, cari merek/model dari database, isi tahun & plat, simpan ke profil."""
import datetime
import flet as ft
import kendaraan_db as kdb
import ui
from ui import TW, M

IKON = {"motor": ft.Icons.TWO_WHEELER, "mobil": ft.Icons.DIRECTIONS_CAR}


class PilihKendaraan:
    def __init__(self, page, tema, awal, saat_simpan, saat_batal):
        """awal: dict kendaraan tersimpan atau None. saat_simpan(jenis, merek, model, tahun, plat) -> (ok, pesan)."""
        self.page, self.tema, self.saat_simpan = page, tema, saat_simpan
        awal = awal or {}
        self.jenis = awal.get("jenis") or "motor"
        self.merek, self.model = awal.get("merek"), awal.get("model")
        self.manual = False
        aksen = tema["aksen"]
        self.cari = ui.kolom("Cari merek atau model (mis. Vario, Avanza)", prefix_icon=ft.Icons.SEARCH,
                             on_change=lambda e: self._hasil(), hint_text="Ketik sebagian nama, typo pun bisa")
        self.chips = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)
        self.daftar = ft.Column(spacing=0)
        self.info = ft.Text("", size=12, color=ui.SECONDARY)
        self.pilihan_kartu = ft.Container(visible=False, padding=14, border_radius=14, bgcolor=tema["tint"])
        self.m_merek = ui.kolom("Merek", visible=False, on_change=lambda e: self._manual_ubah())
        self.m_model = ui.kolom("Model / tipe", visible=False, on_change=lambda e: self._manual_ubah())
        self.tbl_manual = ft.TextButton("Tidak ketemu? Isi manual", icon=ft.Icons.EDIT_OUTLINED, on_click=self._toggle_manual,
                                        style=ft.ButtonStyle(color=aksen))
        self.tahun = ui.kolom("Tahun (opsional)", value=str(awal["tahun"]) if awal.get("tahun") else "",
                              keyboard_type=ft.KeyboardType.NUMBER, max_length=4)
        self.plat = ui.kolom("Plat nomor (opsional)", value=awal.get("plat") or "", capitalization=ft.TextCapitalization.CHARACTERS)
        self.err = ft.Text("", color=ui.RED, size=13, visible=False)
        self.seg = ui.segmented([("motor", "Motor", ft.Icons.TWO_WHEELER), ("mobil", "Mobil", ft.Icons.DIRECTIONS_CAR)], self.jenis,
                                self._ganti_jenis, tema)
        self.kontrol = ui.dengan_bar(
            ui.halaman(
                ui.header("Kendaraan Saya", "Disimpan di profil dan dipakai otomatis saat memesan."),
                ui.body(
                    ft.Row([self.seg], alignment=ft.MainAxisAlignment.CENTER),
                    ui.kartu(self.cari, self.chips, ft.Container(self.daftar, border_radius=12, bgcolor=ui.BG,
                                                                  border=ft.border.all(0.5, ui.SEPARATOR)), self.info,
                             self.tbl_manual, self.m_merek, self.m_model),
                    self.pilihan_kartu,
                    ui.kartu(self.tahun, self.plat, self.err),
                ), nav=False),
            ui.tombol("Batal", None, lambda e: saat_batal(), tema, False), ui.tombol("Simpan", ft.Icons.CHECK, self._simpan, tema))
        self._chips()
        self._hasil()
        self._ringkas()

    # ── tampilan ──
    def _chips(self):
        self.chips.controls = [ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=7), border_radius=18, ink=True, bgcolor=ui.FILL,
            on_click=lambda e, m=m: self._isi_cari(m), content=ft.Text(m, size=13, weight=TW.W_500, color=ui.LABEL))
            for m in kdb.merek(self.jenis)]

    def _isi_cari(self, teks):
        self.cari.value = teks
        self._upd(self.cari)
        self._hasil()

    def _upd(self, c):
        try:
            c.update()
        except Exception:
            pass

    def _hasil(self):
        hasil = kdb.cari(self.jenis, self.cari.value or "", 40)
        baris = []
        for i, (mrk, mdl) in enumerate(hasil):
            pilih = (mrk, mdl) == (self.merek, self.model)
            baris.append(ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=11), ink=True, on_click=lambda e, a=mrk, b=mdl: self._pilih(a, b),
                bgcolor=self.tema["tint"] if pilih else None,
                content=ft.Row([ft.Column([ft.Text(mdl, size=15, weight=TW.W_600, color=ui.LABEL),
                                           ft.Text(mrk, size=12, color=ui.SECONDARY)], spacing=1, expand=True),
                                ft.Icon(ft.Icons.CHECK_CIRCLE if pilih else ft.Icons.CHEVRON_RIGHT, size=20,
                                        color=self.tema["aksen"] if pilih else ui.SEPARATOR)],
                               vertical_alignment=ft.CrossAxisAlignment.CENTER)))
            if i < len(hasil) - 1:
                baris.append(ui.pemisah())
        self.daftar.controls = baris or [ft.Container(padding=16, content=ft.Text(
            "Tidak ditemukan. Coba kata lain atau isi manual.", size=14, color=ui.SECONDARY))]
        total = kdb.jumlah(self.jenis)
        self.info.value = (f"{len(hasil)} hasil dari {total} model {self.jenis}" if (self.cari.value or "").strip()
                           else f"Menampilkan {len(hasil)} dari {total} model {self.jenis}. Ketik untuk mencari.")
        self._upd(self.daftar)
        self._upd(self.info)

    def _ringkas(self):
        mrk, mdl = self._nilai()
        self.pilihan_kartu.visible = bool(mrk and mdl)
        if mrk and mdl:
            self.pilihan_kartu.content = ft.Row([
                ft.Icon(IKON[self.jenis], color=self.tema["aksen"], size=26),
                ft.Column([ft.Text("Kendaraan dipilih", size=12, color=ui.SECONDARY),
                           ft.Text(f"{mrk} {mdl}", size=17, weight=TW.W_700, color=ui.LABEL)], spacing=1, expand=True)],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self._upd(self.pilihan_kartu)

    # ── aksi ──
    def _ganti_jenis(self, k):
        if k == self.jenis:
            return
        self.jenis, self.merek, self.model = k, None, None
        self.cari.value = ""
        self._chips()
        self._hasil()
        self._ringkas()
        self._upd(self.cari)
        self._upd(self.chips)

    def _pilih(self, mrk, mdl):
        self.merek, self.model = mrk, mdl
        self.err.visible = False
        self._hasil()
        self._ringkas()

    def _toggle_manual(self, e):
        self.manual = not self.manual
        self.m_merek.visible = self.m_model.visible = self.manual
        self.tbl_manual.text = "Pilih dari daftar" if self.manual else "Tidak ketemu? Isi manual"
        for c in (self.m_merek, self.m_model, self.tbl_manual):
            self._upd(c)
        self._ringkas()

    def _manual_ubah(self):
        self._ringkas()

    def _nilai(self):
        if self.manual and (self.m_merek.value or "").strip() and (self.m_model.value or "").strip():
            return self.m_merek.value.strip(), self.m_model.value.strip()
        return self.merek, self.model

    def data(self):
        mrk, mdl = self._nilai()
        return dict(jenis=self.jenis, merek=mrk, model=mdl, tahun=(self.tahun.value or "").strip(), plat=(self.plat.value or "").strip())

    def _simpan(self, e=None):
        d = self.data()
        ok, msg = self.saat_simpan(d["jenis"], d["merek"], d["model"], d["tahun"], d["plat"])
        if not ok:
            self.err.value, self.err.visible = msg, True
            self._upd(self.err)

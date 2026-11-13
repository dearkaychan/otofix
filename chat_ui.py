"""Layar chat gaya iMessage antara pengguna dan mekanik untuk satu pesanan (dipakai kedua aplikasi)."""
import time
import flet as ft
import db
import ui
import lokasi
from ui import TW, M


class Chat:
    def __init__(self, page, tema, saya_id, pid, judul, sub, kembali, lawan=None, banner=None, telp=None):
        self.page, self.tema, self.saya, self.pid, self.kembali = page, tema, saya_id, pid, kembali
        self.judul, self.telp = judul, telp
        self.terakhir = None
        self.daftar = ft.ListView(expand=True, spacing=6, auto_scroll=True,
                                  padding=ft.padding.symmetric(horizontal=M, vertical=12))
        self.isian = ui.kolom("Tulis pesan…", multiline=True, min_lines=1, max_lines=4, expand=True, on_submit=self.kirim)
        self.tombol_kirim = ft.Container(
            width=46, height=46, border_radius=23, bgcolor=tema["tombol"], alignment=ft.alignment.center, on_click=self.kirim,
            content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=tema.get("fg", "white"), size=24))
        self.bar_input = ft.Container(padding=ft.padding.symmetric(horizontal=M, vertical=10), bgcolor=ui.SURFACE,
                                      border=ft.border.only(top=ft.BorderSide(0.5, ui.SEPARATOR)))
        self.tutup_info = ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, size=16, color=ui.SECONDARY),
                                  ft.Text("Chat ditutup karena pesanan sudah tidak aktif. Riwayat tetap bisa dibaca.",
                                          size=13, color=ui.SECONDARY, expand=True)], spacing=8)
        self.tbl_telp = ft.IconButton(ft.Icons.CALL, icon_color=tema["aksen"], icon_size=22, tooltip="Telepon",
                                      bgcolor=ui.alpha(tema["aksen"], 0.14), on_click=self.telepon, visible=self._aktif())
        top = ft.Container(
            padding=ft.padding.only(left=8, right=M + 4, top=12, bottom=10), bgcolor=ui.SURFACE,
            border=ft.border.only(bottom=ft.BorderSide(0.5, ui.SEPARATOR)),
            content=ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, icon_color=tema["aksen"], icon_size=20, on_click=lambda e: kembali()),
                ui.avatar(lawan, tema, 20),
                ft.Column([ft.Text(judul, size=17, weight=TW.W_700, color=ui.LABEL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                           ft.Text(sub, size=12, color=ui.SECONDARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                          spacing=1, expand=True), self.tbl_telp], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8))
        self.kontrol = ft.Column([top, *([ft.Container(banner, padding=ft.padding.only(left=M, right=M, top=10))] if banner else []),
                                  self.daftar, self.bar_input], expand=True, spacing=0)
        self._pasang_input()
        self.refresh()

    # ── tampilan ──
    def _aktif(self):
        p = db.pesanan(self.pid)
        return bool(p) and p["status"] == "Mekanik menuju lokasi"

    def _pasang_input(self):
        self.bar_input.content = (ft.Row([self.isian, self.tombol_kirim], spacing=10, vertical_alignment=ft.CrossAxisAlignment.END)
                                  if self._aktif() else self.tutup_info)

    def _gelembung(self, m):
        saya = m["dari_id"] == self.saya
        fg = self.tema.get("fg", "white") if saya else ui.LABEL
        bubble = ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=9), border_radius=ft.border_radius.only(
                top_left=18, top_right=18, bottom_left=18 if saya else 4, bottom_right=4 if saya else 18),
            bgcolor=self.tema["tombol"] if saya else ui.FILL,
            content=ft.Column([ft.Text(m["teks"], size=15, color=fg, selectable=True),
                               ft.Text(m["waktu"], size=10, color=ui.alpha(fg, 0.7), text_align=ft.TextAlign.END)],
                              spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END if saya else ft.CrossAxisAlignment.START, tight=True))
        sisi = ft.Container(width=56)  # batasi lebar gelembung
        return ft.Row([sisi, bubble] if saya else [bubble, sisi], alignment=ft.MainAxisAlignment.END if saya else ft.MainAxisAlignment.START,
                      vertical_alignment=ft.CrossAxisAlignment.START)

    def refresh(self):
        """Ambil pesan baru dan gambar ulang bila ada perubahan (dipanggil saat kirim & oleh polling)."""
        msgs = db.chat_pesanan(self.pid, self.saya)
        tanda = ([m["id"] for m in msgs], self._aktif())
        db.chat_tandai_dibaca(self.pid, self.saya)
        if tanda == self.terakhir:
            return
        self.terakhir = tanda
        self.daftar.controls = ([self._gelembung(m) for m in msgs] if msgs else
                                [ui.kosong(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, "Belum ada pesan", "Sapa dulu untuk memulai percakapan.")])
        self._pasang_input()
        self.tbl_telp.visible = self._aktif()   # telepon hanya selama pesanan berjalan (chat aktif)
        for c in (self.daftar, self.bar_input, self.tbl_telp):
            try:
                c.update()
            except Exception:
                pass

    def telepon(self, e=None):
        """Panggilan telepon biasa (dialer perangkat) ke nomor HP lawan bicara, dengan konfirmasi."""
        uri = lokasi.telp_uri(self.telp)
        if not uri:
            return ui.snack(self.page, f"Nomor telepon {self.judul} belum diisi. Silakan minta ia melengkapinya di Profil, lalu chat saja dulu.")
        ui.konfirmasi(self.page, f"Telepon {self.judul}?", f"Panggilan akan dilakukan ke {self.telp}.", "Telepon",
                      lambda: self.page.launch_url(uri))

    def kirim(self, e=None):
        teks = (self.isian.value or "").strip()
        if not teks:
            return
        ok, msg = db.kirim_chat(self.pid, self.saya, teks)
        if not ok:
            return ui.snack(self.page, msg)
        self.isian.value = ""
        self.refresh()
        try:
            self.isian.update()
        except Exception:
            pass

    def polling(self, aktif):
        """Menyegarkan pesan tiap 1,5 detik selama layar chat terbuka (aktif() -> False menghentikan)."""
        while aktif():
            time.sleep(1.5)
            if aktif():
                self.refresh()

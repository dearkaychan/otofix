"""Peta kecil yang bisa diperbesar (OpenStreetMap). Dipakai mitra untuk melihat lokasi pemesan.
Modul peta Flet 0.28.3 diimpor lewat flet.core.map; bila gagal dimuat, dipakai tampilan cadangan."""
import math
import flet as ft
import ui
import lokasi
from engine import jarak_haversine, MAX_JARAK_KM

try:
    from flet.core.map.map import Map, MapLatitudeLongitude as LL, MapInteractionConfiguration, MapInteractiveFlag
    from flet.core.map.tile_layer import TileLayer
    from flet.core.map.simple_attribution import SimpleAttribution
    from flet.core.map.marker_layer import Marker, MarkerLayer
    ADA = True
except Exception:  # pragma: no cover
    ADA = False

KECIL, BESAR = 150, 400
# Penyedia tile TANPA API key. Server resmi OpenStreetMap memblokir aplikasi tanpa User-Agent khusus (403),
# dan CARTO kini meminta otorisasi. Esri World Street Map bisa dipakai bebas untuk proyek non-komersial
# dengan atribusi. Ganti PENYEDIA bila perlu.
PENYEDIA = "esri"
TILES = {
    "esri": dict(url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
                 sub=None, atribusi="Tiles © Esri"),
    "osm_de": dict(url="https://tile.openstreetmap.de/{z}/{x}/{y}.png", sub=None, atribusi="© OpenStreetMap"),
}
TILE = TILES[PENYEDIA]["url"]


def url_rute(lat, lon):
    """Navigasi Google Maps ke lokasi pemesan. Tanpa 'origin' -> Google memakai lokasi perangkat sebagai titik awal."""
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving"


def _pin(ikon, warna):
    return ft.Container(width=34, height=34, border_radius=17, bgcolor=warna, alignment=ft.alignment.center,
                        border=ft.border.all(2.5, "white"),
                        shadow=ft.BoxShadow(blur_radius=6, color="#40000000"),
                        content=ft.Icon(ikon, color="white", size=18))


def _zoom(km):
    return 16 if km < 0.4 else 15 if km < 1 else 14 if km < 2.5 else 13 if km < 6 else 12


def peta_lipat(page, lat, lon, mitra=None, judul="Lokasi pemesan"):
    """Kartu peta: ketuk untuk membesar (bisa digeser/zoom), ketuk ikon pojok untuk mengecil."""
    buka = [False]
    tengah = ((lat + mitra[0]) / 2, (lon + mitra[1]) / 2) if mitra else (lat, lon)
    zoom = _zoom(jarak_haversine(lat, lon, *mitra)) if mitra else 16

    if ADA:
        penanda = [Marker(content=_pin(ft.Icons.PERSON_PIN_CIRCLE, ui.RED), coordinates=LL(lat, lon), width=34, height=34)]
        if mitra:
            penanda.append(Marker(content=_pin(ft.Icons.ENGINEERING, ui.GREEN), coordinates=LL(*mitra), width=34, height=34))
        peta = Map(
            expand=True, initial_center=LL(*tengah), initial_zoom=zoom, min_zoom=3, max_zoom=19,
            interaction_configuration=MapInteractionConfiguration(flags=MapInteractiveFlag.NONE),
            layers=[TileLayer(url_template=TILE, fallback_url=TILES["osm_de"]["url"], max_native_zoom=19),
                    MarkerLayer(markers=penanda),
                    SimpleAttribution(text=TILES[PENYEDIA]["atribusi"], alignment=ft.alignment.bottom_right,
                                      bgcolor=ui.alpha(ui.SURFACE, 0.85))])
    else:
        peta = ft.Container(expand=True, bgcolor=ui.FILL, alignment=ft.alignment.center, content=ft.Column([
            ft.Icon(ft.Icons.PLACE, color=ui.RED, size=40),
            ft.Text(f"{lat:.5f}, {lon:.5f}", size=13, color=ui.SECONDARY)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, alignment=ft.MainAxisAlignment.CENTER))

    ikon = ft.Icon(ft.Icons.OPEN_IN_FULL, size=16, color=ui.LABEL)
    tombol_sudut = ft.Container(width=34, height=34, border_radius=17, bgcolor=ui.alpha(ui.SURFACE, 0.95), right=10, top=10,
                                alignment=ft.alignment.center, content=ikon,
                                shadow=ft.BoxShadow(blur_radius=6, color="#26000000"))
    chip = ft.Container(left=10, bottom=10, padding=ft.padding.symmetric(horizontal=10, vertical=5), border_radius=14,
                        bgcolor=ui.alpha(ui.SURFACE, 0.95), content=ft.Row([ft.Icon(ft.Icons.PLACE, size=14, color=ui.RED),
                                                             ft.Text(judul, size=12, weight=ui.TW.W_600, color=ui.LABEL)], spacing=4, tight=True))
    penutup = ft.Container(expand=True)  # menangkap ketukan saat peta masih kecil
    kotak = ft.Container(height=KECIL, border_radius=14, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, animate=ui.anim(380),
                         bgcolor=ui.FILL, content=ft.Stack([peta, penutup, chip, tombol_sudut]))
    rute = ft.Row([ft.FilledButton(
        "Rute di Google Maps", icon=ft.Icons.NAVIGATION, height=46, expand=True,
        on_click=lambda e: page.launch_url(url_rute(lat, lon)),
        style=ft.ButtonStyle(bgcolor=ui.GREEN, color="white", shape=ft.RoundedRectangleBorder(radius=12),
                             text_style=ft.TextStyle(size=15, weight=ui.TW.W_600)))])

    def ubah(e=None):
        buka[0] = not buka[0]
        kotak.height = BESAR if buka[0] else KECIL
        penutup.visible = not buka[0]
        chip.visible = not buka[0]
        ikon.name = ft.Icons.CLOSE_FULLSCREEN if buka[0] else ft.Icons.OPEN_IN_FULL
        if ADA:
            peta.interaction_configuration = MapInteractionConfiguration(
                flags=MapInteractiveFlag.ALL if buka[0] else MapInteractiveFlag.NONE)
        try:
            page.update()
        except Exception:
            pass

    penutup.on_click = ubah
    tombol_sudut.on_click = ubah
    return ft.Column([kotak, rute], spacing=8)


class PemilihLokasi:
    """Pemilih lokasi bengkel: ketuk peta untuk menaruh pin, atau pakai GPS perangkat.
    Dipakai saat daftar akun mitra (wajib) dan di Profil mitra (untuk mengubah).
    Aturan radius 10 km tetap dihitung dari titik ini (lihat db.mitra_terdekat/db.penawaran)."""

    def __init__(self, page, pelacak, lat=None, lon=None, alamat="", pusat=None):
        self.page, self.pelacak, self.on_ubah = page, pelacak, None
        self.lat, self.lon = lat, lon
        self._auto = None  # alamat hasil pencarian otomatis terakhir (agar tidak menimpa ketikan pengguna)
        pusat = pusat or ((lat, lon) if lat is not None else (db_base()))
        self.ket = ft.Text("", size=13, weight=ui.TW.W_600)
        self.alamat = ui.kolom("Alamat / patokan bengkel", value=alamat or "", multiline=True, min_lines=1, max_lines=3)
        self.btn_gps = ft.OutlinedButton(
            "Gunakan lokasi saya saat ini", icon=ft.Icons.MY_LOCATION, height=44, on_click=self._gps,
            style=ft.ButtonStyle(color=ui.GREEN, side=ft.BorderSide(1.2, ui.GREEN), shape=ft.RoundedRectangleBorder(radius=10)))
        isi = []
        if ADA:
            self.lapis = MarkerLayer(markers=self._penanda())
            self.peta = Map(
                expand=True, initial_center=LL(*pusat), initial_zoom=15 if lat is not None else 13, min_zoom=3, max_zoom=19,
                interaction_configuration=MapInteractionConfiguration(flags=MapInteractiveFlag.ALL), on_tap=self._tap,
                layers=[TileLayer(url_template=TILE, fallback_url=TILES["osm_de"]["url"], max_native_zoom=19), self.lapis,
                        SimpleAttribution(text=TILES[PENYEDIA]["atribusi"], alignment=ft.alignment.bottom_right,
                                          bgcolor=ui.alpha(ui.SURFACE, 0.85))])
            isi.append(ft.Text("Ketuk peta untuk menaruh pin di lokasi bengkel.", size=13, color=ui.SECONDARY))
            isi.append(ft.Container(height=230, border_radius=14, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, bgcolor=ui.FILL,
                                    content=self.peta))
        isi += [self.ket, self.btn_gps, self.alamat]
        self.kontrol = ft.Column(isi, spacing=10)
        self._teks()

    # -- state --
    def siap(self):
        return self.lat is not None and self.lon is not None

    def data(self):
        return dict(lat=self.lat, lon=self.lon, alamat=(self.alamat.value or "").strip())

    def _penanda(self):
        if not self.siap() or not ADA:
            return []
        return [Marker(content=_pin(ft.Icons.STORE, ui.GREEN), coordinates=LL(self.lat, self.lon), width=34, height=34)]

    def _teks(self):
        if self.siap():
            self.ket.value, self.ket.color = f"Lokasi dipilih: {self.lat:.5f}, {self.lon:.5f}", ui.GREEN
        else:
            self.ket.value, self.ket.color = "Lokasi belum dipilih", ui.ORANGE

    def _perbarui(self, kontrol):
        try:
            kontrol.update()
        except Exception:
            pass

    def set(self, lat, lon, geser_peta=False):
        self.lat, self.lon = round(lat, 6), round(lon, 6)
        if ADA:
            self.lapis.markers = self._penanda()
            self._perbarui(self.lapis)
            if geser_peta:
                try:
                    self.peta.move_to(destination=LL(self.lat, self.lon), zoom=16)
                except Exception:
                    pass
        self._teks()
        self._perbarui(self.ket)
        self.page.run_thread(self._cari_alamat)
        if self.on_ubah:
            self.on_ubah()

    # -- aksi --
    def _tap(self, e):
        self.set(e.coordinates.latitude, e.coordinates.longitude)

    def _gps(self, e=None):
        self.btn_gps.disabled, self.btn_gps.text = True, "Mencari lokasi…"
        self._perbarui(self.btn_gps)
        self.page.run_thread(self._ambil_gps)

    def _ambil_gps(self):
        lat, lon, ok = self.pelacak.posisi()
        self.btn_gps.disabled, self.btn_gps.text = False, "Gunakan lokasi saya saat ini"
        self._perbarui(self.btn_gps)
        if ok:
            self.set(lat, lon, geser_peta=True)
        else:
            ui.snack(self.page, "GPS tidak tersedia. Ketuk peta untuk memilih lokasi bengkel.")

    def _cari_alamat(self):
        if not self.siap():
            return
        nama = lokasi.nama_tempat(self.lat, self.lon, True)
        if not (self.alamat.value or "").strip() or self.alamat.value == self._auto:
            self.alamat.value = self._auto = nama
            self._perbarui(self.alamat)


def db_base():
    import db
    return db.BASE_LAT, db.BASE_LON


def fmt_jarak(km):
    return f"{int(km * 1000)} m" if km < 1 else f"{km:.1f}".replace(".", ",") + " km"


class PetaLacak:
    """Peta pelacakan langsung: posisi mekanik (bergerak) menuju lokasi pemesan. Dipanggil perbarui() berkala
    (tiap ~2 detik) oleh aplikasi pengguna; data berasal dari db.lokasi_mekanik (hanya pemilik pesanan yang boleh melihat)."""

    def __init__(self, page, tema, lat, lon, nama_mekanik, pid, user_id):
        self.page, self.tema, self.lat, self.lon = page, tema, lat, lon
        self.nama, self.pid, self.uid = nama_mekanik, pid, user_id
        self.mk_pos, self.zoom_terakhir = None, None
        self.status = ft.Text("Menunggu sinyal lokasi mekanik…", size=15, weight=ui.TW.W_700, color=ui.LABEL)
        self.sub = ft.Text("", size=12, color=ui.SECONDARY)
        titik = ui.denyut(ft.Container(width=8, height=8, border_radius=4, bgcolor="white"), 1, 0.3, besar=1.8, ms=900)
        live = ft.Container(padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=12, bgcolor=ui.GREEN,
                            content=ft.Row([titik, ft.Text("LANGSUNG", size=10, weight=ui.TW.W_700, color="white")], spacing=6, tight=True))
        isi = [ft.Row([ft.Icon(ft.Icons.NEAR_ME, color=tema["aksen"], size=20),
                       ft.Text("Posisi mekanik", size=16, weight=ui.TW.W_700, color=ui.LABEL, expand=True), live],
                      spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)]
        if ADA:
            self.pin_pelanggan = Marker(content=_pin(ft.Icons.PERSON_PIN_CIRCLE, ui.RED), coordinates=LL(lat, lon), width=34, height=34)
            self.lapis = MarkerLayer(markers=[self.pin_pelanggan])
            self.peta = Map(
                expand=True, initial_center=LL(lat, lon), initial_zoom=15, min_zoom=3, max_zoom=19,
                interaction_configuration=MapInteractionConfiguration(flags=MapInteractiveFlag.ALL),
                layers=[TileLayer(url_template=TILE, fallback_url=TILES["osm_de"]["url"], max_native_zoom=19), self.lapis,
                        SimpleAttribution(text=TILES[PENYEDIA]["atribusi"], alignment=ft.alignment.bottom_right,
                                          bgcolor=ui.alpha(ui.SURFACE, 0.85))])
            isi.append(ft.Container(height=230, border_radius=14, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, bgcolor=ui.FILL,
                                    content=self.peta))
        isi += [self.status, self.sub]
        self.kontrol = ui.kartu(*isi)
        self.perbarui()

    def _upd(self, c):
        try:
            c.update()
        except Exception:
            pass

    def perbarui(self):
        """Ambil posisi terbaru dan perbarui peta serta teks jarak/perkiraan tiba."""
        d = db_live(self.pid, self.uid)
        if not d:
            self.status.value = ("Menunggu sinyal lokasi mekanik…" if self.mk_pos is None else "Sinyal lokasi mekanik terputus sementara…")
            self.sub.value = ""
        else:
            self.mk_pos = (d["lat"], d["lon"])
            jarak = jarak_haversine(self.lat, self.lon, d["lat"], d["lon"])
            self.status.value = ("Mekanik sudah tiba di lokasi Anda" if jarak < 0.05 else
                                 f"{self.nama} berjarak {fmt_jarak(jarak)} · tiba ± {lokasi.eta_menit(jarak)} menit")
            self.sub.value = "Diperbarui " + lokasi.umur_teks(d["umur"])
            if ADA:
                self.lapis.markers = [self.pin_pelanggan, Marker(content=_pin(ft.Icons.ENGINEERING, ui.GREEN),
                                                                  coordinates=LL(*self.mk_pos), width=34, height=34)]
                self._upd(self.lapis)
                z = _zoom(jarak)
                if z != self.zoom_terakhir:  # sesuaikan bingkai hanya saat zoom berubah agar tidak mengganggu geseran pengguna
                    self.zoom_terakhir = z
                    try:
                        self.peta.move_to(destination=LL((self.lat + d["lat"]) / 2, (self.lon + d["lon"]) / 2), zoom=z)
                    except Exception:
                        pass
        self._upd(self.status)
        self._upd(self.sub)


def db_live(pid, uid):
    import db
    return db.lokasi_mekanik(pid, uid)

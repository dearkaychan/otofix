"""Komponen UI bersama OtoFix - gaya iOS (Human Interface Guidelines).
Ritme jarak seragam: margin layar M=16, jarak antar kartu GAP=12, padding kartu 16,
kelipatan 4/8 di semua tempat. Efek: kartu masuk bertahap, radar berdenyut, hero bergradien."""
import threading
import time
import flet as ft
import db

# ── Palet warna (terang & gelap) ───────────────────────────────────────────────
# Semua warna dibaca lewat ui.NAMA saat layar dibangun, jadi ganti tema = terapkan_tema() lalu bangun ulang layar.
# Mode gelap: hitam murni (nyaman di OLED), kartu abu sangat gelap #1C1C1E, teks putih lembut, aksen iOS gelap.
PALET = {
    "terang": dict(
        BG="#F2F2F7", SURFACE="#FFFFFF", LABEL="#1C1C1E", SECONDARY="#6C6C70", SEPARATOR="#D1D1D6", FILL="#E5E5EA",
        FIELD="#EFEFF4", THUMB="#FFFFFF", BLUE="#007AFF", GREEN="#34C759", RED="#FF3B30", ORANGE="#FF9500",
        BLUE_TINT="#E5F1FF", GREEN_TINT="#E3F7E8", ORANGE_TINT="#FFF1DC", RED_TINT="#FFE5E3",
        KARTU_BORDER="#00FFFFFF", BAYANGAN="#0F000000",
        GRAD_P=("#0A84FF", "#5E5CE6"), GRAD_M=("#30C75A", "#0E9F7E"), FG_M="white"),
    "gelap": dict(
        BG="#000000", SURFACE="#1C1C1E", LABEL="#F5F5F7", SECONDARY="#98989F", SEPARATOR="#38383A", FILL="#2C2C2E",
        FIELD="#2C2C2E", THUMB="#636366", BLUE="#0A84FF", GREEN="#30D158", RED="#FF453A", ORANGE="#FF9F0A",
        BLUE_TINT="#0A2A4D", GREEN_TINT="#0C2F1B", ORANGE_TINT="#3B2A08", RED_TINT="#3D1411",
        KARTU_BORDER="#2C2C2E", BAYANGAN="#00000000",
        GRAD_P=("#0A63CC", "#4443B8"), GRAD_M=("#1E8E44", "#0A6B57"), FG_M="#00250F"),
}
GELAP = "#0A6FE0"  # latar layar pencarian imersif (sama di kedua mode)
STAR = "#FFB800"
PENGGUNA, MITRA, STATUS_WARNA, MODE = dict(fg="white"), dict(), {}, "terang"


def terapkan_tema(mode, page=None):
    """Mengganti palet global. Setelah ini, layar harus dibangun ulang agar warna baru terpakai."""
    global MODE
    MODE = "gelap" if mode == "gelap" else "terang"
    p = PALET[MODE]
    globals().update(p)
    PENGGUNA.update(aksen=p["BLUE"], tombol=p["BLUE"], fg="white", tint=p["BLUE_TINT"], grad=p["GRAD_P"])
    MITRA.update(aksen=p["GREEN"], tombol=p["GREEN"], fg=p["FG_M"], tint=p["GREEN_TINT"], grad=p["GRAD_M"])
    STATUS_WARNA.update({
        "Mencari mekanik": (p["ORANGE"], p["ORANGE_TINT"]), "Mekanik menuju lokasi": (p["BLUE"], p["BLUE_TINT"]),
        "Selesai": (p["GREEN"], p["GREEN_TINT"]), "Dibatalkan": (p["SECONDARY"], p["FILL"]),
        "Tidak ada mekanik tersedia": (p["RED"], p["RED_TINT"]), "Tidak ada bengkel terdekat": (p["RED"], p["RED_TINT"]),
        "Ditolak": (p["RED"], p["RED_TINT"])})
    if page is not None:
        page.theme_mode = ft.ThemeMode.DARK if MODE == "gelap" else ft.ThemeMode.LIGHT
        page.bgcolor = p["BG"]


terapkan_tema("terang")

M, GAP = 16, 12  # margin layar & jarak antar blok
TW = ft.FontWeight
I = lambda n: getattr(ft.Icons, n, ft.Icons.BUILD)



def alpha(warna, a):
    """Warna + transparansi -> '#AARRGGBB' (format yang pasti dikenali Flet)."""
    w = {"white": "#FFFFFF", "black": "#000000"}.get(warna, warna).lstrip("#")
    return f"#{round(a * 255):02X}{w}"


def anim(ms=250):
    return ft.Animation(ms, ft.AnimationCurve.EASE_OUT_CUBIC)


def walk(c):
    yield c
    for a in ("controls", "content", "actions", "destinations"):
        v = getattr(c, a, None)
        if v is None:
            continue
        for x in (v if isinstance(v, (list, tuple)) else [v]):
            if isinstance(x, ft.Control):
                yield from walk(x)


# ── Efek ───────────────────────────────────────────────────────────────────────
def _fx(kw):
    kw.update(opacity=0, offset=ft.Offset(0, 0.05), animate_opacity=450,
              animate_offset=ft.Animation(500, ft.AnimationCurve.EASE_OUT_CUBIC), data="fx")
    return kw


def denyut(c, op_kecil, op_besar, besar=1.6, ms=1500, tunda=0.0):
    """Membuat kontrol berdenyut terus-menerus (dimulai oleh muncul())."""
    c.scale, c.opacity = 1, op_kecil
    c.animate_scale = ft.Animation(ms, ft.AnimationCurve.EASE_IN_OUT)
    c.animate_opacity = ft.Animation(ms, ft.AnimationCurve.EASE_IN_OUT)
    besar_dulu = [False]

    def balik(e=None):
        try:
            besar_dulu[0] = not besar_dulu[0]
            c.scale, c.opacity = (besar, op_besar) if besar_dulu[0] else (1, op_kecil)
            c.update()
        except Exception:
            pass
    c.on_animation_end = balik
    c.data = f"pulse:{tunda}"
    c._mulai = balik
    return c


def muncul(page, root, jeda=0.06):
    """Menampilkan kartu satu per satu (fade + geser) dan menyalakan denyutan."""
    fx = [c for c in walk(root) if getattr(c, "data", None) == "fx"]
    pulse = [c for c in walk(root) if str(getattr(c, "data", "")).startswith("pulse:")]

    def kerja():
        import time
        for c in fx:
            time.sleep(jeda)
            try:
                c.opacity, c.offset = 1, ft.Offset(0, 0)
                c.update()
            except Exception:
                continue
        for c in pulse:
            threading.Timer(float(c.data.split(":")[1]), c._mulai).start()
    page.run_thread(kerja)


def tampil(page, host, c):
    host.content = ft.Container(c, key=str(id(c)), expand=True)
    page.update()
    muncul(page, c)


def tema_gelap(page, aktif):
    page.bgcolor = GELAP if aktif else BG


def setup(page, judul, mode="terang"):
    page.title = judul
    page.padding = 0
    terapkan_tema(mode, page)
    tema_ft = lambda: ft.Theme(
        color_scheme_seed=BLUE, visual_density=ft.VisualDensity.COMFORTABLE,
        page_transitions=ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.CUPERTINO, ios=ft.PageTransitionTheme.CUPERTINO))
    page.theme, page.dark_theme = tema_ft(), tema_ft()
    page.window.width, page.window.height = 400, 800


def layar():
    return ft.AnimatedSwitcher(ft.Container(), transition=ft.AnimatedSwitcherTransition.FADE,
                               duration=220, reverse_duration=120, left=0, top=0, right=0, bottom=0)


# ── Struktur halaman ───────────────────────────────────────────────────────────
def header(judul, sub=None, kanan=None):
    isi = [ft.Text(judul, size=32, weight=TW.W_800, color=LABEL),
           *([ft.Text(sub, size=15, color=SECONDARY)] if sub else [])]
    baris = [ft.Column(isi, spacing=2, expand=True)]
    if kanan is not None:
        baris.append(kanan)
    return ft.Container(padding=ft.padding.only(left=M + 4, top=28, right=M + 4, bottom=12),
                        content=ft.Row(baris, vertical_alignment=ft.CrossAxisAlignment.CENTER))


def label_seksi(teks, kanan=None):
    r = [ft.Text(teks.upper(), size=13, color=SECONDARY, weight=TW.W_500)]
    if kanan is not None:
        r.append(kanan)
    return ft.Container(padding=ft.padding.only(left=M + 4, right=M, top=GAP + 4, bottom=0),
                        content=ft.Row(r, alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                       vertical_alignment=ft.CrossAxisAlignment.CENTER))


def body(*isi, spasi=GAP, bawah=32, atas=8):
    return ft.Container(padding=ft.padding.only(left=M, right=M, top=atas, bottom=bawah),
                        content=ft.Column(list(isi), spacing=spasi))


NAV_H = 92  # tinggi ruang untuk tab bar mengambang
KACA_BLUR = False  # blur eksperimental: di Flet 0.28 bisa dirender abu-abu/menutupi layar. Default: kaca tanpa blur


AMBANG_TARIK = 70       # piksel tarikan ke bawah agar memicu refresh
JEDA_SEGARKAN = 0.8     # detik indikator 'Memuat ulang…' terlihat sebelum layar dibangun ulang


def halaman(*isi, nav=True, bawah=None, segarkan=None):
    """Halaman bergulir. nav=True menyisakan ruang di bawah agar isi tidak tertutup tab bar mengambang.
    segarkan: fungsi tanpa argumen -> aktifkan 'tarik ke bawah untuk memuat ulang' (ala iOS)."""
    sisa = (NAV_H if bawah is None else bawah) if nav else 0
    kolom_ = ft.Column([*isi, *([ft.Container(height=sisa)] if sisa else [])], scroll=ft.ScrollMode.ALWAYS if segarkan else ft.ScrollMode.AUTO,
                       expand=True, spacing=0)
    if segarkan:
        ind = ft.Container(height=0, animate=anim(220), clip_behavior=ft.ClipBehavior.ANTI_ALIAS, alignment=ft.alignment.center,
                           content=ft.Row([ft.ProgressRing(width=18, height=18, stroke_width=2, color=BLUE),
                                           ft.Text("Memuat ulang…", size=13, color=SECONDARY)],
                                          alignment=ft.MainAxisAlignment.CENTER, spacing=10))
        kolom_.controls.insert(0, ind)
        st = {"os": 0.0, "jalan": False}

        def saat_scroll(e):
            t = e.event_type
            if t in ("start", "end"):
                st["os"] = 0.0
            px = e.pixels if e.pixels is not None else 0
            tarik = -px if px < 0 else 0          # platform 'bouncing' (iOS/macOS): posisi gulir negatif
            if t == "overscroll" and (e.overscroll or 0) < 0:   # platform 'clamping' (Android/Windows): notifikasi overscroll
                st["os"] += -e.overscroll
                tarik = max(tarik, st["os"])
            if tarik >= AMBANG_TARIK and not st["jalan"]:
                st["jalan"] = True
                ind.height = 52
                _coba(ind)
                try:
                    time.sleep(JEDA_SEGARKAN)
                    segarkan()
                finally:
                    st["jalan"] = False
        kolom_.on_scroll = saat_scroll
        kolom_.on_scroll_interval = 30
    return kolom_


def dengan_bar(isi, *tombol_bar, nav=False):
    """Halaman + tombol aksi di bawah. nav=True: tombol melayang tepat di atas tab bar, isi memudar di belakangnya."""
    if nav:
        bar = ft.Container(left=0, right=0, bottom=0, padding=ft.padding.only(left=M, right=M, top=24, bottom=NAV_H),
                           gradient=ft.LinearGradient(begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                                                      colors=[alpha(BG, 0), BG, BG], stops=[0, 0.35, 1]),
                           content=ft.Row(list(tombol_bar), spacing=10))
        return ft.Stack([ft.Container(isi, left=0, top=0, right=0, bottom=0), bar], expand=True)
    bar = ft.Container(padding=ft.padding.symmetric(horizontal=M, vertical=10), bgcolor=SURFACE,
                       border=ft.border.only(top=ft.BorderSide(0.5, SEPARATOR)),
                       content=ft.Row(list(tombol_bar), spacing=10))
    return ft.Column([isi, bar], expand=True, spacing=0)


def kartu(*isi, pad=16, spasi=12, fx=True):
    kw = dict(padding=pad, bgcolor=SURFACE, border_radius=16, content=ft.Column(list(isi), spacing=spasi),
              border=ft.border.all(1, KARTU_BORDER), shadow=ft.BoxShadow(blur_radius=8, color=BAYANGAN, offset=ft.Offset(0, 2)))
    return ft.Container(**(_fx(kw) if fx else kw))


def hero(tema, *isi, pad=20):
    kw = dict(padding=pad, border_radius=20, content=ft.Column(list(isi), spacing=8),
              gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=list(tema["grad"])),
              shadow=ft.BoxShadow(blur_radius=18, color=alpha(tema["grad"][1], 0.28), offset=ft.Offset(0, 6)))
    return ft.Container(**_fx(kw))


def baris(a, b, tebal=False, warna=None):
    warna = warna or LABEL
    w, sz = (TW.W_700, 17) if tebal else (TW.W_400, 15)
    return ft.Row([ft.Text(a, size=sz, weight=w, color=LABEL if tebal else SECONDARY),
                   ft.Text(b, size=sz, weight=w, color=warna, text_align=ft.TextAlign.RIGHT, expand=True)],
                  alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START)


def pemisah():
    return ft.Divider(height=1, thickness=0.5, color=SEPARATOR)


def badge(teks, warna, latar):
    return ft.Container(padding=ft.padding.symmetric(horizontal=10, vertical=3), border_radius=20, bgcolor=latar,
                        content=ft.Text(teks, size=12, weight=TW.W_600, color=warna))


def badge_status(st):
    w, b = STATUS_WARNA.get(st, (SECONDARY, FILL))
    return badge(st, w, b)


def kosong(ikon, judul, sub):
    return ft.Container(padding=ft.padding.symmetric(vertical=32), alignment=ft.alignment.center, content=ft.Column([
        ft.Icon(ikon, size=48, color=SEPARATOR),
        ft.Text(judul, size=17, weight=TW.W_600, color=LABEL),
        ft.Text(sub, size=14, color=SECONDARY, text_align=ft.TextAlign.CENTER)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6))


def peringatan(teks, judul=None, ikon=None, warna=None, latar=None, fx=False):
    """Kartu peringatan/info berwarna (default oranye)."""
    warna, latar = warna or ORANGE, latar or ORANGE_TINT
    isi = []
    if judul:
        isi.append(ft.Text(judul, size=15, weight=TW.W_700, color=LABEL))
    isi.append(ft.Text(teks, size=14, color=LABEL))
    kw = dict(padding=14, border_radius=14, bgcolor=latar, border=ft.border.all(1, alpha(warna, 0.35)),
              content=ft.Row([ft.Icon(ikon or ft.Icons.INFO_OUTLINE, color=warna, size=22),
                              ft.Column(isi, spacing=3, expand=True)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START))
    return ft.Container(**(_fx(kw) if fx else kw))


def ikon_bulat(ikon, tema, ukuran=40):
    return ft.Container(width=ukuran, height=ukuran, border_radius=ukuran / 2, bgcolor=tema["tint"],
                        alignment=ft.alignment.center, content=ft.Icon(ikon, color=tema["aksen"], size=ukuran * 0.5))


def avatar(row, tema, r=20, on_click=None):
    """Foto profil bulat; bila belum ada foto -> huruf pertama nama."""
    d = r * 2
    foto = (row or {}).get("foto")
    if foto:
        isi = ft.Image(src_base64=foto, width=d, height=d, fit=ft.ImageFit.COVER)
        bg = SURFACE
    else:
        nama = (row or {}).get("nama") or "?"
        isi = ft.Text(nama[:1].upper(), size=r * 0.85, weight=TW.W_700, color=tema.get("fg", "white"))
        bg = tema["aksen"]
    return ft.Container(width=d, height=d, border_radius=r, bgcolor=bg, alignment=ft.alignment.center,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=isi, on_click=on_click)


# ── Kontrol input ──────────────────────────────────────────────────────────────
def tombol(teks, ikon, aksi, tema, solid=True, destruktif=False):
    if destruktif:
        bg, fg = RED_TINT, RED
    elif solid:
        bg, fg = tema["tombol"], tema["fg"]
    else:
        bg, fg = FILL, LABEL
    return ft.FilledButton(teks, icon=ikon, on_click=aksi, height=50, expand=True,
                           style=ft.ButtonStyle(bgcolor={"": bg, "disabled": FILL}, color={"": fg, "disabled": SECONDARY},
                                                shape=ft.RoundedRectangleBorder(radius=12),
                                                text_style=ft.TextStyle(size=17, weight=TW.W_600)))


def kolom(label, **kw):
    return ft.TextField(label=label, filled=True, bgcolor=FIELD, border_radius=10, border_color="transparent",
                        focused_border_color=BLUE, label_style=ft.TextStyle(color=SECONDARY, size=15),
                        text_style=ft.TextStyle(color=LABEL, size=17), cursor_color=BLUE,
                        content_padding=ft.padding.symmetric(horizontal=16, vertical=14), **kw)


class Segmen(ft.Container):
    """Segmented control ala iOS yang RESPONSIF: selalu selebar wadahnya, setiap segmen sama lebar, sudut membulat,
    isi di tengah. (Kontrol bawaan CupertinoSlidingSegmentedButton memakai lebar isi sehingga terpotong di layar HP.)
    Dipakai di dalam ft.Row; kompatibel dengan pemanggilan lama: .on_change(e) dengan e.data = indeks, .selected_index."""

    def __init__(self, opsi, awal, on_ubah, tema=None):
        self.opsi, self.kunci, self.on_ubah = opsi, [o[0] for o in opsi], on_ubah
        self._idx = self.kunci.index(awal) if awal in self.kunci else 0
        self.tiles = []
        for n, o in enumerate(opsi):
            isi = [ft.Text(o[1], size=13, weight=TW.W_600, max_lines=1, no_wrap=True)]
            if len(o) > 2:
                isi.insert(0, ft.Icon(o[2], size=16))
            self.tiles.append(ft.Container(
                expand=True, height=36, border_radius=10, alignment=ft.alignment.center, animate=anim(180),
                padding=ft.padding.symmetric(horizontal=6), on_click=lambda e, n=n: self._klik(n),
                content=ft.Row(isi, alignment=ft.MainAxisAlignment.CENTER, spacing=6, tight=True)))
        super().__init__(content=ft.Row(self.tiles, spacing=2), expand=True, padding=3, border_radius=13, bgcolor=FILL)
        self._gaya()

    def _gaya(self):
        for n, t in enumerate(self.tiles):
            aktif = n == self._idx
            t.bgcolor = THUMB if aktif else ft.Colors.TRANSPARENT
            t.shadow = ft.BoxShadow(blur_radius=4, color="#22000000" if MODE == "terang" else "#00000000", offset=ft.Offset(0, 1)) if aktif else None
            for c in t.content.controls:
                c.color = LABEL if aktif else SECONDARY

    @property
    def selected_index(self):
        return self._idx

    @selected_index.setter
    def selected_index(self, n):
        self._idx = int(n)
        self._gaya()
        _coba(self)

    def _klik(self, n):
        if n == self._idx:
            return
        self.selected_index = n
        self.on_ubah(self.kunci[n])

    def on_change(self, e):
        """Kompatibel dengan event lama: e.data = indeks segmen yang dipilih."""
        self._klik(int(e.data))


def segmented(opsi, awal, on_ubah, tema=PENGGUNA):
    """opsi: [(kunci, label)] atau [(kunci, label, ikon)]. Letakkan di dalam ft.Row([...])."""
    return Segmen(opsi, awal, on_ubah, tema)


def pilihan(opsi, awal, on_ubah, tema=PENGGUNA, kolom_n=3):
    """Grid pilihan ikon+label selebar layar (baris berisi 3 kotak sama lebar)."""
    tiles, aksen = {}, tema["aksen"]

    def gaya(t, aktif):
        t.bgcolor = aksen if aktif else SURFACE
        t.border = ft.border.all(1.5, aksen) if aktif else ft.border.all(1, SEPARATOR)
        t.content.controls[0].color = tema.get("fg", "white") if aktif else SECONDARY
        t.content.controls[1].color = tema.get("fg", "white") if aktif else LABEL

    def set_(k):
        for kk, t in tiles.items():
            gaya(t, kk == k)
            if t.page:
                t.update()

    for k, ik, lb in opsi:
        t = ft.Container(expand=True, height=78, border_radius=12, animate=anim(), ink=True, alignment=ft.alignment.center,
                         padding=ft.padding.symmetric(horizontal=4),
                         on_click=lambda e, k=k: (set_(k), on_ubah(k)),
                         content=ft.Column([ft.Icon(I(ik), size=24),
                                            ft.Text(lb, size=12, text_align=ft.TextAlign.CENTER, weight=TW.W_500,
                                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)],
                                           alignment=ft.MainAxisAlignment.CENTER,
                                           horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4))
        tiles[k] = t
        gaya(t, k == awal)
    sel = list(tiles.values())
    baris_ = []
    for i in range(0, len(sel), kolom_n):
        chunk = sel[i:i + kolom_n]
        chunk += [ft.Container(expand=True)] * (kolom_n - len(chunk))
        baris_.append(ft.Row(chunk, spacing=8))
    return ft.Column(baris_, spacing=8), set_


def konfirmasi(page, judul, pesan, label, aksi, destruktif=False, batal="Batal"):
    dlg = ft.CupertinoAlertDialog(title=ft.Text(judul), content=ft.Text(pesan))

    def ya(e):
        page.close(dlg)
        aksi()
    dlg.actions = [ft.CupertinoDialogAction(batal, on_click=lambda e: page.close(dlg)),
                   ft.CupertinoDialogAction(label, is_destructive_action=destruktif, is_default_action=not destruktif, on_click=ya)]
    page.open(dlg)


def input_dialog(page, judul, pesan, label, saat_ok, teks_ok="Simpan", teks_lewat="Lewati", saat_lewat=None, angka=False):
    """Dialog iOS dengan satu kolom isian."""
    isi = kolom(label, keyboard_type=ft.KeyboardType.NUMBER if angka else ft.KeyboardType.TEXT, autofocus=True)
    dlg = ft.CupertinoAlertDialog(title=ft.Text(judul), content=ft.Column([ft.Text(pesan), isi], tight=True, spacing=10))

    def ok(e):
        page.close(dlg)
        saat_ok(isi.value or "")

    def lewat(e):
        page.close(dlg)
        saat_lewat and saat_lewat()
    dlg.actions = [ft.CupertinoDialogAction(teks_lewat, on_click=lewat),
                   ft.CupertinoDialogAction(teks_ok, is_default_action=True, on_click=ok)]
    page.open(dlg)


def snack(page, teks):
    page.open(ft.SnackBar(ft.Text(teks, color=LABEL), bgcolor=SURFACE, behavior=ft.SnackBarBehavior.FLOATING,
                          margin=ft.margin.only(left=M, right=M, bottom=M)))


class NavFlotan:
    """Tab bar mengambang berbentuk kapsul ala iOS: latar putih tembus pandang + blur,
    garis tepi tipis terang, bayangan lembut, dan 'pil' penanda tab aktif."""

    def __init__(self, tema, saat_pilih):
        self.tema, self.saat_pilih, self.idx, self.tiles = tema, saat_pilih, 0, []
        self.baris = ft.Row(spacing=4, alignment=ft.MainAxisAlignment.SPACE_AROUND)
        # Lapisan dalam (blur) dibungkus wadah luar berukuran tetap supaya efek blur TIDAK melebar menutupi layar.
        self.dalam = ft.Container(expand=True, padding=5, border_radius=33, content=self.baris,
                                  blur=ft.Blur(20, 20) if KACA_BLUR else None)
        self.kontrol = ft.Container(
            left=20, right=20, bottom=12, height=66, visible=False, border_radius=33,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=self.dalam)
        self.tema_ulang(tema)

    def tema_ulang(self, tema=None):
        """Menerapkan warna palet aktif (dipanggil saat ganti terang/gelap)."""
        self.tema = tema or self.tema
        gelap = MODE == "gelap"
        self.dalam.bgcolor = alpha(SURFACE, 0.72 if KACA_BLUR else (0.94 if gelap else 0.9))
        self.dalam.border = ft.border.all(1, SEPARATOR if gelap else alpha("white", 0.9))
        self.kontrol.shadow = ft.BoxShadow(blur_radius=28, color="#66000000" if gelap else "#2A000000", offset=ft.Offset(0, 10))
        if self.tiles:
            self._gaya()
        if self.kontrol.page:
            self.kontrol.update()

    def atur(self, items):
        """items: [(ikon, ikon_aktif, label)]"""
        self.items, self.tiles = items, []
        for n, (ik, ik_a, lb) in enumerate(items):
            t = ft.Container(expand=True, border_radius=28, animate=anim(220), on_click=lambda e, n=n: self.klik(n),
                             alignment=ft.alignment.center,
                             content=ft.Column([ft.Icon(ik, size=24), ft.Text(lb, size=10, weight=TW.W_600)],
                                               alignment=ft.MainAxisAlignment.CENTER,
                                               horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1))
            self.tiles.append(t)
        self.baris.controls = self.tiles
        self._gaya()
        if self.kontrol.page:
            self.kontrol.update()

    def _gaya(self):
        for n, t in enumerate(self.tiles):
            aktif = n == self.idx
            ik, ik_a, _ = self.items[n]
            t.bgcolor = alpha(self.tema["aksen"], 0.22 if MODE == "gelap" else 0.14) if aktif else ft.Colors.TRANSPARENT
            t.content.controls[0].name = ik_a if aktif else ik
            t.content.controls[0].color = t.content.controls[1].color = self.tema["aksen"] if aktif else SECONDARY

    def pilih(self, i):
        self.idx = i
        self._gaya()
        if self.kontrol.page:
            self.kontrol.update()

    def klik(self, i):
        self.pilih(i)
        self.saat_pilih(i)

    def tampil(self, ya):
        self.kontrol.visible = ya
        if self.kontrol.page:
            self.kontrol.update()


# ── Radar pencarian berdenyut ──────────────────────────────────────────────────
def radar(ikon, warna, ukuran=240, cincin=True, pusat_bg=None, pusat_ikon="white"):
    """Cincin gelombang yang memancar + ikon di tengah. Pada latar gelap: warna='white',
    pusat_bg='white', pusat_ikon=BLUE."""
    pusat_bg = pusat_bg or warna
    dia_c = 96
    kontrol = []
    if cincin:
        for tunda in (0.0, 0.5, 1.0):
            d = ukuran * 0.5
            ring = ft.Container(width=d, height=d, left=(ukuran - d) / 2, top=(ukuran - d) / 2, border_radius=d / 2,
                                bgcolor=alpha(warna, 0.14), border=ft.border.all(1.5, warna))
            kontrol.append(denyut(ring, 0.6, 0.0, besar=1.9, ms=1600, tunda=tunda))
    inti = ft.Container(width=dia_c, height=dia_c, left=(ukuran - dia_c) / 2, top=(ukuran - dia_c) / 2,
                        border_radius=dia_c / 2, bgcolor=pusat_bg, alignment=ft.alignment.center,
                        shadow=ft.BoxShadow(blur_radius=20, color="#40000000", offset=ft.Offset(0, 6)),
                        content=ft.Icon(ikon, size=46, color=pusat_ikon))
    kontrol.append(denyut(inti, 1, 1, besar=1.07, ms=900) if cincin else inti)
    return ft.Stack(kontrol, width=ukuran, height=ukuran)


# ── Masuk / daftar ─────────────────────────────────────────────────────────────
def auth(page, peran, nama_app, tagline, tema, saat_masuk, bengkel=None):
    """bengkel: objek pemilih lokasi (peta.PemilihLokasi) khusus daftar akun mitra. Selama lokasi belum
    dipilih, kolom data akun terkunci agar lokasi dipilih TERLEBIH DAHULU."""
    mode_daftar = [False]
    email = kolom("Email", keyboard_type=ft.KeyboardType.EMAIL)
    pw = kolom("Kata sandi", password=True, can_reveal_password=True)
    nama = kolom("Nama lengkap" if peran == "pengguna" else "Nama mekanik / bengkel", visible=False)
    telp = kolom("No. HP", visible=False, keyboard_type=ft.KeyboardType.PHONE)
    err = ft.Text("", color=RED, size=13, visible=False)
    aksi = tombol("Masuk", None, None, tema)
    petunjuk = ft.Text("Akun demo: joko@otofix.id / mitra123", size=13, color=SECONDARY, visible=(peran == "mitra"))
    kunci = ft.Text("Pilih lokasi bengkel terlebih dahulu untuk melanjutkan pendaftaran.", size=13, color=ORANGE, visible=False)
    blok = None
    if bengkel:
        blok = ft.Column([
            ft.Row([ft.Icon(ft.Icons.STORE, color=tema["aksen"], size=20),
                    ft.Text("Langkah 1 · Lokasi bengkel", size=16, weight=TW.W_700, color=LABEL)], spacing=8),
            ft.Text("Pesanan hanya ditawarkan jika pemesan berada dalam radius 10 km dari bengkel Anda.", size=13, color=SECONDARY),
            bengkel.kontrol, ft.Divider(height=1, color=SEPARATOR),
            ft.Text("Langkah 2 · Data akun", size=16, weight=TW.W_700, color=LABEL)], visible=False, spacing=10)

    def terapkan():
        terkunci = bool(bengkel) and mode_daftar[0] and not bengkel.siap()
        for f in (nama, telp, email, pw):
            f.disabled = terkunci
        aksi.disabled = terkunci
        kunci.visible = terkunci

    def pilih(k):
        d = k == "daftar"
        mode_daftar[0] = d
        nama.visible = telp.visible = d
        if blok:
            blok.visible = d
        err.visible = False
        aksi.text = "Buat Akun" if d else "Masuk"
        petunjuk.visible = (peran == "mitra") and not d
        terapkan()
        page.update()

    def tampil_err(m):
        err.value, err.visible = m, True
        page.update()

    def kirim(e=None):
        err.visible = False
        if bengkel and mode_daftar[0] and not bengkel.siap():
            return tampil_err("Pilih lokasi bengkel terlebih dahulu.")
        if not email.value or not pw.value:
            return tampil_err("Isi email dan kata sandi.")
        if mode_daftar[0]:
            ekstra = bengkel.data() if bengkel else {}
            ok, msg = db.daftar(peran, nama.value or "", email.value, telp.value or "", pw.value, **ekstra)
            if not ok:
                return tampil_err(msg)
        row = db.masuk(peran, email.value, pw.value)
        if not row:
            return tampil_err("Email atau kata sandi salah.")
        saat_masuk(row)

    if bengkel:
        bengkel.on_ubah = lambda: (terapkan(), page.update())
    aksi.on_click = kirim
    pw.on_submit = kirim
    logo = ft.Container(width=84, height=84, border_radius=20, alignment=ft.alignment.center,
                        gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=list(tema["grad"])),
                        shadow=ft.BoxShadow(blur_radius=18, color=alpha(tema["grad"][1], 0.3), offset=ft.Offset(0, 6)),
                        content=ft.Icon(ft.Icons.BUILD_CIRCLE, color="white", size=48))
    return ft.Column([
        ft.Container(padding=ft.padding.only(top=40, bottom=GAP), alignment=ft.alignment.center, content=ft.Column([
            denyut(logo, 1, 1, besar=1.05, ms=1800),
            ft.Text(nama_app, size=30, weight=TW.W_800, color=LABEL),
            ft.Text(tagline, size=15, color=SECONDARY, text_align=ft.TextAlign.CENTER)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)),
        body(ft.Row([segmented([("masuk", "Masuk"), ("daftar", "Daftar")], "masuk", pilih, tema)],
                    alignment=ft.MainAxisAlignment.CENTER),
             kartu(*([blok] if blok else []), nama, telp, email, pw, err, petunjuk, kunci, ft.Row([aksi]), pad=20)),
    ], scroll=ft.ScrollMode.AUTO, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


# ── Profil (dengan foto) ───────────────────────────────────────────────────────
_PICKER = {}


def _picker(page, saat_pilih):
    fp = _PICKER.get(id(page))
    if fp is None:
        fp = ft.FilePicker()
        page.overlay.append(fp)
        page.update()
        _PICKER[id(page)] = fp
    fp.on_result = saat_pilih
    return fp


def profil(page, row, tema, simpan, keluar, info="", segarkan=None, ekstra=None, mode_tema=None, saat_tema=None):
    """segarkan(): dipanggil setelah foto diubah agar layar dibangun ulang."""
    nama = kolom("Nama", value=row["nama"])
    telp = kolom("No. HP", value=row["telp"] or "", keyboard_type=ft.KeyboardType.PHONE)

    def hasil_pilih(e):
        if not e.files:
            return
        try:
            db.ubah_foto(row["id"], db.foto_dari_file(e.files[0].path))
        except (ValueError, TypeError, OSError) as ex:
            return snack(page, str(ex) if isinstance(ex, ValueError) else "Foto tidak dapat dibaca. Coba foto lain.")
        snack(page, "Foto profil diperbarui")
        segarkan and segarkan()

    def ganti_foto(e=None):
        _picker(page, hasil_pilih).pick_files(dialog_title="Pilih foto profil", file_type=ft.FilePickerFileType.IMAGE,
                                              allow_multiple=False)

    def hapus_foto():
        db.ubah_foto(row["id"], None)
        segarkan and segarkan()

    pw_lama = kolom("Kata sandi lama", password=True, can_reveal_password=True)
    pw_baru = kolom("Kata sandi baru", password=True, can_reveal_password=True)
    pw_ulang = kolom("Ulangi kata sandi baru", password=True, can_reveal_password=True)
    pw_err = ft.Text("", color=RED, size=13, visible=False)

    def ubah_pw(e):
        pw_err.visible = True
        if not pw_lama.value:
            pw_err.value = "Masukkan kata sandi lama terlebih dahulu."
        elif (pw_baru.value or "") != (pw_ulang.value or ""):
            pw_err.value = "Konfirmasi kata sandi baru tidak sama."
        else:
            ok, msg = db.ubah_password(row["id"], pw_lama.value, pw_baru.value)
            if ok:
                pw_err.visible = False
                for f in (pw_lama, pw_baru, pw_ulang):
                    f.value = ""
                snack(page, "Kata sandi berhasil diubah")
            else:
                pw_err.value = msg
        page.update()

    def kirim(e):
        if not (nama.value or "").strip():
            nama.error_text = "Nama tidak boleh kosong"
            page.update()
            return
        nama.error_text = None
        simpan(nama.value, telp.value or "")

    kamera = ft.Container(width=30, height=30, border_radius=15, bgcolor=tema["aksen"], right=0, bottom=0,
                          alignment=ft.alignment.center, border=ft.border.all(2.5, SURFACE),
                          content=ft.Icon(ft.Icons.CAMERA_ALT, size=14, color=tema.get("fg", "white")))
    foto = ft.Container(on_click=ganti_foto, width=96, height=96,
                        content=ft.Stack([avatar(row, tema, 44), kamera], width=96, height=96))
    aksi_foto = [ft.TextButton("Ubah foto", on_click=ganti_foto, style=ft.ButtonStyle(color=tema["aksen"]))]
    if row.get("foto"):
        aksi_foto.append(ft.TextButton("Hapus", on_click=lambda e: konfirmasi(
            page, "Hapus foto profil?", "Foto akan diganti dengan inisial nama.", "Hapus", hapus_foto, True),
            style=ft.ButtonStyle(color=RED)))
    return halaman(
        header("Profil", info or None),
        body(
            kartu(ft.Row([foto], alignment=ft.MainAxisAlignment.CENTER),
                  ft.Text(row["nama"], size=20, weight=TW.W_700, color=LABEL, text_align=ft.TextAlign.CENTER),
                  ft.Text(row["email"], size=14, color=SECONDARY, text_align=ft.TextAlign.CENTER),
                  ft.Row(aksi_foto, alignment=ft.MainAxisAlignment.CENTER, spacing=4), pad=20, spasi=6),
            *(ekstra or []),
            *([label_seksi("Tampilan"), kartu(
                ft.Row([ft.Icon(ft.Icons.DARK_MODE_OUTLINED if mode_tema == "gelap" else ft.Icons.LIGHT_MODE_OUTLINED,
                                color=tema["aksen"], size=22),
                        ft.Text("Mode tampilan", size=16, weight=TW.W_600, color=LABEL, expand=True)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                ft.Row([segmented([("terang", "Terang", ft.Icons.LIGHT_MODE), ("gelap", "Gelap", ft.Icons.DARK_MODE)],
                                  mode_tema, saat_tema, tema)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("Mode gelap memakai latar hitam yang nyaman di mata; semua isi tetap terbaca.", size=13, color=SECONDARY),
            )] if saat_tema else []),
            label_seksi("Informasi pribadi"),
            kartu(nama, telp, ft.Row([tombol("Simpan Perubahan", None, kirim, tema)])),
            label_seksi("Keamanan"),
            kartu(ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, color=tema["aksen"], size=20),
                          ft.Text("Ubah kata sandi", size=16, weight=TW.W_600, color=LABEL, expand=True)], spacing=10),
                  ft.Text("Untuk keamanan, masukkan kata sandi lama terlebih dahulu.", size=13, color=SECONDARY),
                  pw_lama, pw_baru, pw_ulang, pw_err, ft.Row([tombol("Ubah Kata Sandi", None, ubah_pw, tema)])),
            kartu(ft.Row([tombol("Keluar", ft.Icons.LOGOUT, lambda e: konfirmasi(
                page, "Keluar dari akun?", "Anda perlu masuk lagi untuk memakai aplikasi.", "Keluar", keluar, True),
                tema, destruktif=True)])),
        ))


# ── Rating ─────────────────────────────────────────────────────────────────────
TEKS_BINTANG = {0: "Ketuk bintang untuk menilai", 1: "Sangat buruk", 2: "Kurang baik", 3: "Cukup", 4: "Baik", 5: "Sangat baik"}


def _coba(c):
    try:
        c.update()
    except Exception:
        pass


def bintang_baris(rata, ukuran=16):
    """Deretan 5 bintang (mendukung setengah bintang) untuk nilai rata-rata."""
    isi = []
    for i in range(1, 6):
        if rata is not None and rata >= i - 0.25:
            ik, w = ft.Icons.STAR_ROUNDED, STAR
        elif rata is not None and rata >= i - 0.75:
            ik, w = ft.Icons.STAR_HALF_ROUNDED, STAR
        else:
            ik, w = ft.Icons.STAR_BORDER_ROUNDED, SEPARATOR
        isi.append(ft.Icon(ik, size=ukuran, color=w))
    return ft.Row(isi, spacing=0, tight=True)


def rating_ringkas(ring, ukuran=14, warna_teks=None, warna_sub=None, kosong="Belum ada rating"):
    """Ringkasan: ★ 4,8 (12). ring = hasil db.rating_mekanik / db.rating_pelanggan."""
    warna_teks, warna_sub = warna_teks or LABEL, warna_sub or SECONDARY
    if not ring or not ring["jumlah"]:
        return ft.Row([ft.Icon(ft.Icons.STAR_BORDER_ROUNDED, size=ukuran + 2, color=warna_sub),
                       ft.Text(kosong, size=ukuran - 1, color=warna_sub)], spacing=4, tight=True)
    return ft.Row([ft.Icon(ft.Icons.STAR_ROUNDED, size=ukuran + 3, color=STAR),
                   ft.Text(f"{ring['rata']:.1f}".replace(".", ","), size=ukuran, weight=TW.W_700, color=warna_teks),
                   ft.Text(f"({ring['jumlah']} ulasan)", size=ukuran - 1, color=warna_sub)], spacing=4, tight=True)


def daftar_ulasan(ring, judul="Ulasan terbaru"):
    """Beberapa komentar terakhir (tanpa nama pemberi). None bila belum ada komentar."""
    if not ring or not ring["ulasan"]:
        return None
    baris_ = [ft.Text(judul, size=13, weight=TW.W_600, color=SECONDARY)]
    for r in ring["ulasan"]:
        baris_.append(ft.Column([
            ft.Row([bintang_baris(r["bintang"], 13), ft.Text(r["waktu"], size=11, color=SECONDARY)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(r["komentar"], size=14, color=LABEL)], spacing=2))
    return ft.Column(baris_, spacing=8)


def rating_diberikan(r, judul="Rating Anda"):
    """Tampilan setelah rating dikirim."""
    isi = [ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=GREEN, size=20),
                   ft.Text(judul, size=15, weight=TW.W_600, color=LABEL, expand=True), bintang_baris(r["bintang"], 18)],
                  vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)]
    if r.get("komentar"):
        isi.append(ft.Text(r["komentar"], size=14, color=SECONDARY))
    return ft.Column(isi, spacing=6)


def form_rating(tema, saat_kirim, judul=None, tombol_teks="Kirim Rating"):
    """Bintang interaktif + komentar opsional. saat_kirim(bintang:int, komentar:str)."""
    n = [0]
    ikon = [ft.Icon(ft.Icons.STAR_BORDER_ROUNDED, size=40, color=SEPARATOR) for _ in range(5)]
    label = ft.Text(TEKS_BINTANG[0], size=14, color=SECONDARY, text_align=ft.TextAlign.CENTER)
    komentar = kolom("Komentar (opsional)", multiline=True, min_lines=2, max_lines=4, max_length=200)
    btn = tombol(tombol_teks, ft.Icons.SEND_ROUNDED, None, tema)
    btn.disabled = True

    def pilih(k):
        n[0] = k
        for i, ic in enumerate(ikon):
            ic.name = ft.Icons.STAR_ROUNDED if i < k else ft.Icons.STAR_BORDER_ROUNDED
            ic.color = STAR if i < k else SEPARATOR
        label.value, label.color = TEKS_BINTANG[k], LABEL
        btn.disabled = False
        for c in (*ikon, label, btn):
            _coba(c)

    baris_bintang = ft.Row([ft.Container(ic, data="bintang", on_click=lambda e, k=i + 1: pilih(k), padding=2)
                            for i, ic in enumerate(ikon)], alignment=ft.MainAxisAlignment.CENTER, spacing=2)
    btn.on_click = lambda e: saat_kirim(n[0], komentar.value or "") if n[0] else None
    return ft.Column([*([ft.Text(judul, size=17, weight=TW.W_700, color=LABEL, text_align=ft.TextAlign.CENTER)] if judul else []),
                      baris_bintang, label, komentar, ft.Row([btn])],
                     spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

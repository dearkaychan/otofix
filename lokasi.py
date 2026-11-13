"""Lokasi & waktu perangkat: GPS (bila tersedia), nama tempat, jam sekarang."""
import os, re, json, time, urllib.request
import flet as ft
from db import BASE_LAT, BASE_LON

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
FALLBACK_NAMA = "Pusat Kota Surakarta (lokasi perkiraan)"


def sekarang():
    t = time.localtime()
    return dict(jam=t.tm_hour, label=f"{HARI[t.tm_wday]}, {t.tm_mday} {BULAN[t.tm_mon - 1]} · {t.tm_hour:02d}:{t.tm_min:02d}")


def eta_menit(jarak_km):
    """Perkiraan waktu tiba (kecepatan rata-rata 25 km/jam + 3 menit persiapan)."""
    return max(3, round(jarak_km / 25 * 60) + 3)


class Pelacak:
    """Membungkus ft.Geolocator. Bila GPS tidak ada (mis. laptop tanpa GPS / izin ditolak),
    memakai lokasi simulasi pusat kota Surakarta agar aplikasi tetap bisa dicoba."""

    def __init__(self, page):
        self.page, self.gl = page, None

    def posisi(self, timeout=8):
        """-> (lat, lon, akurat). akurat=False berarti memakai lokasi simulasi."""
        if os.environ.get("OTOFIX_OFFLINE"):
            return BASE_LAT, BASE_LON, False
        try:
            if self.gl is None:
                self.gl = ft.Geolocator()
                self.page.overlay.append(self.gl)
                self.page.update()
            try:
                self.gl.request_permission(wait_timeout=timeout)
            except Exception:
                pass
            p = self.gl.get_current_position(accuracy=ft.GeolocatorPositionAccuracy.LOW, wait_timeout=timeout)
            if p is not None and p.latitude is not None and p.longitude is not None:
                return float(p.latitude), float(p.longitude), True
        except Exception:
            pass
        return BASE_LAT, BASE_LON, False


def nama_tempat(lat, lon, akurat):
    """Nama jalan/daerah dari OpenStreetMap Nominatim (butuh internet); gagal -> teks cadangan."""
    if not akurat:
        return FALLBACK_NAMA
    if not os.environ.get("OTOFIX_OFFLINE"):
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=17&accept-language=id&lat={lat}&lon={lon}"
            req = urllib.request.Request(url, headers={"User-Agent": "OtoFix/1.0 (proyek kuliah)"})
            with urllib.request.urlopen(req, timeout=5) as r:
                a = json.load(r).get("address", {})
            bagian = [a[k] for k in ("road", "neighbourhood", "suburb", "village", "city_district", "city", "town", "county") if a.get(k)]
            if bagian:
                return ", ".join(dict.fromkeys(bagian[:3]))
        except Exception:
            pass
    return f"{lat:.5f}, {lon:.5f}"


def geser(lat, lon, tlat, tlon, km):
    """Menggeser titik (lat, lon) sejauh km ke arah (tlat, tlon); berhenti tepat di tujuan. Dipakai untuk simulasi pergerakan."""
    from engine import jarak_haversine
    d = jarak_haversine(lat, lon, tlat, tlon)
    if d <= km or d == 0:
        return tlat, tlon
    f = km / d
    return lat + (tlat - lat) * f, lon + (tlon - lon) * f


def telp_uri(nomor):
    """Nomor HP -> 'tel:+62…' (None bila tidak valid). Contoh: '0812-3456-7890' -> 'tel:+6281234567890'."""
    n = re.sub(r"[^\d+]", "", nomor or "")
    if n.startswith("+"):
        d = n[1:]
    elif n.startswith("0"):
        d = "62" + n[1:]
    else:
        d = n
    if not d.isdigit() or not 9 <= len(d) <= 15:
        return None
    return "tel:+" + d


def umur_teks(detik):
    return "baru saja" if detik < 5 else f"{int(detik)} detik lalu" if detik < 90 else f"{int(detik // 60)} menit lalu"

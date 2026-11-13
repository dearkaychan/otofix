# OtoFix

Dua aplikasi Flet (UI gaya iOS) yang berbagi satu database SQLite (`otofix.db`, dibuat otomatis).

## Menjalankan
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app_pengguna.py     # aplikasi pengendara (daftar sendiri)
python app_mitra.py        # aplikasi mitra
python test_smoke.py       # uji alur utama tanpa GUI
```
Akun mitra demo: `joko@otofix.id`, `dimas@otofix.id`, `eko@otofix.id` — sandi `mitra123`.
Jalankan kedua aplikasi bersamaan untuk mencoba alur: pesan -> mitra menerima -> selesai.

## Fitur utama
- Lokasi pengguna dibaca dari GPS perangkat (nama jalan via OpenStreetMap) dan jam diambil dari jam perangkat.
  Bila GPS/izin tidak tersedia (mis. laptop), dipakai lokasi simulasi pusat kota Surakarta.
- Tekan **Cari Mekanik Terdekat** -> halaman animasi pencarian -> hasil & rincian biaya -> pesan.
- Mitra melihat peta lokasi pemesan di kartu pesanan (ketuk untuk memperbesar; butuh internet untuk tile peta).
- Pengguna dan mitra bisa mengganti foto profil (tab Profil).
- Daftar akun mitra **wajib memilih lokasi bengkel lebih dulu** (ketuk peta atau pakai GPS); kolom data akun baru terbuka setelah lokasi dipilih. Lokasi bisa diubah kapan saja di Profil. Pesanan hanya ditawarkan ke bengkel yang berjarak **<= 10 km** dari pemesan.
- Rating dua arah setelah pesanan **Selesai**: pengguna menilai mekanik (bintang 1-5 + komentar), mekanik menilai pelanggan.
  Rating mekanik terlihat oleh pengguna yang pesanannya ditawarkan/ditangani mekanik itu; rating pelanggan HANYA terlihat di aplikasi mitra
  (mekanik yang mendapat pelanggan tsb). Aplikasi pengguna tidak menampilkan rating dirinya.
- Mode **Terang / Gelap** di Profil kedua aplikasi (tersimpan per aplikasi). Mode gelap memakai latar hitam murni, kartu #1C1C1E, teks putih lembut.
- Pesanan hanya ditawarkan ke bengkel yang **online** (aplikasinya terbuka & login) DAN berjarak <= 10 km, terdekat lebih dulu. Tidak ada cadangan ke bengkel offline/jauh: bila tidak ada, pengguna melihat "Tidak ada bengkel tersedia/terdekat" beserta peringatan.
- **Tarik ke bawah untuk memuat ulang** di Beranda & Pesanan (pengguna) serta Radar & Pendapatan (mitra).
- Tab bar bawah berbentuk kapsul mengambang dengan efek kaca (blur).

## Fitur tambahan
- **Chat** pengguna <-> montir untuk pesanan yang sedang berjalan (muncul setelah pengguna mendapat montir; ditutup, tapi masih bisa dibaca, setelah selesai).
- **Kendaraan saya**: pilih jenis/merek/model dari database ±700 model motor & mobil (ada pencarian, toleran typo, bisa isi manual), tersimpan di profil.
- **Derek** layanan tersendiri (hanya mobil, tidak tampil untuk motor). Kategori **Lainnya** tidak punya estimasi harga: harga disepakati lewat chat
  (mitra bisa mencatat harga kesepakatan saat menandai selesai).
- Pesanan **ditolak** montir tampil di layar pengguna; bila semua menolak -> status "Ditolak". Tidak ada bengkel dalam 10 km -> "Tidak ada bengkel terdekat".
- **Pelacakan langsung**: setelah mitra menyetujui pesanan, pengguna melihat peta posisi mekanik yang bergerak (jarak, perkiraan tiba, "Diperbarui N detik lalu").
  Mitra membagikan posisi tiap 3 detik selama ada pesanan aktif: GPS perangkat bila ada, bila tidak (mis. laptop) posisinya **disimulasikan** bergerak dari bengkel ke pemesan
  agar bisa didemokan. Hanya pemilik pesanan yang bisa melihat, dan posisi dihapus saat pesanan selesai. Pelacakan GPS hanya berjalan selama aplikasi mitra terbuka (tanpa layanan latar belakang).
- **Telepon** dari ruang chat (ikon telepon di header, hanya selama pesanan berjalan): membuka dialer perangkat ke nomor HP lawan bicara (`tel:`) setelah konfirmasi.
- **Ubah kata sandi** (Profil) wajib memasukkan kata sandi lama.
- **Asisten AI** beranimasi. Memakai LLM bila ada API key, jika tidak memakai analisis offline berbobot (`ai.py`):
  `ANTHROPIC_API_KEY` (Claude) | `GEMINI_API_KEY` | `OTOFIX_AI_KEY` (+ `OTOFIX_AI_URL`/`OTOFIX_AI_MODEL` untuk OpenAI/Groq/OpenRouter).
  Paksa dengan `OTOFIX_AI_PROVIDER=anthropic|gemini|openai|off`. Jangan menaruh API key di APK yang dibagikan; untuk produksi panggil lewat backend.

## Catatan penting
- `requirements.txt` memakai `flet==0.28.3` (sengaja dipin). Flet 1.x menghapus API yang dipakai kode ini.
- Build APK: `flet build apk --module-name app_pengguna` dan `flet build apk --module-name app_mitra`.
- Android: izin lokasi & internet perlu diaktifkan di `pyproject.toml` (`[tool.flet.android.permission]`: `android.permission.ACCESS_FINE_LOCATION`, `android.permission.INTERNET`).
- `db.py` hanya simulasi backend; ganti dengan API/Firebase untuk produksi.
# otofix

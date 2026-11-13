"""Diagnosa keluhan kendaraan.

Urutan penyedia (otomatis, sesuai environment variable yang tersedia):
  1. Claude (Anthropic)   : ANTHROPIC_API_KEY            (model: OTOFIX_AI_MODEL, default claude-haiku-5-5)
  2. Google Gemini        : GEMINI_API_KEY / GOOGLE_API_KEY (model default gemini-2.0-flash)
  3. API kompatibel OpenAI (OpenAI/Groq/OpenRouter/dll): OTOFIX_AI_KEY atau OPENAI_API_KEY
                            (OTOFIX_AI_URL, OTOFIX_AI_MODEL opsional)
  4. Tanpa key / gagal / offline -> analisis offline berbobot (analisis_offline), selalu tersedia.
Paksa penyedia dengan OTOFIX_AI_PROVIDER = anthropic | gemini | openai | off.

PENTING: menaruh API key di dalam aplikasi yang dibagikan tidak aman. Untuk produksi, panggil LLM lewat
backend Anda sendiri (key disimpan di server). Hanya stdlib yang dipakai, jadi tidak ada dependensi baru."""
import os, re, json, urllib.request
from engine import KATEGORI

DEFINISI = {
    "ban_bocor": "ban kempes/bocor/tertusuk paku/pecah, angin ban habis",
    "aki_soak": "aki soak/lemah: starter tidak berputar atau hanya 'klik', lampu redup, tidak mau hidup karena listrik lemah",
    "bensin_habis": "kehabisan bensin/BBM",
    "mesin_overheat": "mesin panas/overheat, temperatur naik, asap/uap, mesin mati/brebet/kasar/knocking, oli habis",
    "kelistrikan": "korsleting, sekring/sikring putus, kabel, lampu/klakson/sein mati, bau gosong, kiprok/regulator, ECU/sensor",
    "rem_blong": "rem blong/tidak pakem/pedal rem dalam, minyak rem bocor/habis, kampas habis",
    "bodi_rusak": "kecelakaan ringan, ditabrak/jatuh, bodi/bumper/spion rusak, stang bengkok",
    "rantai_putus": "rantai/gir putus atau kendor, CVT/vanbelt putus, kopling selip, tenaga tidak tersalur ke roda",
    "lainnya": "tidak termasuk kategori di atas atau gejala tidak jelas",
}

# ── Analisis offline berbobot ───────────────────────────────────────────────────
ATURAN = {
    "ban_bocor": [(r"\bban\b", 3), (r"kempes|kempis|gembos|kebocoran ban|bocor halus", 4),
                  (r"\bpaku\b|tertusuk|tusuk|tubeless|pentil|tambal|pecah ban|ban pecah|meletus|\bletus", 3),
                  (r"angin (ban )?(habis|berkurang|kurang)", 3), (r"\bvelg\b|peleg", 1)],
    "aki_soak": [(r"\baki\b|\baccu\b|akumulator", 4), (r"starter|distarter|electric starter", 2),
                 (r"klik[- ]?klik|ngeklik|bunyi klik|cetek", 3), (r"lampu (redup|berkedip|kedip)|redup", 2),
                 (r"(tidak|gak|nggak|ga|ngga|enggak|belum|susah|sulit) (mau |bisa )?(hidup|nyala|menyala|distarter|start)", 2),
                 (r"jumper|jump ?start|strum", 3), (r"klakson (lemah|pelan)", 1)],
    "bensin_habis": [(r"bensin|bbm|pertalite|pertamax|bahan bakar", 2),
                     (r"(bensin|bbm|tangki|pertalite|pertamax)(\W+\w+){0,3}\W+(habis|abis|kosong|menipis|tipis)"
                      r"|kehabisan (bensin|bbm)|(habis|abis|kosong) (bensin|bbm)", 5),
                     (r"indikator (bensin|bbm)|lampu (bensin|bbm)|jarum bensin|\bfuel\b", 3)],
    "mesin_overheat": [(r"overheat|over heat|terlalu panas|panas banget|mesin panas|temperatur|suhu (naik|tinggi)|jarum (suhu|temp)", 4),
                       (r"radiator|coolant|air radiator|kipas radiator|\buap\b|mengepul", 3), (r"\basap\b|ngebul", 2),
                       (r"kletek|klotok|knocking|ngelitik|mesin kasar|brebet|ngempos|tarikan (berat|lemot)", 3),
                       (r"\bmesin\b", 2), (r"oli (habis|bocor|menyala)|lampu oli|piston|\bklep\b|head ?gasket|gasket", 3),
                       (r"mati (mendadak|saat digas|di jalan|sendiri)", 2)],
    "kelistrikan": [(r"korslet|konslet|konsleting|sekring|sikring|\bfuse\b|\bkabel\b|kiprok|regulator|\bcdi\b|\becu\b|relay|relai|sensor", 4),
                    (r"lampu (mati|depan|belakang|sein|rem|utama|padam)|\bsein\b|klakson|wiper|power window|central lock|speedometer|spido|dashboard", 3),
                    (r"bau gosong|terbakar|percikan|konslet|listrik", 3)],
    "rem_blong": [(r"\brem\b", 3), (r"blong|\bblank\b|tidak pakem|kurang pakem|nggak pakem|gak pakem|ga pakem|tidak ngerem|nggak ngerem|gak ngerem", 5),
                  (r"minyak rem|kampas|brake|cakram|tromol|master rem|pedal rem|tuas rem", 3),
                  (r"rem (bunyi|berdecit|getar|bergetar|bocor)|decit", 3)],
    "bodi_rusak": [(r"tabrak|menabrak|ditabrak|kecelakaan|\blaka\b|senggol|nyenggol|serempet|keserempet|terjatuh|\bjatuh\b|\bslip\b", 5),
                   (r"\bbodi\b|\bbody\b|bumper|spion|kap mesin|fender|lecet|penyok|ringsek|retak|\bpecah\b|\bpatah\b|stang bengkok|bengkok", 3),
                   (r"rangka|shock patah|roda (copot|lepas)", 3)],
    "rantai_putus": [(r"rantai|\bchain\b|\bgir\b|\bgear\b|sproket|sprocket|\brante\b", 4),
                     (r"\bcvt\b|vanbelt|v-belt|v belt|belt putus|roller|kopling|transmisi|persneling|perseneling|ngeden|selip|"
                      r"tarikan hilang|tidak ada tarikan|gas (tapi )?(tidak|nggak|gak) (jalan|maju)|jalan di tempat", 4),
                     (r"putus|kendor|longgar", 1)],
}
RINGKASAN = {
    "ban_bocor": "Ban kemungkinan bocor atau tertusuk benda tajam.",
    "aki_soak": "Aki kemungkinan soak atau lemah sehingga tidak cukup daya untuk menyalakan mesin.",
    "bensin_habis": "Kendaraan kemungkinan kehabisan bahan bakar.",
    "mesin_overheat": "Ada indikasi gangguan mesin atau sistem pendinginan (panas berlebih).",
    "kelistrikan": "Ada indikasi gangguan kelistrikan (korsleting, sekring, atau kabel).",
    "rem_blong": "Ada indikasi masalah serius pada sistem rem.",
    "bodi_rusak": "Kendaraan mengalami kerusakan bodi atau benturan ringan.",
    "rantai_putus": "Rantai, gir, atau CVT kemungkinan putus/selip sehingga tenaga tidak tersalur.",
    "lainnya": "Keluhan belum dapat dikenali dengan pasti. Montir akan menilai langsung.",
}
SARAN = {
    "ban_bocor": "Mekanik akan membawa kunci ban, alat tambal, dan pompa.",
    "aki_soak": "Mekanik akan membawa kabel jumper dan aki cadangan.",
    "bensin_habis": "Mekanik akan membawa jeriken BBM.",
    "mesin_overheat": "Mekanik akan membawa coolant, satu set kunci, dan scanner.",
    "kelistrikan": "Mekanik akan membawa multimeter dan sekring cadangan.",
    "rem_blong": "Mekanik akan memeriksa minyak rem, kampas, dan master rem di lokasi.",
    "bodi_rusak": "Mekanik akan memeriksa kerusakan dan keamanan kendaraan di lokasi.",
    "rantai_putus": "Mekanik akan membawa rantai/belt cadangan dan perkakas.",
    "lainnya": "Jelaskan masalah Anda lewat chat dengan montir setelah pesanan diterima.",
}
AMAN = {
    "ban_bocor": ["Menepi ke tempat aman dan nyalakan lampu hazard", "Jangan memaksa jalan dengan ban kempes"],
    "aki_soak": ["Matikan lampu & perangkat listrik", "Jangan berulang kali menekan starter"],
    "bensin_habis": ["Menepi dan nyalakan lampu hazard", "Jangan mendorong di jalur cepat"],
    "mesin_overheat": ["Matikan mesin dan tunggu dingin", "Jangan membuka tutup radiator saat panas"],
    "kelistrikan": ["Matikan mesin dan lepas kunci", "Jauhkan dari percikan/bau gosong"],
    "rem_blong": ["Jangan dikendarai lagi", "Gunakan rem mesin/turun gigi bila masih bergerak"],
    "bodi_rusak": ["Pastikan semua penumpang aman", "Nyalakan hazard dan pasang segitiga pengaman"],
    "rantai_putus": ["Matikan mesin dan menepi", "Jangan memaksa menarik gas"],
    "lainnya": ["Menepi ke tempat aman", "Siapkan penjelasan gejala untuk montir"],
}
DEREK_KATA = r"mogok total|tidak bisa (jalan|digerakkan)|terendam|kebanjiran|banjir|roda (copot|lepas)|ringsek|tidak aman dikendarai"


def analisis_offline(keluhan, kendaraan="motor"):
    t = re.sub(r"\s+", " ", (keluhan or "").lower())
    skor = {k: sum(w for pola, w in aturan if re.search(pola, t)) for k, aturan in ATURAN.items()}
    urut = sorted(skor.items(), key=lambda x: -x[1])
    (k1, s1), (k2, s2) = urut[0], urut[1]
    if not t.strip() or s1 <= 0:
        kat, yakin, alt = "lainnya", 0.3, None
    else:
        kat = k1
        yakin = round(min(0.93, max(0.4, 0.35 + 0.4 * (s1 - s2) / (s1 + 1) + 0.2 * min(s1, 10) / 10)), 2)
        alt = k2 if s2 >= 0.6 * s1 and s2 > 0 else None
    mobil = (kendaraan or "").lower() == "mobil"
    derek = mobil and (kat == "rem_blong" or bool(re.search(DEREK_KATA, t))
                       or (kat == "bodi_rusak" and bool(re.search(r"tabrak|kecelakaan|ringsek|rangka", t)))
                       or (kat == "mesin_overheat" and bool(re.search(r"asap|knocking|mati total|kletek", t))))
    return dict(kategori=kat, keyakinan=yakin, ringkasan=RINGKASAN[kat], saran=SARAN[kat], tindakan=AMAN[kat][:3],
                perlu_derek=derek, alternatif=alt, sumber="Analisis offline")


# ── LLM (opsional) ──────────────────────────────────────────────────────────────
def _provider():
    p = (os.environ.get("OTOFIX_AI_PROVIDER") or "").lower()
    if p == "off":
        return None
    e = os.environ.get
    if p in ("", "anthropic") and e("ANTHROPIC_API_KEY"):
        return dict(jenis="anthropic", nama="Claude AI", key=e("ANTHROPIC_API_KEY"), model=e("OTOFIX_AI_MODEL") or "claude-haiku-5-5")
    if p in ("", "gemini") and (e("GEMINI_API_KEY") or e("GOOGLE_API_KEY")):
        return dict(jenis="gemini", nama="Gemini AI", key=e("GEMINI_API_KEY") or e("GOOGLE_API_KEY"), model=e("OTOFIX_AI_MODEL") or "gemini-2.0-flash")
    if p in ("", "openai") and (e("OTOFIX_AI_KEY") or e("OPENAI_API_KEY")):
        return dict(jenis="openai", nama="AI", key=e("OTOFIX_AI_KEY") or e("OPENAI_API_KEY"),
                    url=e("OTOFIX_AI_URL") or "https://api.openai.com/v1/chat/completions", model=e("OTOFIX_AI_MODEL") or "gpt-4o-mini")
    return None


def _prompt(keluhan, kendaraan):
    daftar = "\n".join(f'- "{k}": {v}' for k, v in DEFINISI.items())
    sistem = ("Kamu adalah asisten diagnosa kendaraan untuk aplikasi bantuan darurat jalan raya di Indonesia. "
              "Pahami bahasa sehari-hari, singkatan, dan typo. Pilih TEPAT SATU kategori yang paling sesuai:\n" + daftar +
              "\nJawab HANYA dengan JSON valid tanpa teks lain, dengan kunci: "
              '"kategori" (salah satu kunci di atas), "keyakinan" (angka 0-1, jujur: rendah bila gejala ambigu), '
              '"ringkasan" (1 kalimat), "saran" (1 kalimat: apa yang perlu disiapkan montir), '
              '"tindakan" (maks 3 tindakan aman untuk pengguna), "perlu_derek" (true/false). '
              'perlu_derek HANYA boleh true untuk mobil yang tidak aman/tidak bisa dijalankan; untuk motor selalu false. '
              "Jangan menebak berlebihan: bila tidak jelas, pakai kategori lainnya dengan keyakinan rendah.")
    return sistem, f"Jenis kendaraan: {kendaraan}\nKeluhan pengguna: {keluhan}"


def _post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _panggil(pv, keluhan, kendaraan, timeout):
    sistem, user = _prompt(keluhan, kendaraan)
    if pv["jenis"] == "anthropic":
        d = _post("https://api.anthropic.com/v1/messages", {"x-api-key": pv["key"], "anthropic-version": "2023-06-01"},
                  dict(model=pv["model"], max_tokens=500, temperature=0, system=sistem, messages=[dict(role="user", content=user)]), timeout)
        return "".join(b.get("text", "") for b in d["content"])
    if pv["jenis"] == "gemini":
        d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{pv['model']}:generateContent?key={pv['key']}", {},
                  dict(systemInstruction=dict(parts=[dict(text=sistem)]), contents=[dict(role="user", parts=[dict(text=user)])],
                       generationConfig=dict(temperature=0, responseMimeType="application/json")), timeout)
        return d["candidates"][0]["content"]["parts"][0]["text"]
    d = _post(pv["url"], {"Authorization": "Bearer " + pv["key"]},
              dict(model=pv["model"], temperature=0, messages=[dict(role="system", content=sistem), dict(role="user", content=user)]), timeout)
    return d["choices"][0]["message"]["content"]


def _bersihkan(teks, kendaraan):
    m = re.search(r"\{.*\}", teks, re.S)
    d = json.loads(m.group(0))
    kat = d.get("kategori") if d.get("kategori") in KATEGORI else "lainnya"
    try:
        yakin = max(0.0, min(1.0, float(d.get("keyakinan", 0.6))))
    except (TypeError, ValueError):
        yakin = 0.6
    tindakan = [str(x)[:120] for x in (d.get("tindakan") or []) if x][:3] or AMAN[kat][:3]
    return dict(kategori=kat, keyakinan=round(yakin, 2), ringkasan=str(d.get("ringkasan") or RINGKASAN[kat])[:240],
                saran=str(d.get("saran") or SARAN[kat])[:240], tindakan=tindakan,
                perlu_derek=bool(d.get("perlu_derek")) and (kendaraan or "").lower() == "mobil", alternatif=None)


def analisis(keluhan, kendaraan="motor", timeout=12):
    """Mengembalikan dict(kategori, keyakinan 0-1, ringkasan, saran, tindakan[], perlu_derek, sumber[, catatan])."""
    hasil = analisis_offline(keluhan, kendaraan)
    pv = _provider()
    if pv and (keluhan or "").strip():
        try:
            r = _bersihkan(_panggil(pv, keluhan, kendaraan, timeout), kendaraan)
            r["sumber"] = pv["nama"]
            return r
        except Exception as ex:  # jaringan/key/format gagal -> tetap beri hasil offline
            hasil["catatan"] = f"AI online tidak tersedia ({type(ex).__name__}); memakai analisis offline."
    return hasil

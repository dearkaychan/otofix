"""Database jenis kendaraan (motor & mobil) yang umum di Indonesia + pencarian toleran typo.
Daftar bisa ditambah dengan mengedit DATA di bawah; pengguna juga bisa mengisi manual bila model tidak ditemukan."""
import difflib, re

DATA = {
    "motor": {
        "Honda": ["BeAT", "BeAT Street", "Scoopy", "Genio", "Vario 110", "Vario 125", "Vario 150", "Vario 160", "PCX 160", "ADV 160",
                  "Stylo 160", "Forza 250", "Supra X 125", "Supra GTR 150", "Revo", "Blade 125", "Karisma", "Legenda", "Verza 150",
                  "Sonic 150R", "CB150R StreetFire", "CB150 Verza", "CB150X", "CB250R", "CBR150R", "CBR250RR", "CBR500R", "CRF150L",
                  "CRF250 Rally", "XR150L", "Monkey", "Super Cub C125", "ST125 Dax", "Rebel 500", "Africa Twin", "Vario Techno",
                  "Spacy", "Win 100", "Tiger", "Megapro", "GL Pro", "Beat eSP", "EM1 e:", "CUV e:"],
        "Yamaha": ["Mio", "Mio M3", "Mio J", "Mio Z", "Mio Sporty", "Soul GT", "Fino", "Fazzio", "Gear 125", "Lexi", "Freego",
                   "Aerox 155", "NMax 155", "NMax Turbo", "XMax 250", "Grand Filano", "Jupiter Z", "Jupiter Z1", "Jupiter MX",
                   "MX King 150", "Vixion", "Vixion R", "R15", "R25", "R6", "R1", "MT-15", "MT-25", "MT-09", "XSR 155", "WR155R",
                   "Byson", "Vega Force", "Vega ZR", "Force 1", "Xeon", "Scorpio", "RX King", "RX-Z", "Tricity", "TMAX", "Tenere 700",
                   "Fazzio Hybrid", "Gear Ultima", "Neo's e", "E01"],
        "Suzuki": ["Satria F150", "Satria FU150", "Raider R150", "GSX-R150", "GSX-S150", "GSX-R250", "GSX-S750", "V-Strom 250",
                   "Smash", "Shogun", "Shogun Axelo", "Thunder 125", "Thunder 250", "Address", "Nex II", "Nex Crossover", "Avenis",
                   "Burgman Street", "Skydrive", "Spin", "Hayate", "Arashi", "Katana", "Inazuma", "Bandit 150", "Satria 2 Tak", "Smash Titan"],
        "Kawasaki": ["Ninja 150", "Ninja 250", "Ninja 250 SL", "Ninja ZX-25R", "Ninja ZX-4RR", "Ninja 400", "Ninja 650", "Ninja ZX-10R",
                     "Z250", "Z250 SL", "Z400", "Z650", "Z900", "Z1000", "KLX 150", "KLX 230", "D-Tracker 150", "W175", "W175 Cafe",
                     "W800", "Versys 250", "Versys 650", "Vulcan S", "ZX-25R", "Eliminator 400", "Binter Merzy", "Athlete", "Blitz"],
        "Vespa": ["Primavera", "Sprint", "LX 125", "S 125", "GTS 150", "GTS 300", "GTV", "Matic", "Piaggio Liberty", "Piaggio Medley"],
        "TVS": ["Apache RTR 160", "Apache RTR 200", "Apache RR 310", "Ntorq 125", "Jupiter", "Rockz", "Dazz", "Neo NX", "Max 125", "Raider 125"],
        "Benelli": ["TNT 135", "TNT 25", "TNT 249S", "Leoncino 250", "Leoncino 500", "Imperiale 400", "502C", "TRK 251", "TRK 502", "Patagonian Eagle"],
        "Royal Enfield": ["Classic 350", "Hunter 350", "Meteor 350", "Bullet 350", "Himalayan", "Interceptor 650", "Continental GT 650", "Super Meteor 650", "Scram 411"],
        "KTM": ["Duke 125", "Duke 200", "Duke 250", "Duke 390", "RC 200", "RC 390", "Adventure 250", "Adventure 390", "EXC 250"],
        "Viar": ["Q1", "Cross X 150", "Cross X 200", "Star NR", "Vortex", "New Karya 3", "Fox", "Gelis 8"],
        "United": ["T1800", "TX 1800", "TX 3000", "T1800 Lite", "MX 1500"],
        "Kymco": ["Like 150i", "Like 125", "Agility", "Many 110", "Downtown", "Xciting", "AK 550"],
        "SYM": ["Jet 14", "Jet X", "Symphony", "Joyride", "Fiddle", "Maxsym", "Cruisym"],
        "Piaggio": ["Liberty 150", "Medley 150", "MP3", "Beverly", "Zip"],
        "Triumph": ["Speed 400", "Scrambler 400X", "Street Triple", "Bonneville T100", "Tiger 900", "Trident 660"],
        "Ducati": ["Monster", "Scrambler", "Panigale V2", "Panigale V4", "Multistrada", "Diavel", "Hypermotard", "Streetfighter"],
        "BMW Motorrad": ["G 310 R", "G 310 GS", "R 1250 GS", "S 1000 RR", "F 850 GS", "R nineT", "C 400 GT"],
        "Harley-Davidson": ["Sportster", "Iron 883", "Street Bob", "Fat Boy", "Road King", "Nightster", "Pan America"],
        "Motor Listrik": ["Gesits G1", "Polytron Fox-R", "Polytron Fox-S", "Selis E-Max", "Volta 401", "Alva One", "United E-Motor", "Smoot Tempur",
                          "Viar Q1 Listrik", "Honda EM1 e:", "Yamaha E01", "Ather 450", "Zero SR"],
    },
    "mobil": {
        "Toyota": ["Avanza", "Veloz", "Veloz Hybrid", "Innova", "Innova Reborn", "Innova Zenix", "Rush", "Fortuner", "Calya", "Agya", "Yaris",
                   "Yaris Cross", "Raize", "Vios", "Corolla Cross", "Corolla Altis", "Camry", "Alphard", "Vellfire", "Hilux", "Hilux Double Cabin",
                   "Hiace", "Land Cruiser", "Land Cruiser Prado", "Kijang Kapsul", "Kijang Super", "Kijang Grand", "Etios Valco", "Sienta",
                   "C-HR", "Avanza Veloz", "86", "GR Yaris", "bZ4X", "Voxy", "Starlet", "Soluna", "Limo"],
        "Daihatsu": ["Xenia", "Terios", "Sigra", "Ayla", "Gran Max", "Gran Max Blind Van", "Luxio", "Rocky", "Sirion", "Taft", "Taruna",
                     "Zebra", "Espass", "Feroza", "Charade", "Ceria", "Grand Max Pick Up", "Copen", "Hijet", "Sirion Sport"],
        "Honda": ["Brio", "Brio RS", "Brio Satya", "Jazz", "HR-V", "CR-V", "BR-V", "City", "City Hatchback", "Civic", "Civic Turbo",
                  "Civic Type R", "Accord", "WR-V", "Mobilio", "Freed", "Odyssey", "Stream", "Fit", "Elysion", "S660", "e:Ny1", "Prelude"],
        "Suzuki": ["Ertiga", "XL7", "Ignis", "Baleno", "Carry", "Carry Pick Up", "APV", "APV Arena", "S-Presso", "Jimny", "Jimny 5 Pintu",
                   "Swift", "Grand Vitara", "SX4", "Splash", "Karimun", "Karimun Wagon R", "Futura", "Katana", "Escudo", "Fronx", "Vitara"],
        "Mitsubishi": ["Xpander", "Xpander Cross", "Pajero Sport", "Pajero", "Triton", "L300", "Xforce", "Colt T120SS", "Colt Diesel",
                       "Outlander Sport", "Outlander", "Mirage", "Lancer", "Eclipse Cross", "Strada", "Kuda", "Maven"],
        "Nissan": ["Livina", "Grand Livina", "Kicks e-Power", "Magnite", "Terra", "Serena", "X-Trail", "March", "Juke", "Evalia", "Navara",
                   "Note", "Sunny", "Teana", "Almera", "Leaf", "Elgrand", "Patrol", "Datsun Go", "Datsun Go+", "Datsun Cross", "Datsun Redi-Go"],
        "Mazda": ["Mazda2", "Mazda2 Hatchback", "Mazda3", "Mazda6", "CX-3", "CX-30", "CX-5", "CX-8", "CX-9", "CX-60", "MX-5", "BT-50", "RX-8", "Biante", "MX-30"],
        "Hyundai": ["Creta", "Stargazer", "Stargazer X", "Ioniq 5", "Ioniq 6", "Palisade", "Santa Fe", "Kona Electric", "Staria", "Tucson", "H-1",
                    "Avega", "Atoz", "i10", "i20", "Accent", "Elantra", "Venue", "Grand i10", "Trajet", "Starex", "Gets", "Matrix", "Sonata"],
        "Kia": ["Seltos", "Sonet", "Carnival", "Sportage", "EV6", "EV9", "Picanto", "Rio", "Sorento", "Cerato", "Optima", "Carens", "Pregio", "Soul", "Stonic"],
        "Wuling": ["Air ev", "Binguo EV", "Cloud EV", "Confero", "Confero S", "Almaz", "Almaz RS", "Cortez", "Alvez", "Starray", "Formo", "Formo Max", "Hongguang"],
        "Chery": ["Tiggo 5X", "Tiggo 7 Pro", "Tiggo 8 Pro", "Omoda 5", "Omoda E5", "Jaecoo J7", "Tiggo Cross", "QQ", "Arrizo 5"],
        "BYD": ["Atto 3", "Dolphin", "Seal", "Sealion 7", "M6", "Han", "Tang", "Seagull", "Atto 1", "Sealion 6", "Shark 6"],
        "MG": ["ZS EV", "MG4 EV", "HS", "5", "Cyberster", "MG3", "MG VS HEV", "Gloster", "Maxus Mifa 9"],
        "DFSK": ["Glory 560", "Glory i-Auto", "Gelora", "Super Cab", "Seres E1", "Seres 3", "Glory 580", "Mini Truck", "Gelora E"],
        "Isuzu": ["Panther", "D-Max", "Traga", "Elf", "MU-X", "Giga", "Phoenix", "Mu-7", "Bighorn", "Trooper", "Elf Microbus", "NMR", "NLR"],
        "BMW": ["Seri 1", "Seri 2", "Seri 3", "Seri 5", "Seri 7", "X1", "X2", "X3", "X5", "X7", "Z4", "i4", "iX", "iX1", "M3", "M4", "M5", "520i", "320i"],
        "Mercedes-Benz": ["A-Class", "C-Class", "E-Class", "S-Class", "CLA", "GLA", "GLB", "GLC", "GLE", "GLS", "G-Class", "EQA", "EQB", "EQE",
                          "EQS", "V-Class", "Vito", "Sprinter", "SLK", "190E"],
        "Audi": ["A3", "A4", "A6", "Q2", "Q3", "Q5", "Q7", "Q8", "e-tron", "TT", "R8", "A5"],
        "Volkswagen": ["Polo", "Golf", "Tiguan", "Touareg", "Caravelle", "Santana", "Scirocco", "Beetle", "ID.4", "Jetta", "Passat", "Kombi"],
        "Ford": ["Ranger", "Everest", "EcoSport", "Fiesta", "Focus", "Mustang", "Escape", "Territory", "Raptor", "Explorer", "Mondeo", "Laser"],
        "Chevrolet": ["Spin", "Trax", "Captiva", "Trailblazer", "Orlando", "Aveo", "Colorado", "Zafira", "Tavera", "Blazer", "Camaro"],
        "Renault": ["Kwid", "Triber", "Duster", "Kiger", "Captur", "Koleos", "Megane"],
        "Subaru": ["XV", "Crosstrek", "Forester", "BRZ", "WRX", "Outback", "Levorg", "Impreza", "Legacy"],
        "Lexus": ["NX", "RX", "UX", "LX", "LM", "ES", "IS", "LS", "GX", "RZ"],
        "Volvo": ["XC40", "XC60", "XC90", "S60", "S90", "V60", "EX30", "C40"],
        "Peugeot": ["208", "2008", "3008", "5008", "508", "307", "206"],
        "Proton": ["Saga", "Persona", "Exora", "Preve", "X50", "X70", "Iriz"],
        "Tesla": ["Model 3", "Model Y", "Model S", "Model X"],
        "Land Rover": ["Defender", "Discovery", "Range Rover", "Range Rover Evoque", "Range Rover Sport", "Freelander"],
        "Jeep": ["Wrangler", "Compass", "Renegade", "Cherokee", "Gladiator"],
        "Hino": ["Dutro", "Ranger", "Hino 500", "Hino 300", "Hino 700"],
        "Tata": ["Super Ace", "Ace", "Xenon", "Indica"],
        "Mini": ["Cooper", "Cooper S", "Countryman", "Clubman", "Cooper SE"],
        "Neta": ["V", "V-II", "X", "Aya"],
        "Lainnya": ["Mobil klasik / modifikasi", "Mobil impor"],
    },
}


def merek(jenis):
    return list(DATA.get(jenis, {}))


def _norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def jumlah(jenis=None):
    return sum(len(v) for j, m in DATA.items() if jenis in (None, j) for v in m.values())


def cari(jenis, query="", batas=40):
    """Cari (merek, model) untuk jenis 'motor'/'mobil'. Semua kata kunci harus cocok pada 'merek model'
    (urutan bebas); bila tak ada hasil, dicoba pencocokan mirip (typo, mis. 'vaio' -> 'Vario')."""
    kandidat = [(m, mod) for m, daftar in DATA.get(jenis, {}).items() for mod in daftar]
    q = _norm(query)
    if not q:
        return kandidat[:batas]
    kata = q.split()
    teks = lambda c: _norm(c[0] + " " + c[1])
    hasil = [c for c in kandidat if all(k in teks(c) for k in kata)]
    if hasil:
        # model yang namanya diawali kata kunci tampil lebih dulu
        hasil.sort(key=lambda c: (not _norm(c[1]).startswith(kata[0]) and not _norm(c[0]).startswith(kata[0]), len(c[1])))
        return hasil[:batas]
    peta = {teks(c): c for c in kandidat}
    dekat = difflib.get_close_matches(q, list(peta), n=batas, cutoff=0.55)
    if not dekat:  # cocokkan per kata untuk query panjang
        dekat = [t for t in peta if any(difflib.get_close_matches(k, t.split(), n=1, cutoff=0.75) for k in kata)]
    return [peta[t] for t in dekat][:batas]

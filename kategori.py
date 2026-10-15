"""Amazon TR Stanley ilan başlıklarını okur: ürün tipi, seri, alt seri, hacim ve renk.

Kurallar Amazon TR'den toplanan gerçek başlıklardan türetildi. Başlıklar kucuk_harf ile küçültülmüş
olarak saklanır (İ/I/ı -> i), bu yüzden kalıplar da "i" ile yazılır ("kilif", "çantasi").
Sıra önemlidir: ilk eşleşen kural kazanır.

Kurallar değiştiğinde database.kategorileri_yenile() tüm geçmiş kayıtları yeniden kategoriler.
"""
import re

# ---------- Başlık metni yardımcıları ----------

def kucuk_harf(metin):
    # Türkçe 'İ' ve 'I' harflerinin lower() ile bozulmasını engelle
    return metin.replace("İ", "i").replace("I", "ı").lower().replace("ı", "i")

def basliktaki_hacimler(baslik):
    """Başlıktaki tüm hacimleri litre cinsinden döndürür: '1.18 Litre' -> 1.18, '750 ml' -> 0.75, '40 oz' -> 1.18"""
    hacimler = []
    for sayi, birim in re.findall(r"(\d+(?:[.,]\d+)?)\s*(ml|litre|liter|lt|l|oz)\b", baslik):
        deger = float(sayi.replace(",", "."))
        if birim == "ml":
            deger /= 1000
        elif birim == "oz":
            deger = round(deger * 0.0296, 2)
        hacimler.append(deger)
    return hacimler

# Renklerin başlıklarda geçebilecek karşılıkları
# "Çelik" bilinçli olarak yok: neredeyse her başlıkta "paslanmaz çelik" malzeme olarak geçiyor
RENK_ESANLAMLARI = {
    "yeşil": ["yeşil", "yesil", "green"],
    "siyah": ["siyah", "black"],
    "mat siyah": ["mat siyah", "matte black"],
    "lacivert": ["lacivert", "navy"],
    "beyaz": ["beyaz", "white"],
}

def renk_eslesiyor_mu(baslik, renk):
    """Başlıkta seçilen renk (veya karşılığı) geçiyor mu? Filtrelenemeyen renklerde (örn. Çelik) None döner."""
    istenen = RENK_ESANLAMLARI.get(renk)
    if istenen is None:
        return None
    return any(re.search(rf"\b{k}\b", baslik) for k in istenen)

# ---------- Kategori kuralları ----------

# Stanley Tools: aynı adı taşıyan ALET markası (Stanley Black & Decker). Amazon'un marka filtresi ayırmıyor.
# Termos analizinin dışında tutulur (85 TL'lik matkap ucu termos fiyatına karışmasın).
KAPSAM_DISI_KALIPLARI = [
    r"\bsta\d", r"\bst0\d", r"\bpc\d{3}\b", r"zimpara", r"maket biçaği", r"matkap", r"kesim diski",
    r"taşima arabasi", r"tornavida", r"pense", r"şerit metre", r"testere",
]

# Kamp buzluğu, soğutucu çanta, sürahi: aksesuar kalıplarından ("çanta") ÖNCE kontrol edilir
SOGUTUCU_KALIPLARI = [r"buzlu[gğ]u", r"soğutucu", r"julienne", r"sürahi", r"\bjug\b"]

# Aksesuar / yedek parça: fiyat analizine KATILMAZ (134-550 TL'lik kapak, pipet, kılıf termos fiyatını bozar)
# Dikkat: tek başına "kapak" ya da "uyumlu" yeterli değil. Gerçek ürünlerde de geçiyor:
#   "flowstate 3 pozisyonlu kapak" (bardağın kendi kapağı), "seyahat için uyumlu bardak"
AKSESUAR_KALIPLARI = [
    r"(?<!için )uyumlu", r"kapak seti", r"\bkapaği\b", r"\btumbler kapak\b", r"\byedek\b", r"\bkilif",
    r"\btipa\b", r"\bçanta", r"\baltlik\b", r"\bboot\b", r"\btopper\b", r"\bkoruyucu\b", r"\baksesuar\b",
    r"\bsizdirmazlik\b",
]

KATEGORI_KURALLARI = [
    ("Yemek Termosu",   [r"yemek termos", r"food jar"]),
    ("Saklama Kabı",    [r"saklama kutusu", r"useful box"]),
    ("Cep Matarası",    [r"cep matara", r"\bflask\b"]),
    ("Kahve Ekipmanı",  [r"french press", r"pour over", r"demleyici"]),
    ("Pipetli Bardak",  [r"quencher", r"tumbler", r"pipetli", r"fl[i]?p straw"]),
    ("Termos",          [r"vakumlu (çelik )?termos", r"classic bottle", r"klasik şişe", r"botella", r"growler"]),
    # Genel "şişe" kalıbında "termos şişe" hariç: Classic termos başlıklarında geçiyor
    ("Su Şişesi",       [r"su şişesi", r"içecek şişesi", r"wellspr", r"all day", r"water bottle", r"shaker",
                         r"çalkalayici", r"(?<!termos )şişe\b"]),
    ("Kupa & Bardak",   [r"\bmug\b", r"\bkupa", r"\bcup\b", r"bardak", r"bardağ", r"\bstein\b", r"\bpint\b",
                         r"caf[eé][- ]to-go", r"stay[- ]hot"]),
]

# Başlıkta sadece "termos" geçiyorsa, bazı serilerin asıl ürün tipi:
# "the iceflow twist flip termos" bir su şişesi, "the transit fliptop termos" bir seyahat kupası
SERI_VARSAYILAN_KATEGORI = {"IceFlow": "Su Şişesi", "Transit": "Kupa & Bardak", "Café To-Go": "Kupa & Bardak"}

# Seri: daha özel olan önce. Quencher, IceFlow'dan önce ("quencher protour flip straw" bir Quencher'dır);
# IceFlow, Aerolight'tan önce ("aerolight iceflow" bir IceFlow şişesidir)
SERI_KURALLARI = [
    ("Quencher",          [r"quencher"]),
    ("IceFlow",           [r"ice ?flow", r"buz akişi", r"fl[i]?p straw"]),
    ("Aerolight",         [r"aerolight"]),
    ("Adventure",         [r"adventure"]),
    ("Trigger Action",    [r"trigger"]),
    ("Master",            [r"\bmaster\b"]),
    ("Transit",           [r"transit", r"fliptop"]),
    ("Quick Flip",        [r"quick[- ]flip"]),
    ("Café To-Go",        [r"caf[eé][- ]to-go"]),
    ("Everyday",          [r"everyday", r"suburban"]),
    ("Stay Hot",          [r"stay[- ]hot"]),
    ("Stay Chill",        [r"stay[- ]chill"]),
    ("Activate",          [r"activate", r"etkinleştir"]),
    ("Artisan",           [r"artisan"]),
    ("Wellspring",        [r"wellspr"]),
    ("All Day",           [r"all day"]),
    ("Classic Legendary", [r"classic", r"klasik", r"legendary", r"cl[aá]sica", r"growler"]),
]

# Quencher alt serileri: fiyatları belirgin şekilde farklı, karşılaştırmada ayrı tutulmalı
QUENCHER_ALT_SERI = [
    ("ProTour",        [r"pro ?tour"]),
    ("Fluted",         [r"fluted"]),
    ("H2.0 FlowState", [r"h2\.[0o]", r"flowstate"]),
]

# Başlıkta seri adı yazmayan ilanlar için Stanley ürün kodu -> (seri, alt seri, kategori)
# Kodlar, aynı ürünün seri adı yazan başka ilanlarından eşleştirildi.
URUN_KODU_SERI = {
    "10-12486": ("Quencher", "ProTour", None),
    "10-12484": ("Quencher", "ProTour", None),
    "10-21126": ("Quencher", "ProTour", None),
    "10-13002": ("Quencher", "Fluted", None),
    "10-10824": ("Quencher", "H2.0 FlowState", None),
    "10-11353": ("Classic Legendary", None, "Yemek Termosu"),
    "10-09382": ("Classic Legendary", None, "Yemek Termosu"),
    "10-11283": ("IceFlow", None, "Pipetli Bardak"),
    "10-13425": ("IceFlow", None, None),
    "10-11444": ("Everyday", None, "Kupa & Bardak"),
}

def _ilk_eslesen(baslik, kurallar):
    for ad, kaliplar in kurallar:
        if any(re.search(k, baslik) for k in kaliplar):
            return ad
    return None

def _herhangi(baslik, kaliplar):
    return any(re.search(k, baslik) for k in kaliplar)

def kategorize_et(baslik):
    """Başlıktan {kategori, seri, alt_seri, aksesuar, ucuncu_parti} döndürür.
    aksesuar=True olan ilanlar (aksesuarlar ve Stanley Tools aletleri) fiyat analizine katılmaz."""
    ucuncu_parti = not baslik.strip().startswith("stanley")   # başka firmaların "Stanley ile uyumlu" ürünleri

    if _herhangi(baslik, KAPSAM_DISI_KALIPLARI):
        return {"kategori": "Kapsam Dışı (Stanley Tools)", "seri": "Diğer", "alt_seri": None,
                "aksesuar": True, "ucuncu_parti": ucuncu_parti}

    seri = _ilk_eslesen(baslik, SERI_KURALLARI)
    alt_seri = _ilk_eslesen(baslik, QUENCHER_ALT_SERI) if seri == "Quencher" else None
    kod_kategori = None
    kod = re.search(r"\b10-?(\d{5})", baslik)   # "10-12486-099" ya da tiresiz "10112830511"
    if kod and f"10-{kod.group(1)}" in URUN_KODU_SERI:
        kod_seri, kod_alt_seri, kod_kategori = URUN_KODU_SERI[f"10-{kod.group(1)}"]
        seri = seri or kod_seri
        alt_seri = alt_seri or kod_alt_seri

    aksesuar = False
    if _herhangi(baslik, SOGUTUCU_KALIPLARI):
        kategori = "Soğutucu & Sürahi"
    elif _herhangi(baslik, AKSESUAR_KALIPLARI):
        kategori, aksesuar = "Aksesuar", True
    elif seri == "Quencher":   # Ürün koduyla tanınan "stanley 10-12486 termos" gibi ilanlar da pipetli bardaktır
        kategori = "Pipetli Bardak"
    else:
        kategori = _ilk_eslesen(baslik, KATEGORI_KURALLARI)
        if kategori is None and "termos" in baslik:   # yalnızca genel "termos" kelimesi
            kategori = kod_kategori or SERI_VARSAYILAN_KATEGORI.get(seri, "Termos")
        kategori = kategori or kod_kategori

    return {
        "kategori": kategori or "Diğer",
        "seri": seri or "Diğer",
        "alt_seri": alt_seri,
        "aksesuar": aksesuar,
        "ucuncu_parti": ucuncu_parti,
    }

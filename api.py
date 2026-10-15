"""FastAPI servisi: kayıtlı Stanley ilanlarından (ya da demo verisinden) fiyat önerisi üretir.
Amazon'a istek atmaz; veri her gün veri_topla.py ile toplanır."""
from typing import Annotated

from fastapi import FastAPI, Query

from database import kayitli_ilanlar
from fiyat_hesap import buybox_referansi, piyasa_ozeti, strateji_belirle
from kategori import kucuk_harf, renk_eslesiyor_mu
from talep import kar_egrisi

app = FastAPI(title="Stanley Dinamik Fiyatlandırma API")

# Kayıtlı veride kaç gün geriye bakılacağı (veri_topla.py günde 1 kez çalışır)
KAYITLI_VERI_GUN = 7
# Aynı hacim sayılma toleransı (0.74 L ~ 0.75 L, 1.18 L ~ 1.2 L)
HACIM_TOLERANSI = 0.03

def _fiyatlandir(piyasa, urun_adi, alis_maliyeti, komisyon_orani, kargo, min_marj, aylik_satis):
    """Piyasa özetinden kural tabanlı öneri + talep modeli optimumu hesaplar."""
    adil_deger = piyasa["medyan"]   # ortalama değil medyan: tek bir aşırı pahalı/ucuz ilandan etkilenmez

    try:
        sonuc = strateji_belirle(piyasa["en_ucuz"], adil_deger, alis_maliyeti, komisyon_orani, kargo, min_marj)
    except ValueError as e:
        return {"hata": str(e)}

    # Buybox rakibi, piyasa istatistikleriyle aynı ilanlardan seçilir (renk filtresi uygulandıysa sadece o renk)
    rakip_fiyatlari = [i["fiyat"] for i in piyasa["ilanlar"] if i["renk_eslesti"] or not piyasa["renk_filtresi"]]
    egri = kar_egrisi(adil_deger, buybox_referansi(rakip_fiyatlari, adil_deger), sonuc["taban_fiyat"], aylik_satis,
                      alis_maliyeti, komisyon_orani, kargo)

    return {
        "analiz_edilen_urun": urun_adi,
        "piyasa": piyasa,
        "adil_deger_TL": adil_deger,
        "onerilen_aksiyon_fiyati_TL": sonuc["onerilen_fiyat"],
        "taban_fiyat_TL": sonuc["taban_fiyat"],
        "birim_net_kar_TL": sonuc["birim_net_kar"],
        "kar_marji_yuzde": sonuc["kar_marji_yuzde"],
        "strateji": sonuc["strateji"],
        "talep_modeli": egri,
    }

def _veri_tarihi(ilanlar):
    return {"en_eski": min((i["tarih"] for i in ilanlar), default=None),
            "en_yeni": max((i["tarih"] for i in ilanlar), default=None)}

# Parametreler Annotated ile yazıldı: varsayılanlar gerçek değer olur, fonksiyonlar testlerde doğrudan çağrılabilir.
# (Query(False) yazımında doğrudan çağrıda demo bir Query nesnesi, yani "doğru" olur ve demo verisi okunurdu.)
@app.get("/urun-secenekleri")
def urun_secenekleri(gun: Annotated[int, Query(ge=1)] = KAYITLI_VERI_GUN, demo: bool = False):
    """Veride bulunan ürünler: kategori / seri / alt seri / hacim ve ilan sayısı."""
    ilanlar = kayitli_ilanlar(gun, demo)

    # Aynı ürünün farklı yazılan hacimleri (0.59 / 0.6 L, 0.74 / 0.75 L) tek seçenekte birleştirilir:
    # her ürün grubunda hacimler sıralanır, birbirine HACIM_TOLERANSI kadar yakın olanlar aynı kümeye girer.
    urun_hacimleri = {}
    for i in ilanlar:
        urun_hacimleri.setdefault((i["kategori"], i["seri"], i["alt_seri"] or ""), []).append(round(i["hacim_litre"], 2))
    gruplar = {}
    for urun, hacimler in urun_hacimleri.items():
        kumeler = []
        for h in sorted(hacimler):
            if kumeler and abs(h - kumeler[-1][0]) / kumeler[-1][0] <= HACIM_TOLERANSI:
                kumeler[-1].append(h)
            else:
                kumeler.append([h])
        for kume in kumeler:
            temsilci = max(set(kume), key=kume.count)   # kümede en sık görülen hacim
            gruplar[(*urun, temsilci)] = len(kume)
    return {
        "secenekler": [{"kategori": k, "seri": s, "alt_seri": a, "hacim": h, "ilan_sayisi": n}
                       for (k, s, a, h), n in sorted(gruplar.items())],
        "veri_tarihi": _veri_tarihi(ilanlar),
    }

@app.get("/kayitli-fiyat")
def kayitli_fiyat_hesapla(
    kategori: Annotated[str, Query(description="Örn: Pipetli Bardak")],
    seri: Annotated[str, Query(description="Örn: Quencher")],
    hacim: Annotated[float, Query(gt=0, description="Litre, örn: 1.18")],
    alt_seri: Annotated[str, Query(description="Örn: H2.0 FlowState (boş = tüm alt seriler)")] = "",
    renk: Annotated[str, Query(description="Renk filtresi")] = "Fark etmez",
    alis_maliyeti: Annotated[float, Query(ge=0, description="Ürünün satıcıya maliyeti (TL)")] = 1200,
    komisyon_orani: Annotated[float, Query(ge=0, lt=1, description="Platform komisyonu (0.15 = %15)")] = 0.15,
    kargo: Annotated[float, Query(ge=0, description="Ürün başı kargo gideri (TL)")] = 60,
    min_marj: Annotated[float, Query(ge=0, lt=1, description="Kabul edilen minimum kâr marjı (0.10 = %10)")] = 0.10,
    aylik_satis: Annotated[float, Query(gt=0, description="Buybox sende ve piyasa medyanındayken aylık satış")] = 30,
    gun: Annotated[int, Query(ge=1)] = KAYITLI_VERI_GUN,
    demo: Annotated[bool, Query(description="Veritabanı yerine depodaki örnek veriyle çalış")] = False,
):
    """Kayıtlı ilanlardan seçilen ürünün piyasasını çıkarır ve fiyat önerisi hesaplar."""
    eslesenler = [
        {**i, "renk_eslesti": bool(renk_eslesiyor_mu(i["baslik"], kucuk_harf(renk)))}
        for i in kayitli_ilanlar(gun, demo)
        if i["kategori"] == kategori and i["seri"] == seri
        and (not alt_seri or (i["alt_seri"] or "") == alt_seri)
        and abs(i["hacim_litre"] - hacim) / hacim <= HACIM_TOLERANSI
    ]
    if not eslesenler:
        return {"hata": f"Son {gun} günün verisinde bu ürün için ilan yok. `python veri_topla.py` ile veriyi güncelleyin."}

    urun_adi = f"Stanley {seri} {alt_seri} {hacim} L {'' if renk == 'Fark etmez' else renk}".replace("  ", " ").strip()
    sonuc = _fiyatlandir(piyasa_ozeti(eslesenler), urun_adi, alis_maliyeti, komisyon_orani, kargo, min_marj, aylik_satis)
    sonuc["veri_tarihi"] = _veri_tarihi(eslesenler)
    sonuc["demo"] = demo
    return sonuc

"""Piyasa özeti, satıcı kârlılık hesapları ve fiyat stratejisi.

Birim net kâr = fiyat - komisyon (fiyat x oran) - alış maliyeti - kargo
Taban fiyat   = minimum kâr marjını sağlayan en düşük satış fiyatı
"""
import statistics

# Seçilen renkte bundan az ilan varsa piyasa değerleri tüm renklerden hesaplanır (2 ilanın medyanı güvenilmez)
MIN_RENKLI_ILAN = 3
# En ucuz satıcı medyanın bu oranının altındaysa "aykırı" sayılır (stok eritme, şüpheli ilan vb.)
AYKIRI_ESIK = 0.85
# Buybox için en ucuz rakibin ne kadar altına inileceği (TL)
BUYBOX_FARKI = 5

def piyasa_ozeti(ilanlar):
    """Rakip ilanlarından piyasa istatistikleri. İlanlarda 'fiyat' ve 'renk_eslesti' alanları olmalı."""
    if not ilanlar:
        return None

    renkli_fiyatlar = [i["fiyat"] for i in ilanlar if i["renk_eslesti"]]
    renk_filtresi = len(renkli_fiyatlar) >= MIN_RENKLI_ILAN
    fiyat_listesi = renkli_fiyatlar if renk_filtresi else [i["fiyat"] for i in ilanlar]

    return {
        "renk_filtresi": renk_filtresi,
        "en_ucuz": min(fiyat_listesi),
        "en_pahali": max(fiyat_listesi),
        "ortalama": round(statistics.mean(fiyat_listesi), 2),
        "medyan": round(statistics.median(fiyat_listesi), 2),
        "satici_sayisi": len(fiyat_listesi),
        "ilanlar": ilanlar
    }

def birim_net_kar(fiyat, alis_maliyeti, komisyon_orani, kargo):
    return fiyat * (1 - komisyon_orani) - alis_maliyeti - kargo

def taban_fiyat(alis_maliyeti, komisyon_orani, kargo, min_marj):
    """net_kar >= min_marj * fiyat  =>  fiyat >= (maliyet + kargo) / (1 - komisyon - min_marj)"""
    payda = 1 - komisyon_orani - min_marj
    if payda <= 0:
        raise ValueError("Komisyon + minimum marj %100'ü geçemez")
    return (alis_maliyeti + kargo) / payda

def buybox_referansi(rakip_fiyatlari, medyan):
    """Buybox için rekabet edilecek fiyat: medyanın çok altındaki aykırı ilanlar (stok eritme vb.) atlanarak
    en ucuz 'gerçek' rakip."""
    normal_rakipler = [f for f in rakip_fiyatlari if f >= medyan * AYKIRI_ESIK]
    return min(normal_rakipler) if normal_rakipler else medyan

def strateji_belirle(en_ucuz_rakip, medyan, alis_maliyeti, komisyon_orani, kargo, min_marj):
    """Rekabetçi fiyatı bulur ama asla taban fiyatın (zarar sınırının) altına inmez."""
    taban = taban_fiyat(alis_maliyeti, komisyon_orani, kargo, min_marj)

    if en_ucuz_rakip < medyan * AYKIRI_ESIK:
        fark_yuzde = round((1 - en_ucuz_rakip / medyan) * 100)
        aday = medyan * 0.95
        strateji = (f"En ucuz satıcı ({en_ucuz_rakip} TL) piyasa medyanının %{fark_yuzde} altında: muhtemelen stok eritiyor "
                    f"ya da şüpheli bir ilan. Onunla fiyat savaşına girme, medyanın %5 altında konumlan.")
    else:
        aday = en_ucuz_rakip - BUYBOX_FARKI
        strateji = (f"En ucuz satıcı ({en_ucuz_rakip} TL) piyasayla uyumlu fiyatta. "
                    f"{BUYBOX_FARKI} TL altına inerek Buybox'ı (satış önceliğini) sen al!")

    if aday < taban:
        strateji = (f"Rekabetçi fiyat ({aday:.0f} TL) senin taban fiyatının ({taban:.0f} TL) altında kalıyor: "
                    f"bu fiyattan satarsan hedef marjının altına düşersin. Fiyat savaşına girme, taban fiyatta kal.")
        aday = taban

    net_kar = birim_net_kar(aday, alis_maliyeti, komisyon_orani, kargo)
    return {
        "onerilen_fiyat": round(aday, 2),
        "taban_fiyat": round(taban, 2),
        "birim_net_kar": round(net_kar, 2),
        "kar_marji_yuzde": round(net_kar / aday * 100, 1),
        "strateji": strateji,
    }

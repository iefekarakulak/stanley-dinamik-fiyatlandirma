"""Talep modeli ile kâr eğrisi: her aday fiyat için tahmini satış x birim kâr hesaplanır, en kârlı fiyat seçilir.

Tahmini satış = aylık satış x talep çarpanı x Buybox payı

1) Talep çarpanı (VERİDEN ÖĞRENİLDİ): Fiyat normal fiyata (piyasa medyanı) göre değişince satış nasıl değişir?
   - Stanley modeli (stanley_modeli_egitimi.py): her gün toplanan Amazon TR verisiyle yeniden eğitilir.
     Yeterli veri birikip testte fiyat bilgisi tahmini iyileştirdiğinde ("aktif") kullanılır.
   - Aksi halde UCI Online Retail II ile eğitilen genel model (talep_modeli_egitimi.py) kullanılır.
2) Buybox payı (VARSAYIM): Aynı ürünü başka satıcılar da sattığı için en ucuz rakipten pahalıysan satış önceliğini
   kaybedersin. UCI'deki satıcının rakibi olmadığından bu etki o veriden öğrenilemez; lojistik bir eğriyle modellenir.
"""
import json
import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from fiyat_hesap import birim_net_kar

# Buybox varsayımı: rakiple aynı fiyatta pay %50; rakibin ~%2 altında ~%90, ~%2 üstünde ~%10
BUYBOX_GENISLIK = 0.01

_MODEL_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
STANLEY_MODELI = "stanley_talep_modeli"
UCI_MODELI = "talep_modeli"
_onbellek = {}   # model adı -> (dosya değişiklik zamanı, model, metrikler)

def _dosyadan_yukle(ad):
    """Modeli yükler; dosya her gün yeniden eğitilip değiştiğinde API'yi yeniden başlatmadan yenisini alır."""
    metrik_yolu = os.path.join(_MODEL_KLASORU, f"{ad}_metrikler.json")
    model_yolu = os.path.join(_MODEL_KLASORU, f"{ad}.joblib")
    if not (os.path.exists(metrik_yolu) and os.path.exists(model_yolu)):
        return None
    zaman = (os.path.getmtime(metrik_yolu), os.path.getmtime(model_yolu))
    if ad not in _onbellek or _onbellek[ad][0] != zaman:
        with open(metrik_yolu, encoding="utf-8") as f:
            metrikler = json.load(f)
        _onbellek[ad] = (zaman, joblib.load(model_yolu), metrikler)
    return _onbellek[ad][1], _onbellek[ad][2]

def aktif_model():
    """(model, metrikler, kaynak): Stanley modeli aktifse o, değilse UCI modeli."""
    stanley = _dosyadan_yukle(STANLEY_MODELI)
    if stanley and stanley[1].get("aktif"):
        return stanley[0], stanley[1], "Stanley (Amazon TR verisi)"
    model, metrikler = _dosyadan_yukle(UCI_MODELI)
    return model, metrikler, "UCI Online Retail II (genel)"

def talep_carpani(fiyat_oranlari, ay=None):
    """Normal fiyatta satış 1 kabul edilirse, verilen fiyat oranlarında satış kaç katına çıkar/iner?"""
    model, metrikler, _ = aktif_model()
    if "referans" in metrikler:   # Stanley modeli: diğer özellikler tipik değerlerinde sabit
        referans = metrikler["referans"]
    else:                         # UCI modeli
        baz = metrikler["referans_log_baz_talep"]
        referans = {"log_baz_talep": baz, "log_son4_hafta": baz, "ay": ay or datetime.now().month}
    oranlar = np.clip(np.asarray(fiyat_oranlari, dtype=float), *metrikler["oran_araligi"])
    girdi = pd.DataFrame({**referans, "log_fiyat_orani": np.log(np.append(oranlar, 1.0))})[metrikler["ozellikler"]]
    tahmin = np.expm1(model.predict(girdi))
    return tahmin[:-1] / tahmin[-1]   # son eleman oran=1.0 (normal fiyat) referansı

def buybox_payi(fiyatlar, rakip_fiyati):
    """Rakibe göre fiyat konumuna bağlı satış önceliği payı (0-1)."""
    return 1 / (1 + np.exp((np.asarray(fiyatlar) - rakip_fiyati) / (rakip_fiyati * BUYBOX_GENISLIK)))

def kar_egrisi(medyan, rakip, taban, aylik_satis, alis_maliyeti, komisyon_orani, kargo, nokta=200):
    """Taban fiyattan medyanın %40 üstüne kadar fiyatları dener; en yüksek toplam aylık kârı veren fiyatı bulur.
    rakip: Buybox için rekabet edilen fiyat (fiyat_hesap.buybox_referansi)
    aylik_satis: Buybox sende ve fiyat piyasa medyanındayken ayda kaç adet satılacağı."""
    alt = max(taban, medyan * 0.6)
    ust = max(medyan * 1.4, alt * 1.05)
    fiyatlar = np.linspace(alt, ust, nokta)
    satis = aylik_satis * talep_carpani(fiyatlar / medyan) * buybox_payi(fiyatlar, rakip)
    kar = satis * birim_net_kar(fiyatlar, alis_maliyeti, komisyon_orani, kargo)
    en_iyi = int(np.argmax(kar))
    _, metrikler, kaynak = aktif_model()
    return {
        "egri": [{"fiyat": round(float(f), 2), "tahmini_satis": round(float(s), 1), "aylik_kar": round(float(k), 2)}
                 for f, s, k in zip(fiyatlar, satis, kar)],
        "buybox_referans_fiyati": round(float(rakip), 2),
        "optimum_fiyat": round(float(fiyatlar[en_iyi]), 2),
        "optimum_satis": round(float(satis[en_iyi]), 1),
        "optimum_aylik_kar": round(float(kar[en_iyi]), 2),
        "model_esnekligi": metrikler["ortalama_esneklik"],
        "model_kaynagi": kaynak,
    }

"""Stanley'ye özel talep modeli: her gün toplanan Amazon TR verisiyle yeniden eğitilir.

Soru: Aynı ürün grubunda (seri + alt seri + hacim) bir ilan piyasa medyanına göre ucuz/pahalı olduğunda
satışı nasıl değişiyor?

- Hedef: "Geçen ay X adetten fazla satın alındı" rozetinden aylık satış tahmini.
  Amazon bu rozeti ancak belirli bir satışın üstünde gösterir; rozetsiz ilanlar ROZET_YOK_TAHMINI kabul edilir.
- Ana özellik: log(fiyat / aynı gün aynı ürün grubunun medyan fiyatı)
- Kontrol özellikleri: indirim oranı, yorum sayısı, puan, sponsorlu. (Çok yorumlu bir ilan hem pahalı hem çok
  satıyor olabilir; bunlar olmadan model "pahalı = çok satar" gibi yanlış bir ilişki öğrenebilir.)
- Doğrulama: son günler test seti. Model, fiyat bilgisi OLMAYAN aynı modelle karşılaştırılır; fiyat tahmine
  anlamlı katkı yapmıyorsa model devreye alınmaz ve UCI modeli kullanılmaya devam edilir.
"""
import json
import os
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

import database

MODEL_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
MODEL_ADI = "stanley_talep_modeli"

MIN_GUN = 14           # Devreye girmek için en az bu kadar farklı günün verisi
MIN_SATIR = 500        # ve en az bu kadar ilan-gün kaydı
MIN_GRUP_ILAN = 3      # Medyan karşılaştırması için bir ürün grubunda o gün en az bu kadar ilan
MIN_IYILESME = 0.03    # Fiyat bilgisi tahmin hatasını en az %3 azaltmalı
TEST_ORANI = 0.2       # Son %20 gün test seti
ROZET_YOK_TAHMINI = 25 # Rozet yoksa aylık satış "rozet eşiğinin (~50) altında" kabul edilir
ORAN_ARALIGI = (0.6, 1.6)

OZELLIKLER = ["log_fiyat_orani", "indirim_orani", "log_yorum", "puan", "sponsorlu"]

def veri_setini_hazirla(veritabani=None):
    """urun_gozlem tablosundan ilan-gün bazında eğitim tablosu üretir."""
    with sqlite3.connect(veritabani or database.VERITABANI) as conn:
        df = pd.read_sql('''SELECT * FROM urun_gozlem
                            WHERE aksesuar = 0 AND ucuncu_parti = 0
                              AND fiyat IS NOT NULL AND hacim_litre IS NOT NULL''', conn)
    if df.empty:
        return df

    df["gun"] = df["tarih"].str[:10]
    df["ilan"] = df["asin"].fillna(df["baslik"])
    df = df.sort_values("tarih").drop_duplicates(["gun", "ilan"], keep="last")   # günde bir kayıt

    # Ürün grubu: 0.59/0.6 L ve 0.74/0.75 L aynı gruba düşsün diye hacim 0.05 L'ye yuvarlanır
    df["alt_seri"] = df["alt_seri"].fillna("")
    df["hacim_grubu"] = (df["hacim_litre"] * 20).round() / 20
    grup = ["gun", "kategori", "seri", "alt_seri", "hacim_grubu"]
    df["grup_medyan"] = df.groupby(grup)["fiyat"].transform("median")
    df["grup_ilan"] = df.groupby(grup)["fiyat"].transform("size")
    df = df[df["grup_ilan"] >= MIN_GRUP_ILAN].copy()

    df["fiyat_orani"] = df["fiyat"] / df["grup_medyan"]
    df = df[df["fiyat_orani"].between(*ORAN_ARALIGI)]
    df["log_fiyat_orani"] = np.log(df["fiyat_orani"])
    df["indirim_orani"] = np.where(df["onceki_fiyat"] > df["fiyat"], 1 - df["fiyat"] / df["onceki_fiyat"], 0.0)
    df["log_yorum"] = np.log1p(df["yorum_sayisi"].fillna(0))
    df["puan"] = df["puan"].fillna(df["puan"].median() if df["puan"].notna().any() else 4.5)
    df["sponsorlu"] = df["sponsorlu"].fillna(0).astype(int)
    df["hedef"] = np.log1p(df["aylik_satis_tahmini"].fillna(ROZET_YOK_TAHMINI))
    return df

def _kaydet(metrikler, model, model_klasoru):
    os.makedirs(model_klasoru, exist_ok=True)
    if model is not None:
        joblib.dump(model, os.path.join(model_klasoru, f"{MODEL_ADI}.joblib"))
    with open(os.path.join(model_klasoru, f"{MODEL_ADI}_metrikler.json"), "w", encoding="utf-8") as f:
        json.dump(metrikler, f, ensure_ascii=False, indent=2)

def egit(veritabani=None, model_klasoru=MODEL_KLASORU):
    df = veri_setini_hazirla(veritabani)
    gun_sayisi = int(df["gun"].nunique()) if not df.empty else 0
    metrikler = {"egitim_zamani": datetime.now().strftime("%Y-%m-%d %H:%M"), "gun_sayisi": gun_sayisi,
                 "satir_sayisi": int(len(df)), "aktif": False}

    if gun_sayisi < MIN_GUN or len(df) < MIN_SATIR:
        metrikler["durum"] = (f"Yetersiz veri: {gun_sayisi}/{MIN_GUN} gün, {len(df)}/{MIN_SATIR} kayıt. "
                              "UCI modeli kullanılmaya devam ediliyor.")
        _kaydet(metrikler, None, model_klasoru)
        print(metrikler["durum"])
        return metrikler

    # Zamana göre ayır: son günler test (geleceği geçmişle tahmin etmemek için)
    gunler = sorted(df["gun"].unique())
    test_gunleri = set(gunler[-max(1, int(len(gunler) * TEST_ORANI)):])
    egitim, test = df[~df["gun"].isin(test_gunleri)], df[df["gun"].isin(test_gunleri)]

    def model_kur(ozellikler):
        kisit = [-1 if o == "log_fiyat_orani" else 0 for o in ozellikler]   # fiyat artınca talep artamaz
        return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, monotonic_cst=kisit, random_state=42)

    model = model_kur(OZELLIKLER).fit(egitim[OZELLIKLER], egitim["hedef"])
    fiyatsiz = [o for o in OZELLIKLER if o != "log_fiyat_orani"]
    karsilastirma = model_kur(fiyatsiz).fit(egitim[fiyatsiz], egitim["hedef"])

    mae_model = mean_absolute_error(test["hedef"], model.predict(test[OZELLIKLER]))
    mae_fiyatsiz = mean_absolute_error(test["hedef"], karsilastirma.predict(test[fiyatsiz]))
    iyilesme = 1 - mae_model / mae_fiyatsiz if mae_fiyatsiz > 0 else 0.0

    # Diğer özellikler tipik değerlerinde sabitken fiyat esnekliği
    referans = {o: float(egitim[o].median()) for o in fiyatsiz}
    def talep(oran):
        girdi = pd.DataFrame([{**referans, "log_fiyat_orani": np.log(oran)}])[OZELLIKLER]
        return np.expm1(model.predict(girdi))[0]
    esneklik = float((np.log(talep(1.1)) - np.log(talep(0.9))) / (np.log(1.1) - np.log(0.9)))

    aktif = iyilesme >= MIN_IYILESME and esneklik < 0
    metrikler.update({
        "aktif": aktif,
        "test_gun_sayisi": len(test_gunleri),
        "mae_log_model": round(mae_model, 4),
        "mae_log_fiyatsiz": round(mae_fiyatsiz, 4),
        "fiyat_bilgisinin_katkisi": round(iyilesme, 4),
        "ortalama_esneklik": round(esneklik, 3),
        "referans": referans,
        "ozellikler": OZELLIKLER,
        "oran_araligi": ORAN_ARALIGI,
        "durum": ("Stanley modeli aktif." if aktif else
                  f"Model eğitildi ama devreye alınmadı (fiyat katkısı %{iyilesme * 100:.1f}, esneklik {esneklik:.2f}). "
                  "UCI modeli kullanılmaya devam ediliyor."),
    })
    _kaydet(metrikler, model, model_klasoru)
    print(metrikler["durum"])
    return metrikler

if __name__ == "__main__":
    egit()

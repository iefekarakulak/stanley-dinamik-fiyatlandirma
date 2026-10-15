"""Talep (fiyat esnekliği) modeli eğitimi.

Veri: UCI Online Retail II (İngiltere merkezli online perakendeci, 2009-2011, ~1M satış satırı, CC BY 4.0)
https://archive.ics.uci.edu/dataset/502/online+retail+ii

Soru: Bir ürünün fiyatı normal fiyatına göre %X değişirse, haftalık satış adedi nasıl değişir?
- Satırlar ürün-hafta bazında toplanır (adet toplamı, o haftanın küçük siparişlerdeki liste fiyatı)
- fiyat_orani = haftalık liste fiyatı / ürünün eğitim dönemindeki medyan fiyatı
- Model, fiyat_oranı arttıkça talebin ARTMAMASI için monoton kısıtla eğitilir
- Değerlendirme zamana göre ayrılmış test setinde yapılır (gelecek veriyle geçmişi tahmin etmemek için)
"""
import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

PROJE = os.path.dirname(os.path.abspath(__file__))
VERI_DOSYASI = os.path.join(PROJE, "veri", "online_retail_ii.csv.gz")
EXCEL_DOSYASI = os.path.join(PROJE, "veri", "online_retail_II.xlsx")
MODEL_KLASORU = os.path.join(PROJE, "model")
TEST_BASLANGIC = "2011-07-01"
MIN_HAFTA = 20                  # Daha az haftası olan ürünlerden güvenilir fiyat-talep ilişkisi çıkmaz
ORAN_ARALIGI = (0.5, 2.0)       # Bu aralık dışındaki fiyat oranları veri hatası/özel fiyat sayılır
OZELLIKLER = ["log_fiyat_orani", "log_baz_talep", "log_son4_hafta", "ay"]

baslangic = time.time()

# İlk çalıştırmada Excel (~1 dk okuma) sıkıştırılmış CSV'ye çevrilir, sonraki çalıştırmalar CSV'den okur
if not os.path.exists(VERI_DOSYASI):
    if not os.path.exists(EXCEL_DOSYASI):
        sys.exit("Veri bulunamadı. https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip dosyasını "
                 "indirip içindeki online_retail_II.xlsx'i veri/ klasörüne çıkarın.")
    print("Excel CSV'ye çevriliyor (tek seferlik)...")
    sayfalar = pd.read_excel(EXCEL_DOSYASI, sheet_name=None)   # 2009-2010 ve 2010-2011 iki ayrı sayfa
    pd.concat(sayfalar.values(), ignore_index=True).to_csv(VERI_DOSYASI, index=False, compression="gzip")

print("Veri okunuyor...")
df = pd.read_csv(VERI_DOSYASI, dtype={"Invoice": str, "StockCode": str}, parse_dates=["InvoiceDate"])

# 1. Temizlik: iadeler (C ile başlayan faturalar), negatif/sıfır adet-fiyat, ürün olmayan kodlar (POST, M, BANK CHARGES...)
df = df[~df["Invoice"].str.startswith("C") & (df["Quantity"] > 0) & (df["Price"] > 0)
        & df["StockCode"].str.match(r"^\d")]
df["hafta"] = df["InvoiceDate"].dt.to_period("W").dt.start_time

# 2. Ürün-hafta tablosu
# Bu satıcı toptan alana birim fiyatı düşürüyor. Fiyatı tüm siparişlerden alırsak "çok alındığı için fiyat düşük"
# ilişkisini "fiyat düşük olduğu için çok alındı" diye öğreniriz (ters nedensellik). Bu yüzden liste fiyatı,
# sadece küçük siparişlerde (<= KUCUK_SIPARIS adet) en sık görülen fiyat olarak alınır.
KUCUK_SIPARIS = 6
adet = df.groupby(["StockCode", "hafta"])["Quantity"].sum().rename("adet")
kucuk = df[df["Quantity"] <= KUCUK_SIPARIS]
fiyat_sayisi = kucuk.groupby(["StockCode", "hafta", "Price"]).size().rename("satir").reset_index()
liste_fiyati = (fiyat_sayisi.sort_values("satir").groupby(["StockCode", "hafta"]).tail(1)
                .set_index(["StockCode", "hafta"])["Price"].rename("fiyat"))
h = pd.concat([adet, liste_fiyati], axis=1, join="inner").reset_index()

h = h[h.groupby("StockCode")["hafta"].transform("size") >= MIN_HAFTA]
egitim_maske = h["hafta"] < TEST_BASLANGIC

# 3. Ürünün "normal" fiyatı ve "normal" talebi SADECE eğitim döneminden hesaplanır (veri sızıntısı olmasın)
normal = h[egitim_maske].groupby("StockCode").agg(normal_fiyat=("fiyat", "median"), baz_talep=("adet", "median"))
h = h.merge(normal, on="StockCode", how="inner")
h["fiyat_orani"] = h["fiyat"] / h["normal_fiyat"]
h = h[h["fiyat_orani"].between(*ORAN_ARALIGI)]

h["log_fiyat_orani"] = np.log(h["fiyat_orani"])
h["log_baz_talep"] = np.log1p(h["baz_talep"])
# Ürünün yakın dönemdeki popülerliği: önceki 4 satış haftasının ortalaması (shift ile o haftanın kendisi dahil edilmez)
h = h.sort_values(["StockCode", "hafta"])
h["log_son4_hafta"] = np.log1p(h.groupby("StockCode")["adet"]
                               .transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean()))
h = h.dropna(subset=["log_son4_hafta"])
h["ay"] = h["hafta"].dt.month
h["hedef"] = np.log1p(h["adet"])

egitim = h[h["hafta"] < TEST_BASLANGIC]
test = h[h["hafta"] >= TEST_BASLANGIC]
print(f"Ürün sayısı: {h['StockCode'].nunique()} | Eğitim: {len(egitim)} ürün-hafta | Test: {len(test)} ürün-hafta")

# 4. Model: fiyat oranı arttıkça tahmini talep artamaz (monoton kısıt)
model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, monotonic_cst=[-1, 0, 0, 0], random_state=42)
model.fit(egitim[OZELLIKLER], egitim["hedef"])

# 5. Değerlendirme: "her hafta normal talebi kadar satar" diyen basit tahminle karşılaştır
tahmin = model.predict(test[OZELLIKLER])
mae_model = mean_absolute_error(test["hedef"], tahmin)
mae_baz = mean_absolute_error(test["hedef"], test["log_baz_talep"])

# Fiyatı değişen haftalarda model ne kadar iyi? (Asıl önemli olan bu haftalar)
degisen = (test["fiyat_orani"] - 1).abs() > 0.05
mae_model_d = mean_absolute_error(test.loc[degisen, "hedef"], tahmin[degisen.values])
mae_baz_d = mean_absolute_error(test.loc[degisen, "hedef"], test.loc[degisen, "log_baz_talep"])

# 6. Ortalama fiyat esnekliği: fiyat %10 artınca talep % kaç değişiyor?
referans_baz = float(egitim["log_baz_talep"].median())
def talep(oran, ay=6):
    girdi = pd.DataFrame({"log_fiyat_orani": [np.log(oran)], "log_baz_talep": [referans_baz],
                          "log_son4_hafta": [referans_baz], "ay": [ay]})
    return np.expm1(model.predict(girdi))[0]
esneklik = (np.log(talep(1.1)) - np.log(talep(0.9))) / (np.log(1.1) - np.log(0.9))

metrikler = {
    "veri": "UCI Online Retail II",
    "urun_sayisi": int(h["StockCode"].nunique()),
    "egitim_satir": int(len(egitim)),
    "test_satir": int(len(test)),
    "test_baslangic": TEST_BASLANGIC,
    "mae_log_model": round(mae_model, 4),
    "mae_log_baz": round(mae_baz, 4),
    "mae_log_model_fiyat_degisen": round(mae_model_d, 4),
    "mae_log_baz_fiyat_degisen": round(mae_baz_d, 4),
    "ortalama_esneklik": round(float(esneklik), 3),
    "referans_log_baz_talep": referans_baz,
    "oran_araligi": ORAN_ARALIGI,
    "ozellikler": OZELLIKLER,
}

os.makedirs(MODEL_KLASORU, exist_ok=True)
joblib.dump(model, os.path.join(MODEL_KLASORU, "talep_modeli.joblib"))
with open(os.path.join(MODEL_KLASORU, "talep_modeli_metrikler.json"), "w", encoding="utf-8") as f:
    json.dump(metrikler, f, ensure_ascii=False, indent=2)

print(json.dumps(metrikler, ensure_ascii=False, indent=2))
print(f"Eğitim {(time.time() - baslangic) / 60:.1f} dakikada tamamlandı.")

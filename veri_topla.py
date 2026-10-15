"""Amazon TR'deki tüm Stanley ilanlarını toplar (günde en fazla 1 kez, gunluk_guncelleme.py içinden).

Amazon'un marka filtresiyle tek arama yapılır, sonuçlar bitene kadar sayfa sayfa ilerlenir. Her ilanın başlığından
kategori, seri ve hacim çıkarılıp urun_gozlem tablosuna kaydedilir.
"""
from datetime import datetime

from scraper import genis_tarama
from kategori import kategorize_et
from database import veritabanini_hazirla, urun_gozlemlerini_kaydet

ARAMA_TERIMI = "stanley"
MARKA_FILTRESI = "Stanley"

# Amazon arama sonuçları en fazla ~7 sayfa gösterir; sonuçlar daha önce biterse tarama kendiliğinden durur
MAKS_SAYFA = 7
SAYFALAR_ARASI_BEKLEME = 45   # saniye: sık istek Amazon'un bot engelini tetikliyor

def main():
    veritabanini_hazirla()
    print(f"=== Veri toplama başladı: {datetime.now():%Y-%m-%d %H:%M} ===")

    sonuc = genis_tarama(ARAMA_TERIMI, MAKS_SAYFA, SAYFALAR_ARASI_BEKLEME, marka_filtresi=MARKA_FILTRESI)
    urunler = [{**u, **kategorize_et(u["baslik"])} for u in sonuc["urunler"]]

    # Engel çıksa bile o ana kadar toplananları kaydet
    if urunler:
        urun_gozlemlerini_kaydet(ARAMA_TERIMI, urunler)
    if sonuc["engellendi"]:
        print("Amazon engelledi, tarama yarıda kaldı (toplananlar kaydedildi).")

    ozet = {}
    for u in urunler:
        if not u["aksesuar"]:
            anahtar = (u["kategori"], u["seri"])
            ozet[anahtar] = ozet.get(anahtar, 0) + 1
    print(f"=== Veri toplama bitti: {len(urunler)} ilan "
          f"({sum(u['aksesuar'] for u in urunler)} aksesuar) ===")
    for (kategori, seri), adet in sorted(ozet.items(), key=lambda x: -x[1]):
        print(f"  {adet:>4}  {kategori} / {seri}")

if __name__ == "__main__":
    main()

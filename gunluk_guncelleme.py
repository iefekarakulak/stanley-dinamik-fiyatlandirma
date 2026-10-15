"""Günlük güncelleme: Amazon TR'den Stanley ilanlarını toplar, veri setine ekler ve Stanley talep modelini yeniden eğitir.

Windows Görev Zamanlayıcı her gün gunluk_calistir.bat üzerinden bu dosyayı çalıştırır.
Çıktılar logs/gunluk_guncelleme.log dosyasına eklenir.
"""
from datetime import datetime

import database
import stanley_modeli_egitimi
import veri_topla

def main():
    print(f"\n########## Günlük güncelleme: {datetime.now():%Y-%m-%d %H:%M} ##########")

    # 1. Bugünün verisi eklenir, geçmiş günler korunur
    try:
        veri_topla.main()
    except Exception as e:
        # Veri toplanamasa da (ör. Chrome hatası) model mevcut veriyle güncellenmeye devam eder
        print(f"[HATA] Veri toplama başarısız: {type(e).__name__}: {e}")

    # 2. Kategori kuralları geliştirildiyse geçmiş kayıtlar da yeni kurallarla kategorilensin
    print(f"Kategoriler yenilendi: {database.kategorileri_yenile()} kayıt")

    # 3. Birikmiş tüm günlerle
    print("--- Stanley talep modeli eğitimi ---")
    metrikler = stanley_modeli_egitimi.egit()
    print(f"Veri: {metrikler['gun_sayisi']} gün, {metrikler['satir_sayisi']} kayıt | Aktif: {metrikler['aktif']}")

if __name__ == "__main__":
    main()

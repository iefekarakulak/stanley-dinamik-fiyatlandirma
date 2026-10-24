"""Günlük güncelleme: Amazon TR'den Stanley ilanlarını toplar, veri setine ekler, Stanley talep modelini yeniden
eğitir ve demo verisini GitHub'a göndererek Streamlit Cloud'daki yayını günceller.

Windows Görev Zamanlayıcı bu dosyayı her gün 06:00'da ve oturum açıldığında pencere açmadan çalıştırır
(pythonw gunluk_guncelleme.py --log). Aynı gün birden fazla tetiklenirse Amazon'a gereksiz istek gitmemesi için
başarılı bir taramadan sonra ya da MAKS_GUNLUK_DENEME denemeden sonra atlanır.
Çıktılar logs/gunluk_guncelleme.log dosyasına eklenir.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

import database
import stanley_modeli_egitimi
import veri_topla

# Engellenen ya da yarıda kalan bir tarama, yayındaki demo verisinin yerini almasın
MIN_DEMO_ILAN = 100
# Engellenen günlerde en fazla bu kadar deneme (sık deneme Amazon engelini uzatır)
MAKS_GUNLUK_DENEME = 2
LOG_KLASORU = os.path.join(database.PROJE, "logs")
DENEME_DOSYASI = os.path.join(LOG_KLASORU, "denemeler.json")

def _bugunun_denemeleri(artir=False):
    bugun = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(DENEME_DOSYASI, encoding="utf-8") as f:
            kayit = json.load(f)
    except (OSError, ValueError):
        kayit = {}
    if artir:
        kayit = {bugun: kayit.get(bugun, 0) + 1}   # sadece bugünü tut
        os.makedirs(LOG_KLASORU, exist_ok=True)
        with open(DENEME_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(kayit, f)
    return kayit.get(bugun, 0)

def bugun_atlanmali_mi():
    """Bugün başarılı tarama yapıldıysa ya da deneme hakkı dolduysa atlama nedenini döndürür, yoksa None."""
    if database.gunun_ilan_sayisi() >= MIN_DEMO_ILAN:
        return "bugün zaten başarılı bir tarama yapıldı"
    if _bugunun_denemeleri() >= MAKS_GUNLUK_DENEME:
        return f"bugün {MAKS_GUNLUK_DENEME} deneme yapıldı (Amazon engelledi), yarın tekrar denenecek"
    return None

def _git(proje, *argumanlar):
    git = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
    return subprocess.run([git, "-C", proje, *argumanlar], capture_output=True, text=True, encoding="utf-8")

def demo_verisini_yayinla(proje=database.PROJE):
    """Demo dosyasını son taramadan yeniler; SADECE bu dosyayı commit'leyip GitHub'a gönderir.
    Çalışma klasöründeki diğer değişikliklere dokunmaz. Streamlit Cloud gönderimi görünce kendini günceller."""
    ilan_sayisi = database.ornek_veriyi_guncelle(gun=1)
    dosya = os.path.relpath(database.ORNEK_VERI, proje)
    if _git(proje, "diff", "--quiet", "--", dosya).returncode == 0:
        print("Demo verisi değişmedi, gönderilmedi.")
        return False

    mesaj = f"Demo verisi: {datetime.now():%Y-%m-%d} Amazon TR taraması ({ilan_sayisi} ilan)"
    commit = _git(proje, "commit", "-m", mesaj, "--", dosya)
    if commit.returncode != 0:
        print(f"[HATA] Demo verisi commit'lenemedi: {commit.stderr.strip() or commit.stdout.strip()}")
        return False
    push = _git(proje, "push", "-q")
    if push.returncode != 0:
        print(f"[HATA] Demo verisi GitHub'a gönderilemedi (commit yerelde duruyor): {push.stderr.strip()}")
        return False
    print(f"Demo verisi güncellendi ve GitHub'a gönderildi: {ilan_sayisi} ilan")
    return True

def main():
    print(f"\n########## Günlük güncelleme: {datetime.now():%Y-%m-%d %H:%M} ##########")
    neden = bugun_atlanmali_mi()
    if neden:
        print(f"Atlandı: {neden}.")
        return
    _bugunun_denemeleri(artir=True)

    # 1. Bugünün verisi eklenir, geçmiş günler korunur
    tarama = {"ilan_sayisi": 0, "engellendi": True}
    try:
        tarama = veri_topla.main()
    except Exception as e:
        # Veri toplanamasa da (ör. Chrome hatası) model mevcut veriyle güncellenmeye devam eder
        print(f"[HATA] Veri toplama başarısız: {type(e).__name__}: {e}")

    # 2. Kategori kuralları geliştirildiyse geçmiş kayıtlar da yeni kurallarla kategorilensin
    print(f"Kategoriler yenilendi: {database.kategorileri_yenile()} kayıt")

    # 3. Birikmiş tüm günlerle
    print("--- Stanley talep modeli eğitimi ---")
    metrikler = stanley_modeli_egitimi.egit()
    print(f"Veri: {metrikler['gun_sayisi']} gün, {metrikler['satir_sayisi']} kayıt | Aktif: {metrikler['aktif']}")

    # 4. Yayındaki demo: yalnızca tam ve engelsiz bir taramadan sonra
    print("--- Demo verisi (Streamlit Cloud) ---")
    if tarama["engellendi"] or tarama["ilan_sayisi"] < MIN_DEMO_ILAN:
        print(f"Tarama eksik ({tarama['ilan_sayisi']} ilan, engel: {tarama['engellendi']}); "
              "yayındaki demo verisi değiştirilmedi.")
    else:
        try:
            demo_verisini_yayinla()
        except Exception as e:
            print(f"[HATA] Demo verisi yayınlanamadı: {type(e).__name__}: {e}")

if __name__ == "__main__":
    if "--log" in sys.argv:
        # pythonw ile konsolsuz çalışırken çıktılar doğrudan log dosyasına yazılır
        os.makedirs(LOG_KLASORU, exist_ok=True)
        sys.stdout = sys.stderr = open(os.path.join(LOG_KLASORU, "gunluk_guncelleme.log"), "a",
                                       encoding="utf-8", buffering=1)
    main()

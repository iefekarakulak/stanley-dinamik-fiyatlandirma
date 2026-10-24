"""Günlük güncellemenin durumunu özetler: python durum.py"""
import json
import os
import sqlite3
import sys
from datetime import datetime

import database
import gunluk_guncelleme

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def son_calisma():
    yol = os.path.join(gunluk_guncelleme.LOG_KLASORU, "gunluk_guncelleme.log")
    if not os.path.exists(yol):
        return None, []
    with open(yol, encoding="utf-8") as f:
        satirlar = f.read().splitlines()
    baslangic = max((i for i, s in enumerate(satirlar) if s.startswith("########## Günlük güncelleme:")), default=None)
    if baslangic is None:
        return None, []
    return satirlar[baslangic].strip("# ").replace("Günlük güncelleme: ", ""), satirlar[baslangic + 1:]

def main():
    bugun = datetime.now().strftime("%Y-%m-%d")
    print(f"=== Stanley günlük güncelleme durumu ({datetime.now():%Y-%m-%d %H:%M}) ===\n")

    zaman, satirlar = son_calisma()
    if zaman is None:
        print("Son çalışma        : log bulunamadı (görev henüz hiç çalışmamış)")
    else:
        metin = "\n".join(satirlar)
        if "Atlandı" in metin:
            sonuc = "⏭  atlandı (" + next(s for s in satirlar if "Atlandı" in s).split(": ", 1)[1] + ")"
        elif "engelledi" in metin:
            sonuc = "❌ Amazon engelledi"
        elif "[HATA]" in metin:
            sonuc = "⚠  hata: " + next(s for s in satirlar if "[HATA]" in s)
        elif "Veri toplama bitti" in metin:
            sonuc = "✅ " + next(s for s in satirlar if "Veri toplama bitti" in s).strip("= ")
        else:
            sonuc = "⏳ yarıda kalmış ya da hâlâ çalışıyor"
        print(f"Son çalışma        : {zaman}  →  {sonuc}")

    bugunku = database.gunun_ilan_sayisi(bugun)
    print(f"Bugünkü tarama     : {'✅ ' + str(bugunku) + ' ilan' if bugunku else '— henüz başarılı tarama yok'}")

    with sqlite3.connect(database.VERITABANI) as conn:
        gunler = conn.execute("SELECT substr(tarih,1,10), COUNT(*) FROM urun_gozlem GROUP BY 1 ORDER BY 1").fetchall()
    if gunler:
        print(f"Son başarılı tarama: {gunler[-1][0]} ({gunler[-1][1]} ilan)")
        print(f"Veri seti          : {len(gunler)} gün, {sum(n for _, n in gunler)} kayıt")

    try:
        with open(os.path.join(database.PROJE, "model", "stanley_talep_modeli_metrikler.json"), encoding="utf-8") as f:
            model = json.load(f)
        print(f"Stanley modeli     : {'✅ aktif' if model['aktif'] else '⏳ ' + model['durum']}")
    except OSError:
        print("Stanley modeli     : henüz eğitilmedi")

    demo_commit = gunluk_guncelleme._git(database.PROJE, "log", "-1", "--format=%cd  %s", "--date=format:%Y-%m-%d %H:%M",
                                         "--", os.path.relpath(database.ORNEK_VERI, database.PROJE)).stdout.strip()
    print(f"Bulut demo verisi  : {demo_commit or 'bilinmiyor'}")

if __name__ == "__main__":
    main()

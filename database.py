"""SQLite katmanı: her gün toplanan Stanley ilan gözlemleri (urun_gozlem) ve demo verisi."""
import json
import os
import sqlite3
from datetime import datetime

from kategori import kategorize_et

PROJE = os.path.dirname(os.path.abspath(__file__))
# Script hangi klasörden çalıştırılırsa çalıştırılsın veritabanı proje klasöründe olsun
VERITABANI = os.path.join(PROJE, "fiyat_motoru.db")
# Demo modu: veritabanı olmadan denenebilmesi için gerçek bir taramanın anlık görüntüsü (depoda bulunur)
ORNEK_VERI = os.path.join(PROJE, "ornek_veri", "stanley_ornek.json")
TARIH_FORMATI = "%Y-%m-%d %H:%M:%S"

def _baglan():
    return sqlite3.connect(VERITABANI)

def _simdi():
    return datetime.now().strftime(TARIH_FORMATI)

def veritabanini_hazirla():
    with _baglan() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS urun_gozlem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarih TEXT,
                arama_terimi TEXT,
                sayfa INTEGER,
                asin TEXT,
                baslik TEXT,
                fiyat REAL,
                hacim_litre REAL,
                kategori TEXT,
                seri TEXT,
                alt_seri TEXT,
                aksesuar INTEGER,
                ucuncu_parti INTEGER,
                aylik_satis_rozeti TEXT,
                aylik_satis_tahmini INTEGER,
                yorum_sayisi INTEGER,
                puan REAL,
                onceki_fiyat REAL,
                stok_adedi INTEGER,
                sponsorlu INTEGER
            )
        ''')

def urun_gozlemlerini_kaydet(arama_terimi, urunler, zaman=None):
    """veri_topla.py'nin bulduğu ilanları kategorileriyle kaydeder (urunler: kategori.kategorize_et alanlarını içerir)."""
    veritabanini_hazirla()
    zaman = zaman or _simdi()
    with _baglan() as conn:
        conn.executemany('''
            INSERT INTO urun_gozlem (tarih, arama_terimi, sayfa, asin, baslik, fiyat, hacim_litre,
                                     kategori, seri, alt_seri, aksesuar, ucuncu_parti,
                                     aylik_satis_rozeti, aylik_satis_tahmini, yorum_sayisi, puan,
                                     onceki_fiyat, stok_adedi, sponsorlu)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [(zaman, arama_terimi, u.get("sayfa"), u.get("asin"), u["baslik"], u["fiyat"], u.get("hacim_litre"),
               u["kategori"], u["seri"], u["alt_seri"], int(u["aksesuar"]), int(u["ucuncu_parti"]),
               u.get("aylik_satis_rozeti"), u.get("aylik_satis_tahmini"), u.get("yorum_sayisi"), u.get("puan"),
               u.get("onceki_fiyat"), u.get("stok_adedi"), int(bool(u.get("sponsorlu"))))
              for u in urunler])
    print(f"[VERİ] '{arama_terimi}': {len(urunler)} ilan kaydedildi")

def gunun_ilan_sayisi(gun=None):
    """Belirtilen günde (varsayılan bugün) kaydedilen ilan sayısı."""
    veritabanini_hazirla()
    gun = gun or datetime.now().strftime("%Y-%m-%d")
    with _baglan() as conn:
        return conn.execute("SELECT COUNT(*) FROM urun_gozlem WHERE substr(tarih, 1, 10) = ?", (gun,)).fetchone()[0]

def kategorileri_yenile(kategorize=kategorize_et):
    """Kategori kuralları geliştikçe TÜM geçmiş kayıtları yeniden kategoriler (kategori başlıktan türetilen bir alan)."""
    veritabanini_hazirla()
    with _baglan() as conn:
        satirlar = conn.execute("SELECT id, baslik FROM urun_gozlem").fetchall()
        guncel = []
        for kayit_id, baslik in satirlar:
            k = kategorize(baslik)
            guncel.append((k["kategori"], k["seri"], k["alt_seri"], int(k["aksesuar"]), int(k["ucuncu_parti"]), kayit_id))
        conn.executemany('''UPDATE urun_gozlem SET kategori = ?, seri = ?, alt_seri = ?, aksesuar = ?, ucuncu_parti = ?
                            WHERE id = ?''', guncel)
    return len(guncel)

def _analize_uygun(ilan):
    return not ilan["aksesuar"] and not ilan["ucuncu_parti"] and ilan["fiyat"] is not None and ilan["hacim_litre"] is not None

def kayitli_ilanlar(gun=7, demo=False):
    """Analizde kullanılacak ilanlar: her ilanın, SON TARAMADAN geriye `gun` gün içindeki EN GÜNCEL kaydı.
    Pencere bugünden değil son taramadan sayılır: Amazon birkaç gün üst üste engellerse eldeki veri kaybolmaz.
    Aksesuarlar, Stanley Tools aletleri, başka firmaların uyumlu ürünleri ve hacmi okunamayan ilanlar hariç.
    demo=True: veritabanı yerine ornek_veri/stanley_ornek.json kullanılır."""
    if demo:
        with open(ORNEK_VERI, encoding="utf-8") as f:
            ilanlar = json.load(f)["ilanlar"]
        # Kategori kuralları güncellendiyse demo verisi de güncel kurallarla okunur
        ilanlar = [{**i, **kategorize_et(i["baslik"])} for i in ilanlar]
        return [i for i in ilanlar if _analize_uygun(i)]

    veritabanini_hazirla()
    with _baglan() as conn:
        conn.row_factory = sqlite3.Row
        satirlar = conn.execute('''
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY COALESCE(asin, baslik) ORDER BY tarih DESC) AS sira
                FROM urun_gozlem
                WHERE tarih >= datetime((SELECT MAX(tarih) FROM urun_gozlem), ?)
            ) WHERE sira = 1
        ''', (f"-{int(gun)} days",)).fetchall()
    return [i for i in map(dict, satirlar) if _analize_uygun(i)]

def ornek_veriyi_guncelle(gun=1):
    """Demo verisini veritabanındaki son taramadan yeniden oluşturur (GitHub'daki canlı demo bu dosyayı kullanır)."""
    alanlar = ["tarih", "asin", "baslik", "fiyat", "hacim_litre", "aylik_satis_rozeti", "aylik_satis_tahmini",
               "yorum_sayisi", "puan", "onceki_fiyat", "stok_adedi", "sponsorlu"]
    ilanlar = [{a: i[a] for a in alanlar} for i in kayitli_ilanlar(gun)]
    if not ilanlar:
        return 0   # mevcut demo verisi boş bir taramayla ezilmesin
    os.makedirs(os.path.dirname(ORNEK_VERI), exist_ok=True)
    with open(ORNEK_VERI, "w", encoding="utf-8") as f:
        json.dump({"aciklama": "Demo modu için Amazon TR'den toplanmış gerçek Stanley ilanlarının anlık görüntüsü.",
                   "tarama_tarihi": max(i["tarih"] for i in ilanlar)[:10],
                   "ilanlar": ilanlar}, f, ensure_ascii=False, indent=1)
    return len(ilanlar)

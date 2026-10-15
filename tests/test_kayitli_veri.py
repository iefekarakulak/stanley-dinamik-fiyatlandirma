"""Kayıtlı veriden fiyatlandırma: geçici bir veritabanıyla uçtan uca (Amazon'a gitmez)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api
import database
from kategori import kategorize_et

ORTAK = dict(alis_maliyeti=1200, komisyon_orani=0.15, kargo=60, min_marj=0.10, aylik_satis=30, gun=7)

def ilan(asin, baslik, fiyat, hacim):
    return {"asin": asin, "baslik": baslik, "fiyat": fiyat, "hacim_litre": hacim, "sayfa": 1, **kategorize_et(baslik)}

@pytest.fixture(autouse=True)
def gecici_veritabani(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "VERITABANI", str(tmp_path / "test.db"))
    database.urun_gozlemlerini_kaydet("stanley", [
        ilan("A1", "stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - siyah", 2200, 1.18),
        ilan("A2", "stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - krem", 2300, 1.18),
        ilan("A3", "stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - indigo", 2400, 1.18),
        ilan("A4", "stanley quencher h2.0 flowstate tumbler 20oz pipetli termos bardak 0.60 litre", 2000, 0.59),
        ilan("A5", "stanley quencher h2.0 flowstate tumbler pipetli termos bardak 0.60 litre", 2050, 0.6),
        ilan("X1", "stanley quencher önyükleme ve hasir kapak kapaği", 150, 1.18),              # aksesuar
        ilan("X2", "yenigeldi stanley quencher 30/40 oz uyumlu yedek pipet seti", 130, 1.18),   # 3. parti aksesuar
    ])

def test_secenekler_aksesuarsiz_ve_yakin_hacimler_birlesik():
    secenekler = api.urun_secenekleri(gun=7)["secenekler"]
    assert all(s["kategori"] != "Aksesuar" for s in secenekler)
    hacimler = sorted(s["hacim"] for s in secenekler)
    assert len(hacimler) == 2              # 0.59 ve 0.6 tek seçenek
    assert hacimler[1] == pytest.approx(1.18)

def test_kayitli_fiyat_aksesuarlari_katmaz():
    sonuc = api.kayitli_fiyat_hesapla(kategori="Pipetli Bardak", seri="Quencher", hacim=1.18,
                                      alt_seri="H2.0 FlowState", renk="Fark etmez", **ORTAK)
    piyasa = sonuc["piyasa"]
    assert piyasa["satici_sayisi"] == 3
    assert piyasa["en_ucuz"] == 2200       # 150 TL'lik kapak piyasa fiyatına karışmadı
    assert piyasa["medyan"] == 2300

def test_ayni_ilanin_en_guncel_fiyati_kullanilir():
    database.urun_gozlemlerini_kaydet("stanley", [
        ilan("A1", "stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - siyah", 2100, 1.18)],
        zaman="2099-01-01 00:00:00")
    sonuc = api.kayitli_fiyat_hesapla(kategori="Pipetli Bardak", seri="Quencher", hacim=1.18,
                                      alt_seri="", renk="Fark etmez", **ORTAK)
    assert sonuc["piyasa"]["satici_sayisi"] == 3   # A1 iki kez sayılmadı
    assert sonuc["piyasa"]["en_ucuz"] == 2100      # A1'in yeni fiyatı

def test_veri_olmayan_urun_hata_verir():
    sonuc = api.kayitli_fiyat_hesapla(kategori="Termos", seri="Classic Legendary", hacim=1.0,
                                      alt_seri="", renk="Fark etmez", **ORTAK)
    assert "hata" in sonuc

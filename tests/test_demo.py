"""Demo modu: depodaki örnek veriyle (veritabanı olmadan) uçtan uca çalışmalı."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api
import database

ORTAK = dict(alis_maliyeti=1200, komisyon_orani=0.15, kargo=60, min_marj=0.10, aylik_satis=30, gun=7)

def test_demo_verisi_aksesuar_ve_alet_icermez():
    ilanlar = database.kayitli_ilanlar(demo=True)
    assert len(ilanlar) > 100
    assert not any(i["aksesuar"] or i["ucuncu_parti"] for i in ilanlar)

def test_demo_her_secenek_icin_fiyat_hesaplanir():
    secenekler = api.urun_secenekleri(gun=7, demo=True)["secenekler"]
    assert secenekler
    for s in secenekler:
        sonuc = api.kayitli_fiyat_hesapla(kategori=s["kategori"], seri=s["seri"], hacim=s["hacim"],
                                          alt_seri=s["alt_seri"], renk="Fark etmez", demo=True, **ORTAK)
        assert "hata" not in sonuc, s
        piyasa = sonuc["piyasa"]
        assert piyasa["en_ucuz"] <= piyasa["medyan"] <= piyasa["en_pahali"]
        assert sonuc["onerilen_aksiyon_fiyati_TL"] >= sonuc["taban_fiyat_TL"]

def test_demo_veritabanina_dokunmaz(tmp_path, monkeypatch):
    olmayan = tmp_path / "yok.db"
    monkeypatch.setattr(database, "VERITABANI", str(olmayan))
    assert database.kayitli_ilanlar(demo=True)
    assert not olmayan.exists()

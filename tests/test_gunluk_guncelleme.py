"""Günlük güncelleme aynı gün birden fazla tetiklendiğinde Amazon'a gereksiz istek göndermemeli."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database
import gunluk_guncelleme
from kategori import kategorize_et

@pytest.fixture(autouse=True)
def gecici(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "VERITABANI", str(tmp_path / "test.db"))
    monkeypatch.setattr(gunluk_guncelleme, "LOG_KLASORU", str(tmp_path / "logs"))
    monkeypatch.setattr(gunluk_guncelleme, "DENEME_DOSYASI", str(tmp_path / "logs" / "denemeler.json"))
    taramalar = []
    def sahte_tarama():
        taramalar.append(1)
        return {"ilan_sayisi": 0, "engellendi": True}
    monkeypatch.setattr(gunluk_guncelleme.veri_topla, "main", sahte_tarama)
    monkeypatch.setattr(gunluk_guncelleme.stanley_modeli_egitimi, "egit",
                        lambda: {"gun_sayisi": 0, "satir_sayisi": 0, "aktif": False})
    return taramalar

def test_engellenen_gunde_en_fazla_iki_deneme(gecici):
    for _ in range(4):   # ör. 06:00 + üç kez oturum açma
        gunluk_guncelleme.main()
    assert len(gecici) == gunluk_guncelleme.MAKS_GUNLUK_DENEME

def test_basarili_taramadan_sonra_atlanir(gecici):
    baslik = "stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre"
    database.urun_gozlemlerini_kaydet("stanley", [
        {"asin": f"A{i}", "baslik": baslik, "fiyat": 2000 + i, "hacim_litre": 1.18, **kategorize_et(baslik)}
        for i in range(gunluk_guncelleme.MIN_DEMO_ILAN)])
    gunluk_guncelleme.main()
    assert gecici == []

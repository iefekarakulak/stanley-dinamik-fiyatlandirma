"""Günlük eğitilen Stanley talep modeli: veri yetersizken devreye girmemeli, yeterli veride fiyat etkisini öğrenmeli."""
import os
import sys
from datetime import date, timedelta

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database
import stanley_modeli_egitimi
import talep

GRUPLAR = [("Pipetli Bardak", "Quencher", "H2.0 FlowState", 1.18, 2200),
           ("Pipetli Bardak", "Quencher", "ProTour", 1.18, 2400),
           ("Termos", "Classic Legendary", None, 1.0, 2100),
           ("Termos", "Classic Legendary", None, 1.4, 2500)]

def rozet(satis):
    """Amazon gibi: 50'nin altında rozet yok, üstünde kaba aralıklar (50, 100, 200, 300...)."""
    if satis < 50:
        return None
    return 50 if satis < 100 else int(satis // 100 * 100)

def sentetik_veri_yaz(gun_sayisi, esneklik=-2.0, tohum=0):
    """Her gün her grupta 15 ilan; fiyatlar rastgele oynar, satış = popülerlik x (fiyat oranı)^esneklik."""
    rng = np.random.default_rng(tohum)
    populerlik = {(g, i): rng.uniform(40, 400) for g in range(len(GRUPLAR)) for i in range(15)}
    for d in range(gun_sayisi):
        gun = (date(2099, 1, 1) + timedelta(days=d)).isoformat()
        ilanlar = []
        for g, (kategori, seri, alt_seri, hacim, taban) in enumerate(GRUPLAR):
            for i in range(15):
                oran = rng.uniform(0.85, 1.15)
                satis = populerlik[(g, i)] * oran ** esneklik
                ilanlar.append({"asin": f"G{g}I{i}", "baslik": f"stanley {seri} {i}", "fiyat": round(taban * oran, 2),
                                "hacim_litre": hacim, "sayfa": 1, "kategori": kategori, "seri": seri,
                                "alt_seri": alt_seri, "aksesuar": False, "ucuncu_parti": False,
                                "aylik_satis_tahmini": rozet(satis), "yorum_sayisi": int(populerlik[(g, i)] * 20),
                                "puan": 4.5})
        database.urun_gozlemlerini_kaydet("stanley", ilanlar, zaman=f"{gun} 10:00:00")

@pytest.fixture
def gecici(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "VERITABANI", str(tmp_path / "test.db"))
    return str(tmp_path / "model")

def test_yetersiz_veride_devreye_girmez(gecici):
    sentetik_veri_yaz(gun_sayisi=3)
    metrikler = stanley_modeli_egitimi.egit(model_klasoru=gecici)
    assert metrikler["aktif"] is False
    assert "Yetersiz veri: 3/14 gün" in metrikler["durum"]

def test_yeterli_veride_fiyat_etkisini_ogrenir_ve_devreye_girer(gecici, monkeypatch):
    sentetik_veri_yaz(gun_sayisi=20, esneklik=-2.0)
    metrikler = stanley_modeli_egitimi.egit(model_klasoru=gecici)
    assert metrikler["aktif"] is True
    assert metrikler["ortalama_esneklik"] < -0.5             # fiyat artınca satış belirgin şekilde düşüyor
    assert metrikler["fiyat_bilgisinin_katkisi"] > 0.03

    # talep.py artık Stanley modelini kullanmalı
    monkeypatch.setattr(talep, "_MODEL_KLASORU", gecici)
    _, _, kaynak = talep.aktif_model()
    assert kaynak.startswith("Stanley")
    carpanlar = talep.talep_carpani([0.9, 1.0, 1.1])
    assert carpanlar[1] == pytest.approx(1.0)                 # medyan fiyatta çarpan 1
    assert carpanlar[0] > 1.0 > carpanlar[2]                  # ucuzda daha çok, pahalıda daha az satış

def test_fiyatin_etkisi_yoksa_devreye_girmez(gecici):
    # Satış fiyattan bağımsız: model "fiyat önemli" diye uydurmamalı
    sentetik_veri_yaz(gun_sayisi=20, esneklik=0.0)
    metrikler = stanley_modeli_egitimi.egit(model_klasoru=gecici)
    assert metrikler["aktif"] is False

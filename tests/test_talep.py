import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fiyat_hesap import buybox_referansi
from talep import buybox_payi, kar_egrisi, talep_carpani

def test_normal_fiyatta_talep_carpani_bir():
    assert talep_carpani([1.0])[0] == pytest.approx(1.0)

def test_fiyat_arttikca_talep_artmaz():
    carpanlar = talep_carpani(np.linspace(0.6, 1.6, 30))
    assert np.all(np.diff(carpanlar) <= 1e-9)

def test_buybox_payi_rakip_fiyatinda_yarim():
    assert buybox_payi(2000, 2000) == pytest.approx(0.5)
    assert buybox_payi(1950, 2000) > 0.9
    assert buybox_payi(2050, 2000) < 0.1

def test_aykiri_ucuz_rakip_buybox_referansi_olmaz():
    assert buybox_referansi([1500, 2290, 2340, 2400], medyan=2315) == 2290
    assert buybox_referansi([2200, 2290, 2340], medyan=2290) == 2200

def test_optimum_tabanin_altinda_olmaz_ve_rakibin_biraz_altinda():
    sonuc = kar_egrisi(medyan=2340, rakip=2200, taban=1680, aylik_satis=30,
                       alis_maliyeti=1200, komisyon_orani=0.15, kargo=60)
    assert sonuc["optimum_fiyat"] >= 1680
    assert 2200 * 0.9 < sonuc["optimum_fiyat"] < 2200
    assert all(n["fiyat"] >= 1680 for n in sonuc["egri"])

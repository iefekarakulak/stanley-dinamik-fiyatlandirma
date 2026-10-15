import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fiyat_hesap import birim_net_kar, taban_fiyat, strateji_belirle

# Ortak satıcı parametreleri: 1200 TL maliyet, %15 komisyon, 60 TL kargo, %10 minimum marj
PARAM = dict(alis_maliyeti=1200, komisyon_orani=0.15, kargo=60, min_marj=0.10)

def test_birim_net_kar():
    # 2000 - 300 komisyon - 1200 maliyet - 60 kargo
    assert birim_net_kar(2000, 1200, 0.15, 60) == pytest.approx(440)

def test_taban_fiyatta_marj_tam_olarak_minimum():
    taban = taban_fiyat(**PARAM)
    assert taban == pytest.approx(1260 / 0.75)
    assert birim_net_kar(taban, 1200, 0.15, 60) / taban == pytest.approx(0.10)

def test_imkansiz_parametreler_hata_verir():
    with pytest.raises(ValueError):
        taban_fiyat(1200, 0.6, 60, 0.5)

def test_normal_piyasada_en_ucuzun_altina_iner():
    sonuc = strateji_belirle(en_ucuz_rakip=2200, medyan=2325, **PARAM)
    assert sonuc["onerilen_fiyat"] == 2195

def test_aykiri_ucuz_rakipte_medyana_gore_konumlanir():
    sonuc = strateji_belirle(en_ucuz_rakip=1500, medyan=2325, **PARAM)
    assert sonuc["onerilen_fiyat"] == pytest.approx(2325 * 0.95)

def test_asla_taban_fiyatin_altini_onermez():
    # Rakip 1700 TL'de, taban fiyat 1680 TL: en ucuz - 5 = 1695 hâlâ üstünde
    assert strateji_belirle(1700, 1750, **PARAM)["onerilen_fiyat"] == 1695
    # Rakip 1600 TL'de: 1595 tabanın altında kalır, taban önerilir
    sonuc = strateji_belirle(1600, 1650, **PARAM)
    assert sonuc["onerilen_fiyat"] == pytest.approx(1680)
    assert "taban" in sonuc["strateji"]

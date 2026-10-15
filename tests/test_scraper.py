"""Amazon TR kartlarında görülen gerçek metinlerle ayrıştırma testleri (tarayıcı açmaz)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kategori import basliktaki_hacimler, kucuk_harf, renk_eslesiyor_mu
from scraper import sayiya_cevir, tl_cevir

@pytest.mark.parametrize("metin, beklenen", [
    ("Geçen ay 300 adetten fazla satın alındı", 300),
    ("Geçen ay 1 B adetten fazla satın alındı", 1000),
    ("6.937 derecelendirme", 6937),
    ("84 derecelendirme", 84),
])
def test_sayiya_cevir(metin, beklenen):
    assert sayiya_cevir(metin) == beklenen

@pytest.mark.parametrize("metin, beklenen", [
    ("2.218,50 TL", 2218.5),
    ("2.499,00 TL", 2499.0),
    ("1.481,85 TL", 1481.85),
])
def test_tl_cevir(metin, beklenen):
    assert tl_cevir(metin) == pytest.approx(beklenen)

@pytest.mark.parametrize("baslik, beklenen", [
    ("stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - krem 2.0", [1.18]),
    ("stanley classic legendary vakumlu çelik termos, 1 l", [1.0]),
    ("thermos termos 750 ml", [0.75]),
    ("stanley the quencher h2.o flowstate tumbler 1.18l / 40oz", [1.18, 1.18]),
])
def test_basliktaki_hacimler(baslik, beklenen):
    assert basliktaki_hacimler(baslik) == pytest.approx(beklenen)

def test_turkce_kucuk_harf():
    # İ/I/ı hepsi "i" olur (Amazon başlıklarında Türkçe ve İngilizce karışık yazıldığı için); diğer harfler korunur
    assert kucuk_harf("STANLEY İnce Işık") == "stanley ince işik"

def test_renk_eslesmesi():
    assert renk_eslesiyor_mu("stanley quencher 1.18 litre - siyah", "siyah") is True
    assert renk_eslesiyor_mu("stanley quencher 1.18 litre - yeşil (shale)", "siyah") is False
    assert renk_eslesiyor_mu("stanley quencher paslanmaz çelik", "çelik") is None   # filtrelenemeyen renk

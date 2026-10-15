"""Amazon TR'den toplanan gerçek Stanley başlıklarıyla kategorilendirme testleri."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kategori import kategorize_et

@pytest.mark.parametrize("baslik, kategori, seri, alt_seri", [
    ("stanley classic legendary vakumlu çelik termos, 1 l", "Termos", "Classic Legendary", None),
    ("stanley classic legendary termos 0,94 l - 24 saat sicakliği korur - termos şişe", "Termos", "Classic Legendary", None),
    ("stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - indigo", "Pipetli Bardak", "Quencher", "H2.0 FlowState"),
    ("stanley the quencher pro tour pipetli termos, 1.18 l, kül", "Pipetli Bardak", "Quencher", "ProTour"),
    ("stanley 10-13002-072 termos, 1.18 l, kirmizi", "Pipetli Bardak", "Quencher", "Fluted"),          # ürün kodundan
    ("stanley classic legendary kaşikli yemek termosu 0.4l", "Yemek Termosu", "Classic Legendary", None),
    ("stanley klasik cep matarasi 0.23 litre - mat siyah", "Cep Matarası", "Classic Legendary", None),
    ("stanley the transit fliptop mug termos 0.47 litre - siyah 2.0", "Kupa & Bardak", "Transit", None),
    ("stanley aerolight iceflow fast flow içecek şişesi, 0.6 l", "Su Şişesi", "IceFlow", None),
    ("stanley the wellspring termos, 0.70 l, yeşil", "Su Şişesi", "Wellspring", None),
])
def test_urun_kategorileri(baslik, kategori, seri, alt_seri):
    k = kategorize_et(baslik)
    assert (k["kategori"], k["seri"], k["alt_seri"]) == (kategori, seri, alt_seri)
    assert not k["aksesuar"]

@pytest.mark.parametrize("baslik", [
    "stanley quencher uyumlu sizdirmaz silikon tipa (siyah)",
    "stanley carry all quencher taşima çantasi 1.18 l için - krem",
    "stanley quencher önyükleme ve hasir kapak kapaği",
    "1 set (3 parça) beyaz sizdirmaz kapak seti stanley quencher 40 oz ve 30 oz termos modelleri ile uyumlu",
    "yenigeldi stanley quencher 30/40 oz uyumlu yedek pipet seti, 6 adet pipet ve 1 temizleme firçasi",
])
def test_aksesuarlar_ayrilir(baslik):
    assert kategorize_et(baslik)["kategori"] == "Aksesuar"

@pytest.mark.parametrize("baslik", [
    # Gerçek ürünler: "kapak" ve "uyumlu" kelimeleri geçse de aksesuar DEĞİL
    "stanley quencher h2.0 sapli ve pipetli bardak 20 oz | flowstate 3 pozisyonlu kapak | seyahat için uyumlu bardak",
    "stanley quencher protour kapakli hasir bardak sizdirmaz kapakli 14 oz | seyahat için uyumlu bardak",
])
def test_kapak_ve_uyumlu_gecen_gercek_urunler(baslik):
    assert kategorize_et(baslik)["kategori"] == "Pipetli Bardak"

@pytest.mark.parametrize("baslik", [
    # Stanley Tools: aynı adlı alet markası, termos analizine girmemeli
    "stanley sta31517 zimpara, kirmizi, 5 adet, 80g uyumlu",
    "stanley st010095 9 mm maket biçaği",
    "stanley sta50028 metal matkap ucu/bits giriş, siyah, 1 adet, 5 mm",
    "stanley pc537 150 kilogram profesyonel paket taşima arabasi",
])
def test_stanley_tools_kapsam_disi(baslik):
    k = kategorize_et(baslik)
    assert k["kategori"].startswith("Kapsam Dışı") and k["aksesuar"]

@pytest.mark.parametrize("baslik, kategori, seri", [
    # 15.10.2026 marka filtreli taramada kategorilenemeyen gerçek başlıklar
    ("stanley adventure easy carry kamp buzluğu 15.1 litre - siyah", "Soğutucu & Sürahi", "Adventure"),
    ("stanley julienne termos çanta 7 litre - krem", "Soğutucu & Sürahi", "Diğer"),
    ("stanley stay chill sürahi 1.9 litre - beyaz (frost)", "Soğutucu & Sürahi", "Stay Chill"),
    ("stanley adventure büyük tutuşlu bira bardaği kül 0,71l", "Kupa & Bardak", "Adventure"),
    ("stanley adventure stacking pint vakumlu soğuk içecek bardaği, pembe, 0.47 litre", "Kupa & Bardak", "Adventure"),
    ("stanley stay-hot termos bardak 0.29 litre - krem", "Kupa & Bardak", "Stay Hot"),
    ("stanley everyday suburban travel mug 16oz termos bardak 0.47 litre", "Kupa & Bardak", "Everyday"),
    ("stanley cafe to-go travel mug termos bardak, haki (dried pine), 0.35 litre", "Kupa & Bardak", "Café To-Go"),
    ("stanley the activate shaker 0.6l / 20oz / rose quartz pudra", "Su Şişesi", "Activate"),
    ("stanley iceflow twist flip şişe, 0,71 l, biber siyahi", "Su Şişesi", "IceFlow"),
    ("stanley the iceflow twist flip termos 0.47 lt | turuncu", "Su Şişesi", "IceFlow"),
    ("stanley the ice flow flp straw termos, 0.60 l, sari", "Pipetli Bardak", "IceFlow"),
    ("stanley buz akişi bottle flip straw 2.0 pipetli termos bardak 0.7l şeftali gülü, 10112830511", "Pipetli Bardak", "IceFlow"),
    ("stanley the transit fliptop termos 0.59l / renkli", "Kupa & Bardak", "Transit"),
    ("stanley pour over paslanmaz çelik kahve demleyici", "Kahve Ekipmanı", "Diğer"),
    ("stanley legendary useful box çok amaçli saklama kutusu 2 litre", "Saklama Kabı", "Classic Legendary"),
    ("stanley 10-11353-0113 termos, 0.40 l, mavi", "Yemek Termosu", "Classic Legendary"),   # ürün kodundan
    ("stanley the quencher protour flip straw tumbler 1.18l pipetli termos", "Pipetli Bardak", "Quencher"),
])
def test_yeni_gorulen_urunler(baslik, kategori, seri):
    k = kategorize_et(baslik)
    assert (k["kategori"], k["seri"]) == (kategori, seri)
    assert not k["aksesuar"]

def test_ucuncu_parti_urun():
    assert kategorize_et("yenigeldi 1 adet flip pipetli kapak – stanley quencher ile uyumlu 40 oz")["ucuncu_parti"]
    assert not kategorize_et("stanley classic legendary vakumlu çelik termos, 1 l")["ucuncu_parti"]

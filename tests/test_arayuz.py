"""Streamlit arayüzü: API sunucusu olmadan (tek süreç) ve veritabanı olmadan (bulut) çalışmalı."""
import os
import sys

import pytest
from streamlit.testing.v1 import AppTest

PROJE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJE)
import database

ARAYUZ = os.path.join(PROJE, "arayuz.py")

@pytest.fixture(autouse=True)
def bos_veritabani(tmp_path, monkeypatch):
    # Bulutta yayınlanan sürüm gibi: veritabanı yok, sadece depodaki demo verisi var
    monkeypatch.delenv("FIYAT_API_URL", raising=False)
    monkeypatch.setattr(database, "VERITABANI", str(tmp_path / "yok.db"))

def test_veritabani_yokken_demo_ile_acilir():
    at = AppTest.from_file(ARAYUZ, default_timeout=60).run()
    assert not at.exception
    assert at.sidebar.radio[0].value == "🧪 Demo"
    assert any("anlık görüntü" in i.value for i in at.info)
    assert len(at.sidebar.selectbox[0].options) > 3        # demo kataloğundaki kategoriler

def test_link_ile_analiz_dogrudan_acilir():
    at = AppTest.from_file(ARAYUZ, default_timeout=60)
    at.query_params.update({"kaynak": "demo", "kategori": "Pipetli Bardak", "seri": "Quencher",
                            "alt_seri": "H2.0 FlowState", "hacim": "1.18", "analiz": "1"})
    at.run()
    assert not at.exception and not at.error
    assert "Quencher H2.0 FlowState 1.18 L" in at.subheader[0].value
    assert any(m.label == "Model Optimum Fiyatı" for m in at.metric)

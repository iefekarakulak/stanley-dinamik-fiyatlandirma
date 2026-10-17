"""Günlük demo yayını: geçici git depolarıyla (GitHub yerine yerel bir 'uzak' depo) uçtan uca."""
import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database
import gunluk_guncelleme
from kategori import kategorize_et

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git kurulu değil")

def git(klasor, *argumanlar):
    return subprocess.run(["git", "-C", str(klasor), *argumanlar], capture_output=True, text=True, check=True).stdout

def ilan(asin, baslik, fiyat):
    return {"asin": asin, "baslik": baslik, "fiyat": fiyat, "hacim_litre": 1.18, "sayfa": 1, **kategorize_et(baslik)}

@pytest.fixture
def depo(tmp_path, monkeypatch):
    """Uzak (bare) depo + içinde demo dosyası ve ilgisiz bir dosya olan çalışma kopyası."""
    uzak, calisma = tmp_path / "uzak.git", tmp_path / "calisma"
    subprocess.run(["git", "init", "-q", "--bare", str(uzak)], check=True)
    subprocess.run(["git", "clone", "-q", str(uzak), str(calisma)], check=True, capture_output=True)
    git(calisma, "config", "user.name", "test")
    git(calisma, "config", "user.email", "test@example.com")
    (calisma / "ornek_veri").mkdir()
    (calisma / "ornek_veri" / "stanley_ornek.json").write_text('{"ilanlar": []}', encoding="utf-8")
    (calisma / "baska_dosya.py").write_text("x = 1\n", encoding="utf-8")
    git(calisma, "add", "-A")
    git(calisma, "commit", "-q", "-m", "ilk")
    git(calisma, "push", "-q", "origin", "HEAD")

    monkeypatch.setattr(database, "VERITABANI", str(tmp_path / "test.db"))
    monkeypatch.setattr(database, "ORNEK_VERI", str(calisma / "ornek_veri" / "stanley_ornek.json"))
    database.urun_gozlemlerini_kaydet("stanley", [
        ilan("A1", "stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - siyah", 2200),
        ilan("A2", "stanley quencher h2.0 flowstate pipetli termos bardak 1.18 litre - krem", 2300)])
    return uzak, calisma

def test_sadece_demo_dosyasi_commitlenip_gonderilir(depo):
    uzak, calisma = depo
    (calisma / "baska_dosya.py").write_text("x = 2  # kullanıcının yarım kalmış değişikliği\n", encoding="utf-8")

    assert gunluk_guncelleme.demo_verisini_yayinla(proje=str(calisma)) is True

    son_commit_dosyalari = git(uzak, "show", "--name-only", "--format=", "HEAD").split()
    assert son_commit_dosyalari == ["ornek_veri/stanley_ornek.json"]
    assert "Demo verisi" in git(uzak, "log", "-1", "--format=%s")
    assert "baska_dosya.py" in git(calisma, "status", "--short")     # kullanıcının değişikliğine dokunulmadı
    veri = json.loads((calisma / "ornek_veri" / "stanley_ornek.json").read_text(encoding="utf-8"))
    assert {i["asin"] for i in veri["ilanlar"]} == {"A1", "A2"}

def test_degisiklik_yoksa_commit_atilmaz(depo):
    uzak, calisma = depo
    assert gunluk_guncelleme.demo_verisini_yayinla(proje=str(calisma)) is True
    commit_sayisi = git(uzak, "rev-list", "--count", "HEAD")
    assert gunluk_guncelleme.demo_verisini_yayinla(proje=str(calisma)) is False
    assert git(uzak, "rev-list", "--count", "HEAD") == commit_sayisi

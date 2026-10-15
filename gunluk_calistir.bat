@echo off
rem Windows Görev Zamanlayıcı tarafından her gün çalıştırılır: veri toplama + model güncelleme
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist logs mkdir logs
rem -u: çıktı tamponlanmadan anında log'a yazılsın (çalışırken de takip edilebilsin)
python -u gunluk_guncelleme.py >> logs\gunluk_guncelleme.log 2>&1

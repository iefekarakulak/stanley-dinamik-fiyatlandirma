"""Amazon TR arama sonuçlarını Selenium ile tarar (veri_topla.py tarafından günde bir kez kullanılır)."""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import os
import random
import re
import time

from kategori import basliktaki_hacimler, kucuk_harf

def sayiya_cevir(metin):
    """'1.234' -> 1234, '1 B+' / '1K+' -> 1000, '4,7' için kullanılmaz"""
    eslesme = re.search(r"(\d+(?:[.,]\d+)?)\s*(b|bin|k)?\b", kucuk_harf(metin))
    if not eslesme:
        return None
    sayi, kat = eslesme.groups()
    if kat:
        return int(float(sayi.replace(",", ".")) * 1000)
    return int(sayi.replace(".", "").replace(",", ""))

def tl_cevir(metin):
    """'2.218,50 TL' -> 2218.5"""
    temiz = re.sub(r"[^\d.,]", "", metin or "").replace(".", "").replace(",", ".")
    try:
        return float(temiz)
    except ValueError:
        return None

def kart_ek_bilgileri(kart, fiyat=None):
    """Satış ve rekabet göstergeleri. Bulunamayan alan None kalır.
    - aylik_satis_rozeti/tahmini: 'Geçen ay 300 adetten fazla satın alındı' -> 300
    - yorum_sayisi, puan
    - onceki_fiyat: üstü çizili 'Önceki' fiyat (indirim oranı için)
    - stok_adedi: 'Stokta sadece 7 adet kaldı' -> 7
    - sponsorlu: reklamlı sonuç mu"""
    bilgi = {"aylik_satis_rozeti": None, "aylik_satis_tahmini": None, "yorum_sayisi": None, "puan": None,
             "onceki_fiyat": None, "stok_adedi": None, "sponsorlu": False}
    try:
        kart_metni = kart.get_attribute("innerText") or ""
        rozet = re.search(r"[^\n]*satın alındı[^\n]*", kart_metni, re.IGNORECASE)
        if rozet:
            bilgi["aylik_satis_rozeti"] = rozet.group(0).strip()
            bilgi["aylik_satis_tahmini"] = sayiya_cevir(rozet.group(0))
        stok = re.search(r"Stokta sadece (\d+) adet", kart_metni)
        if stok:
            bilgi["stok_adedi"] = int(stok.group(1))
        bilgi["sponsorlu"] = "Sponsorlu" in kart_metni
    except Exception:
        pass
    try:
        onceki = tl_cevir(kart.find_element(By.CSS_SELECTOR, "span.a-price.a-text-price span.a-offscreen")
                          .get_attribute("textContent"))
        # Birim fiyat gibi başka üstü çizili olmayan değerleri ele: önceki fiyat güncel fiyattan yüksek olmalı
        if onceki and (fiyat is None or onceki > fiyat):
            bilgi["onceki_fiyat"] = onceki
    except Exception:
        pass
    try:
        puan_metni = kart.find_element(By.CSS_SELECTOR, "span.a-icon-alt").get_attribute("textContent")
        puan = re.search(r"(\d[.,]\d)", puan_metni.split("üzerinden")[-1])
        if puan:
            bilgi["puan"] = float(puan.group(1).replace(",", "."))
    except Exception:
        pass
    try:
        # Görünen metin yuvarlanmış ("6,9 B"), aria-label kesin sayıyı verir ("6.937 derecelendirme")
        bilgi["yorum_sayisi"] = sayiya_cevir(kart.find_element(By.CSS_SELECTOR, "a[href*='customerReviews']")
                                             .get_attribute("aria-label") or "")
    except Exception:
        pass
    return bilgi

# Kalıcı tarayıcı profili (kullanıcının kendi Chrome profilinden ayrı): her gün aynı çerezlerle gelen bir ziyaretçi,
# her seferinde sıfırdan açılan çerezsiz bir tarayıcıdan çok daha doğal görünür.
PROFIL_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tarayici_profili")

def tarayici_ac():
    options = Options()
    options.add_argument(f'--user-data-dir={PROFIL_KLASORU}')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=tr-TR')
    options.add_experimental_option("prefs", {"intl.accept_languages": "tr-TR,tr"})
    # Sahte user-agent kullanılmaz: önceden "Chrome 114" yazılıyordu, oysa çalışan tarayıcı çok daha yeni bir sürümdü.
    # Bildirilen sürümle tarayıcının gerçek özelliklerinin çelişmesi, otomasyonu ele veren bir işaretti.
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # Sayfanın tüm reklam/takip kaynaklarını beklemez, HTML hazır olunca devam eder: bunlardan biri asılı kalınca
    # driver.get 120 sn'lik zaman aşımına kadar donuyordu (24.10 taramasında 3. sayfa)
    options.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver

def engel_var_mi(driver):
    # Amazon botu engellediyse ürün listesi yerine "Üzgünüz" ya da robot doğrulama sayfası gelir
    return "Üzgünüz" in driver.title or "Sorry" in driver.title or "validateCaptcha" in driver.page_source

def kart_fiyati(kart):
    """Ürün kartındaki güncel fiyatı kuruşuyla döndürür (2218.5), fiyat yoksa None.
    Üstü çizili 'Önceki' fiyat (a-text-price) güncel fiyat sayılmaz."""
    try:
        return tl_cevir(kart.find_element(By.CSS_SELECTOR, "span.a-price:not(.a-text-price) span.a-offscreen")
                        .get_attribute("textContent"))
    except Exception:
        return None

def genis_tarama(arama_terimi, sayfa_sayisi=3, sayfalar_arasi_bekleme=30, marka_filtresi=None):
    """Arama sonuçlarındaki tüm ürünleri sayfa sayfa döndürür; hacim başlıktan ayıklanır.
    Engel çıkarsa {"engellendi": True, "urunler": [...]} döner (o ana kadar toplananlar kaybolmasın diye)."""
    driver = tarayici_ac()
    urunler = []
    gorulen_urunler = set()

    try:
        # Doğrudan arama adresine atlamak yerine, normal bir ziyaretçi gibi önce ana sayfa açılır
        # (Amazon oturum çerezlerini burada verir; çerezsiz ilk istek olarak arama sayfası şüpheli görünür).
        print("Amazon ana sayfası açılıyor...")
        driver.get("https://www.amazon.com.tr/")
        if engel_var_mi(driver):
            print(f"Amazon erişimi engelledi (sayfa başlığı: {driver.title})")
            return {"engellendi": True, "urunler": urunler}
        time.sleep(random.uniform(3, 6))

        for sayfa in range(1, sayfa_sayisi + 1):
            if sayfa > 1:
                time.sleep(sayfalar_arasi_bekleme * random.uniform(0.8, 1.3))

            url = f"https://www.amazon.com.tr/s?k={arama_terimi.replace(' ', '+')}&page={sayfa}"
            if marka_filtresi:
                # Amazon'un marka filtresi: sadece bu markanın kendi ürünleri (uyumlu aksesuar satıcıları elenir)
                url += f"&rh=p_89%3A{marka_filtresi}"
            print(f"[{arama_terimi}] sayfa {sayfa} taranıyor...")
            try:
                driver.get(url)
            except TimeoutException:
                # Ürün listesi çoğu zaman yüklenmiş olur; yüklemeyi durdurup sayfadakiyle devam edilir
                print("  Sayfa 60 sn'de tam yüklenmedi, yüklenen kısımla devam ediliyor.")
                driver.execute_script("window.stop();")

            if engel_var_mi(driver):
                print(f"Amazon erişimi engelledi (sayfa başlığı: {driver.title})")
                return {"engellendi": True, "urunler": urunler}

            try:
                kartlar = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except Exception:
                print(f"  Sayfa {sayfa}'da ürün bulunamadı, arama sonuçlarının sonuna gelindi.")
                break

            sayfadaki = 0
            for kart in kartlar:
                try:
                    asin = kart.get_attribute("data-asin")
                    if not asin or asin in gorulen_urunler:
                        continue

                    fiyat = kart_fiyati(kart)
                    if fiyat is None:  # Stokta olmayan / fiyatı gösterilmeyen ürün
                        continue

                    baslik = kucuk_harf(kart.find_element(By.TAG_NAME, "h2").get_attribute("textContent")).strip()
                    hacimler = basliktaki_hacimler(baslik)

                    urunler.append({"asin": asin, "baslik": baslik, "fiyat": fiyat, "sayfa": sayfa,
                                    "hacim_litre": hacimler[0] if hacimler else None, **kart_ek_bilgileri(kart, fiyat)})
                    gorulen_urunler.add(asin)
                    sayfadaki += 1
                except Exception:
                    continue
            print(f"  {sayfadaki} ürün kaydedildi")
    except Exception as e:
        # Tarayıcı hatası taramayı bitirir ama o ana kadar toplananlar kaybolmaz (24.10'da 95 ilan kaybolmuştu)
        print(f"[HATA] Tarama yarıda kaldı ({type(e).__name__}); toplanan {len(urunler)} ilan korunuyor.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return {"engellendi": False, "urunler": urunler}

import json
import os
from datetime import datetime

import plotly.graph_objects as go
import requests
import streamlit as st

# FIYAT_API_URL tanımlıysa (örn. http://127.0.0.1:8000) hesaplamalar ayrı çalışan FastAPI servisine gönderilir.
# Tanımlı değilse aynı fonksiyonlar bu süreçte doğrudan çağrılır: tek komutla çalışır ve
# Streamlit Community Cloud gibi tek süreçli ortamlarda da yayınlanabilir.
API_ADRESI = os.environ.get("FIYAT_API_URL")
RENKLER = ["Yeşil", "Siyah", "Lacivert", "Beyaz", "Mat Siyah", "Çelik"]

st.set_page_config(page_title="Stanley Fiyat Optimizasyonu", page_icon="📈", layout="wide")
st.title("📈 Stanley Pazar Analizi ve Kâr Optimizasyonu")
st.markdown("Amazon TR'deki Stanley rekabetini analiz ederek kârı en yüksek yapan fiyatı belirler.")

def api_cagir(yol, parametreler):
    if API_ADRESI:
        istek = requests.get(f"{API_ADRESI}{yol}", params=parametreler, timeout=30)
        istek.raise_for_status()
        return istek.json()
    import api
    fonksiyon = {"/urun-secenekleri": api.urun_secenekleri, "/kayitli-fiyat": api.kayitli_fiyat_hesapla}[yol]
    return json.loads(json.dumps(fonksiyon(**parametreler)))   # HTTP yanıtıyla aynı biçim

@st.cache_data(ttl=60, show_spinner=False)
def urun_secenekleri(demo):
    return api_cagir("/urun-secenekleri", {"demo": demo})

# Paylaşılabilir link: ?kaynak=demo&kategori=Pipetli Bardak&seri=Quencher&alt_seri=ProTour&hacim=1.18&analiz=1
# seçimleri önceden doldurur, analiz=1 ise analizi butona basmadan gösterir.
LINK = st.query_params

def _link_sirasi(secenekler, anahtar, karsilastir=lambda a, b: str(a) == b):
    """Linkteki değerin seçenekler içindeki sırası; yoksa ilk seçenek."""
    if anahtar in LINK:
        for sira, secenek in enumerate(secenekler):
            if karsilastir(secenek, LINK[anahtar]):
                return sira
    return 0

def _hacim_esit(hacim, metin):
    try:
        return abs(hacim - float(metin)) < 0.005
    except ValueError:
        return False

# ---------- Kenar çubuğu: veri kaynağı ve ürün seçimi ----------

def secenekleri_getir(demo):
    try:
        return urun_secenekleri(demo)
    except requests.exceptions.RequestException:
        st.sidebar.error(f"API'ye ulaşılamadı ({API_ADRESI}). Sunucuyu başlatın: python -m uvicorn api:app")
        return {"secenekler": []}

# Kayıtlı veri yoksa (ör. bulutta yayınlanan sürüm) sadece demo verisi sunulur
kayitli_var = bool(secenekleri_getir(demo=False)["secenekler"])
KAYNAKLAR = ["📦 Kayıtlı veri", "🧪 Demo"] if kayitli_var else ["🧪 Demo"]
kaynak = st.sidebar.radio(
    "Veri kaynağı", KAYNAKLAR,
    index=KAYNAKLAR.index("🧪 Demo") if LINK.get("kaynak") == "demo" else 0,
    help="Kayıtlı veri: her sabah veri_topla.py ile Amazon TR'den toplanan son ilanlar.\n\n"
         "Demo: veritabanı olmadan denemek için depodaki gerçek bir taramanın anlık görüntüsü.")
demo = kaynak == "🧪 Demo"
if not kayitli_var:
    demo_tarihi = (secenekleri_getir(demo=True)["veri_tarihi"]["en_yeni"] or "")[:10]
    st.info(f"🧪 Bu sürüm, Amazon TR'den **{demo_tarihi}** tarihinde toplanmış gerçek Stanley ilanlarının anlık "
            "görüntüsüyle çalışıyor (her gün otomatik güncellenir). Soldan bir ürün seçip **Piyasayı Analiz Et**'e basın.")

st.sidebar.header("🔍 Ürün")
parametreler, hazir = {}, True

veri_secenek = secenekleri_getir(demo)
secenekler = veri_secenek["secenekler"]

if not secenekler:
    hazir = False
else:
    tarih = veri_secenek["veri_tarihi"]
    st.sidebar.caption(f"Veri: {tarih['en_eski'][:16]} – {tarih['en_yeni'][:16]}")
    if not demo:
        eskilik = (datetime.now() - datetime.strptime(tarih["en_yeni"][:19], "%Y-%m-%d %H:%M:%S")).days
        if eskilik >= 2:
            st.sidebar.warning(f"Son başarılı tarama {eskilik} gün önce. Günlük güncellemenin loglarını "
                               "kontrol edin (logs/gunluk_guncelleme.log).")

    kategoriler = sorted({s["kategori"] for s in secenekler})
    kategori = st.sidebar.selectbox("Kategori", kategoriler, index=_link_sirasi(kategoriler, "kategori"))
    s_kat = [s for s in secenekler if s["kategori"] == kategori]
    seriler = sorted({s["seri"] for s in s_kat})
    seri = st.sidebar.selectbox("Seri", seriler, index=_link_sirasi(seriler, "seri"))
    s_seri = [s for s in s_kat if s["seri"] == seri]

    alt_seriler = ["Tümü"] + sorted({s["alt_seri"] for s in s_seri if s["alt_seri"]})
    alt_seri = (st.sidebar.selectbox("Alt seri", alt_seriler, index=_link_sirasi(alt_seriler, "alt_seri"))
                if len(alt_seriler) > 1 else "Tümü")
    s_alt = [s for s in s_seri if alt_seri == "Tümü" or s["alt_seri"] == alt_seri]

    hacimler = {}
    for s in s_alt:
        hacimler[s["hacim"]] = hacimler.get(s["hacim"], 0) + s["ilan_sayisi"]
    hacim_listesi = sorted(hacimler)
    hacim = st.sidebar.selectbox("Hacim", hacim_listesi, index=_link_sirasi(hacim_listesi, "hacim", _hacim_esit),
                                 format_func=lambda h: f"{h} L ({hacimler[h]} ilan)")
    renk_listesi = ["Fark etmez"] + RENKLER
    renk = st.sidebar.selectbox("Renk", renk_listesi, index=_link_sirasi(renk_listesi, "renk"))

    parametreler = {"kategori": kategori, "seri": seri, "hacim": hacim, "renk": renk, "demo": demo,
                    "alt_seri": "" if alt_seri == "Tümü" else alt_seri}

st.sidebar.header("💰 Satıcı Parametreleri")
alis_maliyeti = st.sidebar.number_input("Alış maliyeti (TL)", min_value=0.0, value=1200.0, step=50.0)
komisyon = st.sidebar.number_input("Platform komisyonu (%)", min_value=0.0, max_value=99.0, value=15.0, step=0.5)
kargo = st.sidebar.number_input("Ürün başı kargo (TL)", min_value=0.0, value=60.0, step=5.0)
min_marj = st.sidebar.number_input("Minimum kâr marjı (%)", min_value=0.0, max_value=99.0, value=10.0, step=1.0)
aylik_satis = st.sidebar.number_input("Tahmini aylık satış (adet)", min_value=1, value=30, step=5,
                                      help="Buybox sende ve fiyatın piyasa medyanındayken ayda kaç adet satacağını tahmin et. "
                                           "Talep modeli, fiyat değiştikçe bu sayının nasıl değişeceğini hesaplar.")
parametreler.update({"alis_maliyeti": alis_maliyeti, "komisyon_orani": komisyon / 100,
                     "kargo": kargo, "min_marj": min_marj / 100, "aylik_satis": aylik_satis})

# ---------- Sonuç ekranı ----------

def sonucu_goster(veri):
    st.subheader(f"📊 {veri['analiz_edilen_urun']} Analiz Raporu")
    piyasa = veri['piyasa']
    tarih = f"{veri['veri_tarihi']['en_eski'][:16]} – {veri['veri_tarihi']['en_yeni'][:16]}"
    if veri.get('demo'):
        st.caption(f"🧪 Demo: Amazon TR'den {tarih} tarihli taramanın anlık görüntüsü.")
    else:
        st.caption(f"📦 Kayıtlı veri: {tarih} arasındaki Amazon TR taramaları.")
    if not piyasa.get('renk_filtresi') and parametreler.get("renk") != "Fark etmez":
        st.info(f"'{parametreler['renk']}' renginde yeterli ilan bulunamadı, piyasa değerleri tüm renklerden hesaplandı.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Adil Değer (Piyasa Medyanı)", f"{veri['adil_deger_TL']} TL")
    col2.metric("Piyasa Ortalaması", f"{piyasa['ortalama']} TL")
    col3.metric("İlan Sayısı", piyasa['satici_sayisi'])

    st.divider()

    col_fiyat1, col_fiyat2, col_fiyat3 = st.columns(3)
    col_fiyat1.metric("Piyasadaki En Ucuz", f"{piyasa['en_ucuz']} TL")
    col_fiyat2.metric("Piyasadaki En Pahalı", f"{piyasa['en_pahali']} TL")
    col_fiyat3.metric("🎯 ÖNERİLEN AKSİYON FİYATI", f"{veri['onerilen_aksiyon_fiyati_TL']} TL")

    col_kar1, col_kar2, col_kar3 = st.columns(3)
    col_kar1.metric("Taban Fiyat (Zarar Sınırı)", f"{veri['taban_fiyat_TL']} TL",
                    help="Minimum kâr marjını sağlayan en düşük fiyat. Sistem bunun altını asla önermez.")
    col_kar2.metric("Birim Net Kâr", f"{veri['birim_net_kar_TL']} TL")
    col_kar3.metric("Kâr Marjı", f"%{veri['kar_marji_yuzde']}")

    st.success(f"**STRATEJİ:** {veri['strateji']}")

    tm = veri['talep_modeli']
    st.divider()
    st.subheader("📈 Talep Modeli: Kârı En Yüksek Yapan Fiyat")
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Model Optimum Fiyatı", f"{tm['optimum_fiyat']} TL")
    col_m2.metric("Tahmini Aylık Satış", f"{tm['optimum_satis']} adet")
    col_m3.metric("Tahmini Aylık Kâr", f"{tm['optimum_aylik_kar']:,.0f} TL")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[n["fiyat"] for n in tm["egri"]], y=[n["aylik_kar"] for n in tm["egri"]],
                             mode="lines", name="Tahmini aylık kâr",
                             customdata=[n["tahmini_satis"] for n in tm["egri"]],
                             hovertemplate="Fiyat: %{x:.0f} TL<br>Aylık kâr: %{y:,.0f} TL<br>Satış: %{customdata} adet<extra></extra>"))
    for x, ad, renk_kod in [(tm["optimum_fiyat"], "Model optimumu", "green"),
                            (piyasa["medyan"], "Piyasa medyanı", "gray"),
                            (piyasa["en_ucuz"], "En ucuz rakip", "orange"),
                            (veri["taban_fiyat_TL"], "Taban fiyat", "red")]:
        fig.add_vline(x=x, line_dash="dot", line_color=renk_kod, annotation_text=ad, annotation_textangle=-90)
    fig.update_layout(xaxis_title="Satış fiyatı (TL)", yaxis_title="Tahmini aylık kâr (TL)",
                      height=420, margin=dict(t=30, b=40), showlegend=False)
    st.plotly_chart(fig, width="stretch")

    if tm["optimum_satis"] < 1:
        st.error(f"Bu maliyetlerle rekabet edemiyorsun: taban fiyatın ({veri['taban_fiyat_TL']} TL) rakip fiyatının "
                 f"({tm['buybox_referans_fiyati']} TL) üstünde, ayda 1 adet bile satış beklenmiyor. "
                 "Daha ucuz tedarik ya da daha düşük marj hedefi gerekiyor.")

    stanley_aktif = tm.get("model_kaynagi", "").startswith("Stanley")
    st.caption(f"Tahmini satış = aylık satış × talep çarpanı × Buybox payı. "
               f"Talep modeli: **{tm.get('model_kaynagi', 'UCI Online Retail II (genel)')}** "
               f"(ortalama fiyat esnekliği: {tm['model_esnekligi']})"
               + ("." if stanley_aktif else
                  "; termos pazarına özel değildir. Her gün toplanan Amazon verisi yeterli seviyeye ulaşınca "
                  "Stanley'ye özel modele geçilir.")
               + f" Buybox payı bir varsayımdır: {tm['buybox_referans_fiyati']} TL'lik rakip fiyatının "
               f"üstüne çıktıkça satış önceliği hızla kaybedilir.")

    with st.expander(f"📋 Bulunan ilanlar ({len(piyasa['ilanlar'])})"):
        st.dataframe(
            [{"Fiyat (TL)": i["fiyat"], "Ürün": i["baslik"], "Renk eşleşti": "✓" if i["renk_eslesti"] else "",
              "Aylık satış rozeti": i["aylik_satis_rozeti"] or "", "Yorum": i["yorum_sayisi"], "Puan": i["puan"],
              "Önceki fiyat": i.get("onceki_fiyat"),
              "İndirim %": round((1 - i["fiyat"] / i["onceki_fiyat"]) * 100) if i.get("onceki_fiyat") else None,
              "Stok": i.get("stok_adedi"), "Sponsorlu": "✓" if i.get("sponsorlu") else ""}
             for i in sorted(piyasa['ilanlar'], key=lambda i: i["fiyat"])],
            width="stretch", hide_index=True
        )

butona_basildi = st.sidebar.button("Piyasayı Analiz Et", disabled=not hazir)
if hazir and (butona_basildi or LINK.get("analiz") == "1"):
    with st.spinner("Hesaplanıyor..."):
        try:
            veri = api_cagir("/kayitli-fiyat", parametreler)
            if "hata" in veri:
                st.error(veri["hata"])
            else:
                sonucu_goster(veri)
        except requests.exceptions.ConnectionError:
            st.error(f"API sunucusuna ulaşılamadı ({API_ADRESI}). Sunucuyu başlatın: python -m uvicorn api:app")
        except requests.exceptions.Timeout:
            st.error("API zamanında cevap vermedi, tekrar deneyin.")
        except requests.exceptions.HTTPError as e:
            st.error(f"API hata döndürdü ({e.response.status_code}). Ayrıntı için uvicorn terminaline bakın.")
            st.code(e.response.text)
        except Exception as e:
            st.error(f"Beklenmeyen hata: {type(e).__name__}: {e}")

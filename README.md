# B2B Kitap Dağıtım Paneli

İTÜ ISL 533 Veri Madenciliği, Ödev I: Python Streamlit ile akıllı gösterge paneli.

Bir B2B kitap dağıtıcısının 2020 yılı satış verisi üzerinde satış, pazarlama ve tedarik zinciri
ekipleri için karar destek paneli.

**Canlı panel:** https://isl533-kitap.streamlit.app/
## Sayfalar

| Sayfa | İçerik |
|---|---|
| Satış | Ciro trendi, kategori mevsimselliği, haftanın günü × ay, il haritası, COVID dönemleri |
| Müşteri & Pazarlama | Pareto (ciro yoğunlaşması), RFM ısı haritası, pazar sepeti analizi (destek / güven / lift) |
| Ürün & Tedarik | ABC analizi, haftalık talep tahmini (geri testle model seçimi), kitap fiyat endeksi ve TÜFE |
| Veri Kalitesi | Temizlik günlüğü, eksik veri, geçersiz satırlar, uç satış ve dönemsel indirim |
| Kullanım Kılavuzu | Görsellerin ve metriklerin nasıl çalıştığı |

Her sayfanın kendi filtre şeridi vardır. Tutarlar kenar çubuğundan **Reel** (TÜFE ile Aralık 2020
fiyatlarına taşınmış) ya da **Nominal** gösterilebilir.

## Yerelde çalıştırma

```bash
pip install -r app/requirements.txt
streamlit run app/streamlit_app.py
```

Komutlar repo kökünden çalıştırılır (`.streamlit/config.toml` kökte okunur).

## Veri hazırlığı

`app/kod.py` ham Excel'den uygulamanın okuduğu dosyaları üretir. Adımlar dosya içinde sırayla
belgelenmiştir:

1. Excel → Parquet dönüşümü
2. Temizlik: birebir tekrarlar silinir; sorunlu satırlar silinmez, `dq_flag` / `is_valid` ile işaretlenir; eksik veri raporlanır
3. Yardımcı kolonlar: satır tutarları, indirim, TÜFE ile enflasyon düzeltmesi, uç değer bayrakları (Tukey)
4. Boyutlar: tarih, COVID dönemleri, ana kategori eşlemesi, müşteri alım düzeni
5. RFM skorları ve değer grupları

```bash
python app/kod.py
```

## Klasör yapısı

```
├── B2B_Transaction_Data_.xlsx     ham veri
├── .streamlit/config.toml
└── app/
    ├── streamlit_app.py           giriş dosyası, sayfa menüsü
    ├── requirements.txt
    ├── kod.py                     veri hazırlık adımları
    ├── core/                      veri yükleme, filtreler, analitik, grafik/tablo bileşenleri
    ├── views/                     sayfalar
    └── data/                      işlenmiş veri, raporlar, referans tablolar
```

## Kaynaklar

- TÜFE (2003=100), TÜİK: [hakedis.org](https://www.hakedis.org/endeksler/tuketici-fiyat-genel-endeksi-ve-degisim-oranlari-2003)
- Türkiye il sınırları: [cihadturhan/tr-geojson](https://github.com/cihadturhan/tr-geojson)

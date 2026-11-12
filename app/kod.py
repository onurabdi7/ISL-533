"""
ISL 533 - ÖDEV-I | B2B Kitap Dağıtıcısı - Veri Hazırlık Kodu
==============================================================
Bu dosya, veri üzerinde yapılan tüm adımların geçmişini adım adım tutar.
Her adım ayrı bir fonksiyondur; yeni adımlar dosyanın sonuna eklenir.

Çıktılar app/data/ altına yazılır ve Streamlit uygulaması bunları okur.
Ham veri (B2B_Transaction_Data_.xlsx) repo kökündedir; ilk çalıştırmada
Excel okunur (birkaç dakika sürer), sonra ara parquet dosyası kullanılır.

Çalıştırma (repo kökünden):
    python app/kod.py
"""

from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# Yollar
# --------------------------------------------------------------------------
DEV_DIR = Path(__file__).resolve().parent
ROOT_DIR = DEV_DIR.parent
DATA_DIR = DEV_DIR / "data"

RAW_XLSX = ROOT_DIR / "B2B_Transaction_Data_.xlsx"
RAW_PARQUET = DATA_DIR / "b2b_raw.parquet"
CLEAN_PARQUET = DATA_DIR / "b2b_clean.parquet"

REPORT_MISSING = DATA_DIR / "report_missing.csv"
REPORT_INVALID = DATA_DIR / "report_invalid.csv"
REPORT_CLEANING_LOG = DATA_DIR / "report_cleaning_log.csv"

ENRICHED_PARQUET = DATA_DIR / "b2b_enriched.parquet"

# Kaynak: TÜİK Tüketici Fiyat Genel Endeksi (2003=100), aylık.
# Alındığı yer: https://www.hakedis.org/endeksler/tuketici-fiyat-genel-endeksi-ve-degisim-oranlari-2003
# Kontrol: Ara.2020 / Ara.2019 = 504.81 / 440.50 -> %14.60 (TÜİK 2020 yıllık TÜFE ile aynı)
REF_TUFE = DATA_DIR / "ref_tufe_2003.csv"

# 306 alt kategori -> ana kategori eşlemesi (elle hazırlanmış referans tablo)
REF_MAIN_CATEGORY = DATA_DIR / "ref_main_category.csv"
CUSTOMERS_PARQUET = DATA_DIR / "b2b_customers.parquet"
REPORT_THRESHOLDS = DATA_DIR / "report_thresholds.csv"


# --------------------------------------------------------------------------
# ADIM 1: Excel -> Parquet dönüşümü
# --------------------------------------------------------------------------
# Amaç: Excel okuması çok yavaş (>2 dk). Ham veri, içeriği değiştirilmeden
# Parquet formatına çevrilir; sonraki tüm adımlar bu dosyadan okur.
# Not: Parquet her sütunda tek tip ister. Karışık tipli (ör. hem sayı hem
# metin içeren) 'object' sütunlar metne (string) çevrilir; değerler korunur.
def adim1_excel_to_parquet(force: bool = False) -> pd.DataFrame:
    if RAW_PARQUET.exists() and not force:
        print(f"[ADIM 1] Parquet zaten var, atlanıyor: {RAW_PARQUET}")
        return pd.read_parquet(RAW_PARQUET)

    print(f"[ADIM 1] Excel okunuyor (uzun sürebilir): {RAW_XLSX}")
    df = pd.read_excel(RAW_XLSX, sheet_name="Transaction")

    for col in df.columns:
        if df[col].dtype == object:
            types = df[col].dropna().map(type).value_counts()
            if len(types) > 1:
                detay = {t.__name__: int(n) for t, n in types.items()}
                print(f"  - '{col}' karışık tipli {detay} -> string")
                df[col] = df[col].astype("string")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RAW_PARQUET, index=False)

    size_mb = RAW_PARQUET.stat().st_size / 1024**2
    print(f"[ADIM 1] Yazıldı: {RAW_PARQUET} ({size_mb:.1f} MB) | şekil: {df.shape}")
    return df


# --------------------------------------------------------------------------
# ADIM 2: Temizlik ve bayraklama
# --------------------------------------------------------------------------
# Usul: "bayrakla, raporla, analizden dışla". Tek fiziksel silme işlemi
# birebir tekrarlı satırlardır. Diğer sorunlu satırlar silinmez:
#   - dq_flag  : satırı GEÇERSİZ yapan kural kodları (';' ile ayrılır)
#   - is_valid : dq_flag boşsa True -> analizlere yalnızca bu satırlar girer
#   - dq_note  : bilgi amaçlı notlar; satır geçerli kalır
# Eksik City/Category doldurulamaz (her müşterinin tek şehri, her ürünün
# tek kategorisi var; boş olanların başka satırda değeri yok) -> etiketlenir.
# Ciro etkisi = Quantity * NetPrice (NetPrice birim net fiyat varsayımı;
# Adım 3'te doğrulanacak).

UNITPRICE_PLACEHOLDER_MAX = 0.01   # altındaki birim fiyatlar yer tutucu kabul edilir
LABEL_UNKNOWN_CITY = "Bilinmiyor"
LABEL_UNKNOWN_CATEGORY = "Kategorisiz"

# Geçersizlik kuralları: kod -> (açıklama, koşul fonksiyonu)
INVALID_RULES = {
    "QTY_MISSING": ("Miktar boş (değer fiyat sütununa kaymış görünüyor)",
                    lambda d: d["Quantity"].isna()),
    "QTY_ZERO": ("Miktar sıfır (iade benzeri satır)",
                 lambda d: d["Quantity"] == 0),
    "NETPRICE_NONPOSITIVE": ("Net fiyat sıfır veya negatif",
                             lambda d: d["NetPrice"] <= 0),
    "NETPRICE_GT_UNITPRICE": ("Net fiyat liste fiyatından yüksek (negatif indirim)",
                              lambda d: d["NetPrice"] > d["UnitPrice"]),
    "UNITPRICE_PLACEHOLDER": (f"Liste fiyatı yer tutucu (< {UNITPRICE_PLACEHOLDER_MAX})",
                              lambda d: d["UnitPrice"] < UNITPRICE_PLACEHOLDER_MAX),
}

# Excel'in ürün adını tarih/saat/ondalık sayıya çevirdiği değerler
# (tam sayılar meşru kitap adı olabilir: "1984", "13" -> bayraklanmaz)
EXCEL_CONVERTED_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$|^\d{2}:\d{2}:\d{2}$|^-?\d+\.\d+$"


def _join_flags(masks: dict[str, pd.Series], index: pd.Index) -> pd.Series:
    """Kural maskelerini satır bazında 'KOD1;KOD2' metnine çevirir."""
    out = pd.Series("", index=index, dtype="string")
    for code, mask in masks.items():
        mask = mask.fillna(False)
        out = out.mask(mask, out.where(out == "", out + ";") + code)
    return out


def adim2_temizlik(df: pd.DataFrame) -> pd.DataFrame:
    log = []  # (adım, kural, açıklama, satır, ciro etkisi)

    def ciro(d):
        return float((d["Quantity"].fillna(0) * d["NetPrice"]).sum())

    n0 = len(df)
    log.append(("Başlangıç", "-", "Ham veri", n0, ciro(df)))

    # 2.1 Metin alanlarında baş/son boşluk temizliği ve tip dönüşümleri
    df = df.copy()
    for col in ["InvoiceNo", "CustomerID", "Description", "Category", "City"]:
        df[col] = df[col].astype("string").str.strip()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], format="%Y-%m-%d")
    df["StockCode"] = df["StockCode"].astype("string")

    # 2.2 Birebir tekrarlı satırların silinmesi
    # Varsayım: satır numarası olmadığından, aynı faturada aynı ürün/miktar/fiyat
    # ile tekrar eden satırlar mükerrer kayıt kabul edilir.
    dup = df.duplicated(keep="first")
    log.append(("2.2 Silme", "DUPLICATE", "Birebir tekrarlı satır (ilki tutuldu)",
                int(dup.sum()), ciro(df[dup])))
    df = df[~dup].reset_index(drop=True)

    # 2.3 Eksik veri raporu (etiketlemeden ÖNCE, tekilleştirilmiş veri üzerinde)
    actions = {
        "City": f"'{LABEL_UNKNOWN_CITY}' etiketi (başka satırdan doldurulamıyor)",
        "Category": f"'{LABEL_UNKNOWN_CATEGORY}' etiketi (başka satırdan doldurulamıyor)",
        "Quantity": "Geçersiz bayrağı (QTY_MISSING)",
    }
    rows = []
    for col in df.columns:
        m = df[col].isna()
        if m.any():
            rows.append({
                "Sütun": col,
                "Eksik Satır": int(m.sum()),
                "Oran (%)": round(m.mean() * 100, 3),
                "Etkilenen Müşteri": df.loc[m, "CustomerID"].nunique(),
                "Etkilenen Ürün": df.loc[m, "StockCode"].nunique(),
                "Ciro Etkisi": round(ciro(df[m]), 2),
                "Aksiyon": actions.get(col, "-"),
            })
    missing_report = pd.DataFrame(rows)

    # 2.4 Eksik kategorik değerlerin etiketlenmesi
    df["City"] = df["City"].fillna(LABEL_UNKNOWN_CITY)
    df["Category"] = df["Category"].fillna(LABEL_UNKNOWN_CATEGORY)

    # 2.5 Geçersizlik bayrakları
    masks = {code: rule(df) for code, (_, rule) in INVALID_RULES.items()}
    df["dq_flag"] = _join_flags(masks, df.index)
    df["is_valid"] = df["dq_flag"] == ""
    for code, (desc, _) in INVALID_RULES.items():
        m = masks[code].fillna(False)
        log.append(("2.5 Bayrak", code, desc, int(m.sum()), ciro(df[m])))

    # 2.6 Bilgi notları (satır geçerli kalır)
    series = df["InvoiceNo"].str[:3]
    inv_per_series = df.groupby(series)["InvoiceNo"].transform("nunique")
    notes = {
        "DESC_EXCEL_CONVERTED": (
            "Ürün adı Excel tarafından tarih/saat/ondalığa çevrilmiş",
            df["Description"].str.match(EXCEL_CONVERTED_PATTERN, na=False)),
        "DOC_SERIES_SINGLETON": (
            "Belge serisinde tek fatura var (olağandışı belge)",
            inv_per_series == 1),
    }
    df["dq_note"] = _join_flags({k: v[1] for k, v in notes.items()}, df.index)
    for code, (desc, m) in notes.items():
        log.append(("2.6 Not", code, desc, int(m.sum()), ciro(df[m])))

    valid = df["is_valid"]
    log.append(("Sonuç", "-", "Analize giren geçerli satır", int(valid.sum()), ciro(df[valid])))

    # Raporlar ve çıktı
    cleaning_log = pd.DataFrame(log, columns=["Adım", "Kural", "Açıklama", "Satır", "Ciro Etkisi"])
    cleaning_log["Ciro Etkisi"] = cleaning_log["Ciro Etkisi"].round(2)
    invalid_report = df.loc[~valid].drop(columns=["is_valid"])

    missing_report.to_csv(REPORT_MISSING, index=False, encoding="utf-8-sig")
    invalid_report.to_csv(REPORT_INVALID, index=False, encoding="utf-8-sig")
    cleaning_log.to_csv(REPORT_CLEANING_LOG, index=False, encoding="utf-8-sig")
    df.to_parquet(CLEAN_PARQUET, index=False)

    print("[ADIM 2] Temizlik günlüğü:")
    print(cleaning_log.to_string(index=False))
    print("\n[ADIM 2] Eksik veri raporu:")
    print(missing_report.to_string(index=False))
    print(f"\n[ADIM 2] Geçersiz satır: {len(invalid_report)} | Yazıldı: {CLEAN_PARQUET} | şekil: {df.shape}")
    return df


# --------------------------------------------------------------------------
# ADIM 3: Helper kolonlar (satır bazlı ölçüler ve uç değer bayrakları)
# --------------------------------------------------------------------------
# Doğrulama: NetPrice birim net fiyattır. NetPrice/UnitPrice oranı miktar
# 1'den 5000'e kadar ~0.60'ta sabit kalıyor; satır toplamı olsaydı miktarla
# büyürdü. Dolayısıyla satır tutarı = Quantity * NetPrice.
#
# DiscountRate satır bazlıdır. Toplu indirim oranı ağırlıklı hesaplanmalıdır:
# sum(DiscountAmt) / sum(LineGross) -- satır oranlarının ortalaması alınmaz.
#
# Uç değer eşikleri yalnızca geçerli satırlardan hesaplanır; geçersiz
# satırlarda bayraklar False / boş kalır.

OUTLIER_IQR_K = 3.0  # Tukey "aşırı uç" katsayısı

# Enflasyon düzeltmesi: tutarlar baz ayın fiyatlarına taşınır.
#   Adjusted = Nominal * TÜFE(baz) / TÜFE(işlem ayı)
# Baz = Aralık 2020 -> tüm yıl "yıl sonu TL"si ile ifade edilir. Aylar arası
# büyüme karşılaştırmaları baz seçiminden bağımsızdır; yalnızca seviye değişir.
CPI_BASE_YEAR, CPI_BASE_MONTH = 2020, 12


def _log_iqr_upper(s: pd.Series, k: float) -> float:
    """Sağa çarpık seriler için log1p ölçeğinde Tukey üst sınırı."""
    import numpy as np
    l = np.log1p(s)
    q1, q3 = l.quantile([0.25, 0.75])
    return float(np.expm1(q3 + k * (q3 - q1)))


def adim3_helper_kolonlar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    valid = df["is_valid"]

    # 3.1 Satır ölçüleri
    df["LineGross"] = df["Quantity"] * df["UnitPrice"]          # liste fiyatıyla tutar
    df["LineNet"] = df["Quantity"] * df["NetPrice"]             # gerçekleşen ciro
    df["DiscountAmt"] = df["LineGross"] - df["LineNet"]         # verilen indirim tutarı
    df["DiscountRate"] = 1 - df["NetPrice"] / df["UnitPrice"]   # satır indirim oranı

    # 3.2 Enflasyon düzeltmesi (TÜFE 2003=100, baz: Aralık 2020)
    cpi = pd.read_csv(REF_TUFE)
    base = cpi.loc[(cpi["Yil"] == CPI_BASE_YEAR) & (cpi["Ay"] == CPI_BASE_MONTH), "TUFE_2003"].item()
    cpi["CPI_Factor"] = base / cpi["TUFE_2003"]
    key = df["InvoiceDate"].dt.year * 100 + df["InvoiceDate"].dt.month
    factor = key.map(cpi.set_index(cpi["Yil"] * 100 + cpi["Ay"])["CPI_Factor"])
    if factor.isna().any():
        raise ValueError(f"TÜFE tablosunda olmayan ay(lar): {sorted(key[factor.isna()].unique())}")
    df["CPI_Factor"] = factor
    df["Sales_Adjusted"] = df["LineNet"] * df["CPI_Factor"]          # reel ciro
    df["Gross_Adjusted"] = df["LineGross"] * df["CPI_Factor"]        # reel brüt tutar
    df["UnitPrice_Adjusted"] = df["UnitPrice"] * df["CPI_Factor"]    # reel liste fiyatı
    df["NetPrice_Adjusted"] = df["NetPrice"] * df["CPI_Factor"]      # reel net fiyat

    # 3.3 Fatura düzeyi bağlam (sepet büyüklüğü) - yalnızca geçerli satırlar
    inv = df[valid].groupby("InvoiceNo")
    df.loc[valid, "InvoiceLines"] = inv["StockCode"].transform("size")
    df.loc[valid, "InvoiceNet"] = inv["LineNet"].transform("sum")
    df.loc[valid, "InvoiceNet_Adjusted"] = inv["Sales_Adjusted"].transform("sum")

    # 3.4 Belge serisi (boyut değil; yalnızca uç satış sekmesinde açıklama için)
    df["DocSeries"] = df["InvoiceNo"].str[:3]

    # 3.5 Uç satış bayrağı: Sales_Adjusted (reel), log ölçeğinde Tukey üst sınırı.
    # Nominal tutar kullanılsaydı yıl sonu satırları yalnızca fiyat artışı
    # nedeniyle daha sık uç çıkardı.
    line_thr = _log_iqr_upper(df.loc[valid, "Sales_Adjusted"], OUTLIER_IQR_K)
    df["is_outlier"] = valid & (df["Sales_Adjusted"] > line_thr)

    # 3.6 Uç indirim bandı: DiscountRate, iki yönlü Tukey sınırları
    # (oran olduğu için enflasyondan etkilenmez)
    d = df.loc[valid, "DiscountRate"]
    q1, q3 = d.quantile([0.25, 0.75])
    disc_lo = float(q1 - OUTLIER_IQR_K * (q3 - q1))
    disc_hi = float(q3 + OUTLIER_IQR_K * (q3 - q1))
    df["DiscountBand"] = pd.Series(pd.NA, index=df.index, dtype="string")
    df.loc[valid, "DiscountBand"] = "Normal"
    df.loc[valid & (df["DiscountRate"] < disc_lo), "DiscountBand"] = "Düşük İndirim"
    df.loc[valid & (df["DiscountRate"] > disc_hi), "DiscountBand"] = "Yüksek İndirim"

    # Eşik raporu
    v = df[valid]
    total = v["LineNet"].sum()
    out = v["is_outlier"]
    thresholds = pd.DataFrame([
        {"Ölçü": "Sales_Adjusted (uç satış, Ara.2020 TL)", "Yöntem": f"log1p Tukey, k={OUTLIER_IQR_K}",
         "Alt Sınır": None, "Üst Sınır": round(line_thr, 2),
         "Satır": int(out.sum()), "Satır (%)": round(out.mean() * 100, 2),
         "Ciro Payı (%)": round(v.loc[out, "LineNet"].sum() / total * 100, 2)},
        *[{"Ölçü": f"DiscountRate ({band})", "Yöntem": f"Tukey, k={OUTLIER_IQR_K}",
           "Alt Sınır": round(disc_lo, 4), "Üst Sınır": round(disc_hi, 4),
           "Satır": int(m.sum()), "Satır (%)": round(m.mean() * 100, 2),
           "Ciro Payı (%)": round(v.loc[m, "LineNet"].sum() / total * 100, 2)}
          for band in ["Düşük İndirim", "Yüksek İndirim"]
          for m in [v["DiscountBand"] == band]],
    ])
    thresholds.to_csv(REPORT_THRESHOLDS, index=False, encoding="utf-8-sig")
    df.to_parquet(ENRICHED_PARQUET, index=False)

    w_disc = v["DiscountAmt"].sum() / v["LineGross"].sum()
    print("\n[ADIM 3] Eşikler:")
    print(thresholds.to_string(index=False))
    print(f"\n[ADIM 3] Toplam net ciro: {total:,.2f} | brüt: {v['LineGross'].sum():,.2f} "
          f"| ağırlıklı indirim: %{w_disc * 100:.2f}")
    print(f"[ADIM 3] Reel net ciro (Ara.2020 TL): {v['Sales_Adjusted'].sum():,.2f} "
          f"| fark: %{(v['Sales_Adjusted'].sum() / total - 1) * 100:.2f}")
    monthly = v.groupby(v["InvoiceDate"].dt.month).agg(
        Nominal=("LineNet", "sum"), Reel=("Sales_Adjusted", "sum"), Faktor=("CPI_Factor", "first"))
    monthly["Nominal Değ.%"] = (monthly["Nominal"].pct_change() * 100).round(1)
    monthly["Reel Değ.%"] = (monthly["Reel"].pct_change() * 100).round(1)
    print("\n[ADIM 3] Aylık nominal vs reel ciro:")
    print(monthly.round({"Nominal": 0, "Reel": 0, "Faktor": 4}).to_string())
    print(f"[ADIM 3] Yazıldı: {ENRICHED_PARQUET} | şekil: {df.shape}")
    return df


# --------------------------------------------------------------------------
# ADIM 4: Helper boyutlar (tarih, ana kategori, müşteri alım eğrisi)
# --------------------------------------------------------------------------
# 4.1 Tarih boyutları + COVID dönemi
#     Kapanma: ilk vaka (11.03.2020) -> normalleşmenin ilk adımı (01.06.2020)
# 4.2 MainCategory: ref_main_category.csv ile 306 -> 16 grup.
#     Eşlenmemiş kategori kalırsa hata verir (sessizce 'Diğer'e düşmez).
# 4.3 Müşteri alım eğrisi (yalnızca geçerli satırlar, ayrı müşteri tablosu):
#     PurchasePattern - alım günleri arası sürelerin değişkenlik katsayısı (CV):
#       1 alım günü            -> Tek Seferlik
#       2-3 alım günü          -> Seyrek
#       >=4 gün ve CV <= 1     -> Düzenli   (rastgele/Poisson geliş CV=1'den daha düzenli)
#       >=4 gün ve CV >  1     -> Dönemsel  (alımlar belirli dönemlerde kümeleniyor)
#     Bu gruplama yalnızca gözlenen dönemi TANIMLAR; ileriye dönük nitelik değildir.
#
# Kapsam kararı: Veri tek yılı (2020) kapsadığından müşteri bazında trend
# (büyüyen/düşen) ve churn (riskli/kayıp) NİTELEMESİ YAPILMAZ. Kısa dönemde
# mevsimsellik ve COVID etkisi bu etiketleri yanıltıcı kılar.

COVID_START, COVID_END = pd.Timestamp("2020-03-11"), pd.Timestamp("2020-06-01")
MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
             "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
WEEKDAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

PATTERN_MIN_DAYS = 4          # CV'nin anlamlı olması için en az 3 aralık
PATTERN_CV_THRESHOLD = 1.0


def _musteri_alim_egrisi(v: pd.DataFrame) -> pd.DataFrame:
    import numpy as np

    g = v.groupby("CustomerID")
    cust = g.agg(
        City=("City", "first"),
        FirstPurchase=("InvoiceDate", "min"),
        LastPurchase=("InvoiceDate", "max"),
        Invoices=("InvoiceNo", "nunique"),
        PurchaseDays=("InvoiceDate", "nunique"),
        ActiveMonths=("Month", "nunique"),
        Products=("StockCode", "nunique"),
        Quantity=("Quantity", "sum"),
        Sales=("LineNet", "sum"),
        Sales_Adjusted=("Sales_Adjusted", "sum"),
        DiscountAmt=("DiscountAmt", "sum"),
        Gross=("LineGross", "sum"),
    )
    cust["DiscountRate"] = cust["DiscountAmt"] / cust["Gross"]

    # Alım günleri arası süreler
    days = v[["CustomerID", "InvoiceDate"]].drop_duplicates().sort_values(["CustomerID", "InvoiceDate"])
    days["Gap"] = days.groupby("CustomerID")["InvoiceDate"].diff().dt.days
    gaps = days.groupby("CustomerID")["Gap"].agg(["mean", "std"])
    cust["AvgInterval"] = gaps["mean"]
    cust["IntervalCV"] = gaps["std"] / gaps["mean"]

    n = cust["PurchaseDays"]
    cust["PurchasePattern"] = np.select(
        [n == 1, n < PATTERN_MIN_DAYS, cust["IntervalCV"] <= PATTERN_CV_THRESHOLD],
        ["Tek Seferlik", "Seyrek", "Düzenli"], default="Dönemsel")
    return cust.reset_index()


def adim4_helper_boyutlar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    d = df["InvoiceDate"]

    # 4.1 Tarih boyutları
    df["Month"] = d.dt.month
    df["MonthName"] = d.dt.month.map(dict(enumerate(MONTHS_TR, start=1)))
    df["YearMonth"] = d.dt.strftime("%Y-%m")
    df["Quarter"] = "Q" + d.dt.quarter.astype(str)
    df["Week"] = d.dt.isocalendar().week.astype(int)
    df["WeekdayNo"] = d.dt.dayofweek
    df["WeekdayName"] = d.dt.dayofweek.map(dict(enumerate(WEEKDAYS_TR)))
    df["is_weekend"] = d.dt.dayofweek >= 5
    df["CovidPhase"] = pd.cut(
        d, bins=[pd.Timestamp.min, COVID_START, COVID_END, pd.Timestamp.max],
        labels=["COVID Öncesi", "Kapanma", "Normalleşme"], right=False).astype("string")

    # 4.2 Ana kategori
    ref = pd.read_csv(REF_MAIN_CATEGORY)
    if ref["Category"].duplicated().any():
        raise ValueError(f"Eşlemede tekrarlı kategori: {ref.loc[ref['Category'].duplicated(), 'Category'].tolist()}")
    df["MainCategory"] = df["Category"].map(ref.set_index("Category")["MainCategory"]).astype("string")
    unmapped = sorted(df.loc[df["MainCategory"].isna(), "Category"].unique())
    if unmapped:
        raise ValueError(f"Eşlenmemiş kategori(ler): {unmapped}")
    unused = sorted(set(ref["Category"]) - set(df["Category"]))
    if unused:
        print(f"[ADIM 4] Uyarı - veride olmayan eşleme satırları: {unused}")

    # 4.3 Müşteri alım eğrisi
    v = df[df["is_valid"]]
    cust = _musteri_alim_egrisi(v)

    df.to_parquet(ENRICHED_PARQUET, index=False)
    cust.to_parquet(CUSTOMERS_PARQUET, index=False)

    # Özet çıktılar
    total = v["Sales_Adjusted"].sum()
    mc = v.groupby("MainCategory").agg(Kategori=("Category", "nunique"), Urun=("StockCode", "nunique"),
                                       Reel_Ciro=("Sales_Adjusted", "sum"))
    mc["Pay%"] = (mc["Reel_Ciro"] / total * 100).round(1)
    print("\n[ADIM 4] Ana kategoriler:")
    print(mc.sort_values("Reel_Ciro", ascending=False).round({"Reel_Ciro": 0}).to_string())

    ph = v.groupby("CovidPhase").agg(Gun=("InvoiceDate", "nunique"), Reel_Ciro=("Sales_Adjusted", "sum"))
    ph["Günlük Ort."] = (ph["Reel_Ciro"] / ph["Gun"]).round(0)
    print("\n[ADIM 4] COVID dönemleri (satış olan günler):")
    print(ph.reindex(["COVID Öncesi", "Kapanma", "Normalleşme"]).round({"Reel_Ciro": 0}).to_string())

    ct = cust.groupby("PurchasePattern").agg(Musteri=("CustomerID", "size"),
                                             Reel_Ciro=("Sales_Adjusted", "sum"),
                                             Ort_Aralik_Gun=("AvgInterval", "median"))
    ct["Ciro Pay%"] = (ct["Reel_Ciro"] / cust["Sales_Adjusted"].sum() * 100).round(1)
    print("\n[ADIM 4] Müşteri alım düzeni:")
    print(ct.round({"Reel_Ciro": 0, "Ort_Aralik_Gun": 1}).to_string())
    print("IntervalCV dağılımı (>=4 gün):",
          cust.loc[cust["PurchaseDays"] >= PATTERN_MIN_DAYS, "IntervalCV"].quantile([.1, .25, .5, .75, .9]).round(2).to_dict())
    print(f"\n[ADIM 4] Yazıldı: {ENRICHED_PARQUET} {df.shape} | {CUSTOMERS_PARQUET} {cust.shape}")
    return df, cust


# --------------------------------------------------------------------------
# ADIM 5: RFM skorlama ve değer grupları (müşteri tablosu)
# --------------------------------------------------------------------------
# Ham ölçüler (yorum içermez):
#   Recency   = referans tarih - son alım tarihi (gün); referans = son işlem günü + 1
#   Frequency = fatura sayısı
#   Monetary  = reel ciro (Sales_Adjusted, Ara.2020 TL)
# Skorlar: müşteriler her ölçüde dönem içi sıralamaya göre 5 eşit gruba
#   bölünür (1 = en düşük, 5 = en yüksek). Recency ters çevrilir (yakın = 5).
#   Eşit değerler sıra numarasıyla ayrıştırılır (rank 'first'), böylece her
#   grup ~%20 müşteri içerir.
# Değer grubu: F + M skor toplamına (2-10) göre nötr gruplama.
#   Kapsam kararı gereği churn/risk çağrıştıran segment adları (At Risk, Lost,
#   Hibernating vb.) KULLANILMAZ; Recency etiketsiz metrik olarak raporlanır.

RFM_BINS = 5
VALUE_GROUPS = [  # (alt sınır dahil F+M toplamı, etiket) - büyükten küçüğe
    (8, "Yüksek Değer"),
    (5, "Orta Değer"),
    (2, "Düşük Değer"),
]


def _quintile_score(s: pd.Series, reverse: bool = False) -> pd.Series:
    r = s.rank(method="first", ascending=not reverse)
    return pd.qcut(r, RFM_BINS, labels=range(1, RFM_BINS + 1)).astype(int)


def adim5_rfm(cust: pd.DataFrame) -> pd.DataFrame:
    import numpy as np

    cust = cust.copy()
    ref_date = cust["LastPurchase"].max() + pd.Timedelta(days=1)

    cust["Recency"] = (ref_date - cust["LastPurchase"]).dt.days
    cust["Frequency"] = cust["Invoices"]
    cust["Monetary"] = cust["Sales_Adjusted"]

    cust["R_Score"] = _quintile_score(cust["Recency"], reverse=True)
    cust["F_Score"] = _quintile_score(cust["Frequency"])
    cust["M_Score"] = _quintile_score(cust["Monetary"])
    cust["RFM_Code"] = (cust["R_Score"].astype(str) + cust["F_Score"].astype(str)
                        + cust["M_Score"].astype(str))
    cust["FM_Score"] = cust["F_Score"] + cust["M_Score"]

    fm = cust["FM_Score"]
    cust["ValueGroup"] = np.select([fm >= lo for lo, _ in VALUE_GROUPS],
                                   [lbl for _, lbl in VALUE_GROUPS], default="Düşük Değer")

    cust.to_parquet(CUSTOMERS_PARQUET, index=False)

    # Özet
    total = cust["Monetary"].sum()
    vg = cust.groupby("ValueGroup").agg(
        Musteri=("CustomerID", "size"), Reel_Ciro=("Monetary", "sum"),
        Ort_Recency=("Recency", "median"), Ort_Frequency=("Frequency", "median"),
        Ort_Monetary=("Monetary", "median"))
    vg["Musteri%"] = (vg["Musteri"] / len(cust) * 100).round(1)
    vg["Ciro Pay%"] = (vg["Reel_Ciro"] / total * 100).round(1)
    vg = vg.reindex([lbl for _, lbl in VALUE_GROUPS])

    print(f"\n[ADIM 5] Referans tarih: {ref_date.date()}")
    print("[ADIM 5] Skor sınırları (her skorun min-max ham değeri):")
    for m, s in [("Recency", "R_Score"), ("Frequency", "F_Score"), ("Monetary", "M_Score")]:
        b = cust.groupby(s)[m].agg(["min", "max"]).round(0).astype(int)
        print(f"  {m}: " + " | ".join(f"{k}: {r['min']}-{r['max']}" for k, r in b.iterrows()))
    print("\n[ADIM 5] Değer grupları:")
    print(vg.round({"Reel_Ciro": 0, "Ort_Monetary": 0}).to_string())
    print("\n[ADIM 5] Değer grubu x alım düzeni (müşteri sayısı):")
    print(pd.crosstab(cust["ValueGroup"], cust["PurchasePattern"]).reindex(vg.index).to_string())
    print(f"\n[ADIM 5] Yazıldı: {CUSTOMERS_PARQUET} {cust.shape}")
    return cust


# --------------------------------------------------------------------------
# Çalıştırma
# --------------------------------------------------------------------------
if __name__ == "__main__":
    df = adim1_excel_to_parquet()
    df = adim2_temizlik(df)
    df = adim3_helper_kolonlar(df)
    df, customers = adim4_helper_boyutlar(df)
    customers = adim5_rfm(customers)

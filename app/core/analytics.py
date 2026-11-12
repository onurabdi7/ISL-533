"""Analitik hesaplar: RFM, birliktelik kuralları, ABC, talep tahmini, fiyat endeksi.

Hepsi filtrelenmiş veri üzerinde çalışır; böylece sayfa filtreleri analizlere
de yansır.
"""

import math
import warnings

import numpy as np
import pandas as pd
import streamlit as st


# --------------------------------------------------------------------------
# RFM
# --------------------------------------------------------------------------
def _score(s: pd.Series, reverse: bool = False) -> pd.Series:
    """Dönem içi sıralamaya göre 1-5 skor (eşitlikler sıra numarasıyla ayrışır)."""
    r = s.rank(method="first", ascending=not reverse, pct=True)
    return np.ceil(r * 5).clip(1, 5).astype(int)


def rfm(df: pd.DataFrame, amt: str, ref_date: pd.Timestamp) -> pd.DataFrame:
    c = df.groupby("CustomerID").agg(Last=("InvoiceDate", "max"), Frequency=("InvoiceNo", "nunique"),
                                     Monetary=(amt, "sum"))
    c["Recency"] = (ref_date - c["Last"]).dt.days
    c["R"] = _score(c["Recency"], reverse=True)
    c["F"] = _score(c["Frequency"])
    c["M"] = _score(c["Monetary"])
    return c.reset_index()


# --------------------------------------------------------------------------
# Birliktelik kuralları (pazar sepeti)
# --------------------------------------------------------------------------
def association(df: pd.DataFrame, level: str, top_n: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aynı faturada birlikte geçen kategori çiftleri.

    destek(A,B) = A ve B'yi içeren fatura / tüm fatura
    güven(A→B)  = destek(A,B) / destek(A)
    lift(A,B)   = destek(A,B) / (destek(A) * destek(B))   (>1: beklenenden sık birlikte)
    Döner: (lift matrisi, kural tablosu)
    """
    basket = df[["InvoiceNo", level]].drop_duplicates()
    if top_n:
        keep = basket[level].value_counts().head(top_n).index
        basket = basket[basket[level].isin(keep)]
    x = pd.crosstab(basket["InvoiceNo"], basket[level].astype(str)).clip(upper=1)
    n = df["InvoiceNo"].nunique()
    co = x.T.dot(x)
    support = np.diag(co) / n
    cats = co.index.tolist()
    arr = (co.to_numpy(dtype=float) / n) / np.outer(support, support)
    np.fill_diagonal(arr, np.nan)
    lift = pd.DataFrame(arr, index=co.index, columns=co.columns)

    rows = []
    for i in range(len(cats)):
        for j in range(i + 1, len(cats)):
            both = co.iat[i, j]
            if both == 0:
                continue
            rows.append({"Kategori A": cats[i], "Kategori B": cats[j], "Birlikte fatura": both,
                         "Destek (%)": both / n * 100,
                         "Güven A→B (%)": both / co.iat[i, i] * 100,
                         "Güven B→A (%)": both / co.iat[j, j] * 100,
                         "Lift": lift.iat[i, j]})
    rules = pd.DataFrame(rows).sort_values("Lift", ascending=False) if rows else pd.DataFrame()
    order = pd.Series(support, index=cats).sort_values(ascending=False).index
    return lift.loc[order, order], rules


# --------------------------------------------------------------------------
# ABC
# --------------------------------------------------------------------------
ABC_LIMITS = (80, 95)   # A: cironun ilk %80'i, B: sonraki %15, C: kalan %5


def abc(df: pd.DataFrame, amt: str) -> pd.DataFrame:
    p = df.groupby("StockCode").agg(Description=("Description", "first"), Category=("Category", "first"),
                                    MainCategory=("MainCategory", "first"), Quantity=("Quantity", "sum"),
                                    Sales=(amt, "sum")).sort_values("Sales", ascending=False)
    p["CumShare"] = p["Sales"].cumsum() / p["Sales"].sum() * 100
    prev = p["CumShare"].shift(fill_value=0)   # sınıf, ürünün başladığı noktaya göre
    p["Class"] = np.where(prev < ABC_LIMITS[0], "A", np.where(prev < ABC_LIMITS[1], "B", "C"))
    p["Rank"] = np.arange(1, len(p) + 1)
    return p.reset_index()


# --------------------------------------------------------------------------
# Talep tahmini
# --------------------------------------------------------------------------
def _ets(y: np.ndarray, h: int, trend: bool) -> np.ndarray:
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = ETSModel(pd.Series(y), error="add", trend="add" if trend else None,
                       damped_trend=trend).fit(disp=False)
        return res.forecast(h).to_numpy()


FORECAST_MODELS = {
    "Naif (son hafta)": lambda y, h: np.repeat(y[-1], h),
    "Hareketli ortalama (4 hafta)": lambda y, h: np.repeat(y[-4:].mean(), h),
    "Basit üstel düzeltme (ETS A,N,N)": lambda y, h: _ets(y, h, trend=False),
    "Sönümlü trend (ETS A,Ad,N)": lambda y, h: _ets(y, h, trend=True),
}


@st.cache_data(show_spinner="Tahmin modelleri karşılaştırılıyor…")
def forecast_weekly(values: tuple, h: int, holdout: int = 8, z: float = 1.2816) -> dict:
    """Aday modeller arasından geri testle seçilen haftalık tahmin.

    Doğrulama: son `holdout` hafta dışarıda bırakılır, her aday kalan veriyle
    kurulup bu haftaları tahmin eder; ortalama mutlak yüzde hata (MAPE) en
    düşük olan model tüm veriyle yeniden kurulup ileriye tahmin yapar.
    Tek yıllık veride mevsimsellik öğrenilemez; adaylarda mevsimsel bileşen yoktur.

    Tahmin aralığı (yaklaşık %80): seçilen modelin geri test hatalarının
    standart sapması, ufuk büyüdükçe √k ile genişletilir.
    """
    y = np.asarray(values, dtype=float)
    train, actual = y[:-holdout], y[-holdout:]
    ok = actual > 0
    scores, backtests = {}, {}
    for name, f in FORECAST_MODELS.items():
        bt = f(train, holdout)
        backtests[name] = bt
        scores[name] = float(np.mean(np.abs(actual[ok] - bt[ok]) / actual[ok]) * 100)
    best = min(scores, key=scores.get)

    mean = FORECAST_MODELS[best](y, h)
    sigma = float(np.std(actual - backtests[best], ddof=1))
    k = np.sqrt(np.arange(1, h + 1))
    lo = np.maximum(mean - z * sigma * k, 0)
    hi = mean + z * sigma * k
    return dict(model=best, mean=mean.tolist(), lo=lo.tolist(), hi=hi.tolist(), holdout=holdout,
                scores=scores, backtest=backtests[best].tolist())


# --------------------------------------------------------------------------
# Fiyat endeksi
# --------------------------------------------------------------------------
def price_index(df: pd.DataFrame, cpi: pd.DataFrame) -> pd.DataFrame:
    """Sabit tabanlı kitap fiyat endeksi ve TÜFE (ilk ay = 100).

    Her ay için hem taban ayında hem o ayda satılan ürünlerin medyan liste
    fiyatı oranlarının geometrik ortalaması (Jevons). Fiyat endeksi nominal
    liste fiyatıyla hesaplanır (TÜFE ile karşılaştırılabilir olsun diye).
    """
    m = df.groupby(["StockCode", df["InvoiceDate"].dt.to_period("M")])["UnitPrice"].median().unstack()
    base = m.columns[0]
    rows = []
    c = cpi.assign(P=pd.PeriodIndex.from_fields(year=cpi["Yil"], month=cpi["Ay"], freq="M")).set_index("P")["TUFE_2003"]
    for p in m.columns:
        ok = m[base].notna() & m[p].notna()
        rel = np.log(m.loc[ok, p] / m.loc[ok, base])
        rows.append({"Period": p, "Kitap": math.exp(rel.mean()) * 100 if ok.any() else np.nan,
                     "TÜFE": c[p] / c[base] * 100, "Ürün": int(ok.sum())})
    return pd.DataFrame(rows)

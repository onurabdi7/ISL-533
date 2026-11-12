"""Veri yükleme (önbellekli) ve tutar birimi seçimi.

Veriler kod.py ile üretilmiş parquet/CSV dosyalarından okunur. Uygulama
yalnızca geçerli satırları (is_valid) kullanır; geçersiz satırlar Veri
Kalitesi sayfasındaki raporlarda gösterilir.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TX_COLUMNS = [
    "InvoiceNo", "CustomerID", "InvoiceDate", "StockCode", "Description", "Category", "MainCategory", "City",
    "Quantity", "UnitPrice", "NetPrice",
    "LineGross", "LineNet", "DiscountAmt", "DiscountRate",
    "CPI_Factor", "Sales_Adjusted", "Gross_Adjusted",
    "is_outlier", "DiscountBand", "DocSeries",
    "Month", "YearMonth", "WeekdayNo", "CovidPhase",
]
CATEGORICAL = ["Category", "MainCategory", "City", "DiscountBand", "DocSeries", "CovidPhase", "YearMonth"]

UNIT_KEY = "unit"
UNIT_REAL = "Reel"
UNIT_NOMINAL = "Nominal"


@st.cache_data(show_spinner="Satış verisi yükleniyor…")
def load_transactions() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "b2b_enriched.parquet", columns=TX_COLUMNS + ["is_valid"],
                         filters=[("is_valid", "==", True)]).drop(columns="is_valid")
    for col in CATEGORICAL:
        df[col] = df[col].astype("category")

    # Müşteri boyutları (değer grubu, alım düzeni) satırlara taşınır -> filtrelenebilir
    cust = load_customers()[["CustomerID", "ValueGroup", "PurchasePattern"]]
    df = df.merge(cust, on="CustomerID", how="left")
    df["ValueGroup"] = df["ValueGroup"].astype("category")
    df["PurchasePattern"] = df["PurchasePattern"].astype("category")
    return df


@st.cache_data(show_spinner=False)
def load_customers() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "b2b_customers.parquet")


@st.cache_data(show_spinner=False)
def load_report(name: str) -> pd.DataFrame:
    """name: 'missing' | 'invalid' | 'cleaning_log' | 'thresholds'"""
    return pd.read_csv(DATA_DIR / f"report_{name}.csv")


@st.cache_data(show_spinner=False)
def load_cpi() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "ref_tufe_2003.csv")


def is_real() -> bool:
    return st.session_state.get(UNIT_KEY, UNIT_REAL) == UNIT_REAL


def amount_col() -> str:
    """Seçili birime göre net ciro sütunu."""
    return "Sales_Adjusted" if is_real() else "LineNet"


def gross_col() -> str:
    """Seçili birime göre brüt (liste fiyatı) tutar sütunu."""
    return "Gross_Adjusted" if is_real() else "LineGross"


def unit_label() -> str:
    return "reel" if is_real() else "nominal"

"""Zaman serisi yardımcıları: aralığa göre günlük/haftalık seri ve tam ay karşılaştırması."""

from datetime import date

import pandas as pd

DAILY_MAX_DAYS = 60   # bu sürenin altındaki aralıklar günlük, üstündekiler haftalık çizilir


def granularity(start: date, end: date) -> str:
    return "D" if (end - start).days + 1 < DAILY_MAX_DAYS else "W"


def time_series(df: pd.DataFrame, cols: list[str], start: date, end: date) -> tuple[pd.DataFrame, str]:
    """Seçili aralık için günlük ya da haftalık toplamlar.

    Günlük: satış olmayan günler 0 ile doldurulur.
    Haftalık: Pazartesi başlangıçlı haftalar; aralığın kenarında kalan eksik
    haftalar çizilmez (yarım hafta düşüş gibi görünürdü).
    """
    freq = granularity(start, end)
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if freq == "D":
        out = df.groupby("InvoiceDate")[cols].sum().reindex(pd.date_range(s, e), fill_value=0)
        return out, freq

    week = df["InvoiceDate"].dt.to_period("W-SUN").dt.start_time
    out = df.groupby(week)[cols].sum()
    weeks = pd.date_range(s - pd.Timedelta(days=s.dayofweek), e, freq="W-MON")
    out = out.reindex(weeks, fill_value=0)
    full = (out.index >= s) & (out.index + pd.Timedelta(days=6) <= e)
    return out[full], freq


def full_months(start: date, end: date) -> list[pd.Period]:
    """Aralığın tamamen kapsadığı takvim ayları."""
    return [p for p in pd.period_range(start, end, freq="M")
            if p.start_time.date() >= start and p.end_time.date() <= end]


def first_last_month_change(df: pd.DataFrame, col: str, start: date, end: date) -> tuple[float, str] | None:
    """İlk ve son TAM ay arasındaki % değişim. En az iki tam ay yoksa None."""
    months = full_months(start, end)
    if len(months) < 2:
        return None
    m = df.groupby(df["InvoiceDate"].dt.to_period("M"))[col].sum()
    a, b = m.get(months[0], 0), m.get(months[-1], 0)
    if a == 0:
        return None
    from core.style import MONTHS_TR
    return (b / a - 1) * 100, f"{MONTHS_TR[months[0].month - 1]}→{MONTHS_TR[months[-1].month - 1]}"

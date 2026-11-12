"""Tablo biçimlendirme: binlik ayraçlı Türkçe sayılar ve artış/azalış renkleri.

st.dataframe pandas Styler'ı destekler; görünen değer biçimlenir, sıralama
alttaki sayısal değere göre yapılır.
"""

import pandas as pd
from pandas.io.formats.style import Styler

from core.style import num

GREEN, RED = "#1a9e47", "#d64545"


def _na(f):
    return lambda v: "–" if pd.isna(v) else f(v)


def _sign_color(v, invert: bool = False) -> str:
    if pd.isna(v) or v == 0:
        return ""
    good = (v > 0) != invert
    return f"color: {GREEN if good else RED}; font-weight: 600"


def _index_color(v) -> str:
    """Endeks (100 = ortalama) için: üstü yeşil, altı kırmızı."""
    if pd.isna(v) or v == 100:
        return ""
    return f"color: {GREEN if v > 100 else RED}"


def styled(df: pd.DataFrame, *, money=(), integer=(), dec1=(), dec2=(), pct=(), change=(),
           change_inv=(), change_pp=(), index_cols=()) -> Styler:
    """Sütun gruplarına göre biçim ve renk uygular.

    money      : 1.234 ₺            integer : 1.234          dec1/dec2 : 1.234,5 / 1,23
    pct        : %12,3 (değer zaten yüzde)
    change     : +%12,3 yeşil / −%4,5 kırmızı
    change_inv : işaret renkleri ters (ör. indirim artışı kırmızı)
    change_pp  : yüzde puan farkı, +1,2 pp (ters renk: artış kırmızı)
    index_cols : 100 tabanlı endeks; 100 üstü yeşil, altı kırmızı
    """
    fmt = {}
    for c in money:
        fmt[c] = _na(lambda v: f"{num(v)} ₺")
    for c in integer:
        fmt[c] = _na(lambda v: num(v))
    for c in dec1:
        fmt[c] = _na(lambda v: num(v, 1))
    for c in dec2:
        fmt[c] = _na(lambda v: num(v, 2))
    for c in pct:
        fmt[c] = _na(lambda v: "%" + num(v, 1))
    for c in (*change, *change_inv):
        fmt[c] = _na(lambda v: ("+" if v > 0 else "−" if v < 0 else "") + "%" + num(abs(v), 1))
    for c in change_pp:
        fmt[c] = _na(lambda v: ("+" if v > 0 else "−" if v < 0 else "") + num(abs(v), 1) + " pp")
    for c in index_cols:
        fmt[c] = _na(lambda v: num(v))

    s = df.style.format(fmt)
    if change:
        s = s.map(_sign_color, subset=list(change))
    if change_inv or change_pp:
        s = s.map(lambda v: _sign_color(v, invert=True), subset=[*change_inv, *change_pp])
    if index_cols:
        s = s.map(_index_color, subset=list(index_cols))
    return s

"""Türkçe sayı biçimleri, renk paleti, sayfa başlığı/KPI bileşenleri ve Plotly ortak düzeni."""

from html import escape

import plotly.graph_objects as go
import streamlit as st

# Kategorik palet (sabit sıra; renk körlüğü testinden geçmiş referans palet)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE, ORANGE, AQUA, YELLOW = SERIES[:4]
MUTED = "#898781"

# Sıralı (tek ton, açıktan koyuya) ve ıraksak (kırmızı - gri - mavi) skalalar
SEQUENTIAL = [[0.0, "#eef4fc"], [0.2, "#cde2fb"], [0.4, "#9ec5f4"], [0.6, "#5598e7"], [0.8, "#256abf"], [1.0, "#0d366b"]]
DIVERGING = [[0.0, "#d03b3b"], [0.5, "#f0efec"], [1.0, "#2a78d6"]]

MONEY_AXIS = dict(tickformat=",.0f", ticksuffix=" ₺")   # binlik ayraçlı para ekseni

MONTHS_TR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
WEEKDAYS_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def num(x: float, d: int = 0) -> str:
    """1234567.8 -> '1.234.567,8'"""
    s = f"{x:,.{d}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(x: float, d: int = 1, sign: bool = False) -> str:
    """x yüzde cinsinden: 12.3 -> '%12,3' (sign=True -> '+%12,3')"""
    p = "%" + num(abs(x), d)
    if sign:
        return ("+" if x >= 0 else "−") + p
    return ("−" if x < 0 else "") + p


def money(x: float) -> str:
    """Kısa para gösterimi: 29417403 -> '29,42 M ₺', 159400 -> '159,4 bin ₺'"""
    a = abs(x)
    if a >= 1e6:
        return f"{num(x / 1e6, 2)} M ₺"
    if a >= 1e3:
        return f"{num(x / 1e3, 1)} bin ₺"
    return f"{num(x, 0)} ₺"


def layout(fig: go.Figure, height: int = 360, legend: bool = False, **kw) -> go.Figure:
    """Tüm grafiklerde ortak düzen. Tema renkleri Streamlit temasından gelir."""
    base = dict(
        height=height,
        separators=",.",
        margin=dict(l=8, r=8, t=36 if legend else 12, b=8),
        font=dict(size=12),
        showlegend=legend,
        legend=dict(orientation="h", x=0, y=1.12, title=None),
        hoverlabel=dict(font_size=12),
    )
    base.update(kw)   # sayfa bazlı ayarlar varsayılanları ezer
    fig.update_layout(**base)
    fig.update_xaxes(automargin=True, zeroline=False)
    fig.update_yaxes(automargin=True, zeroline=False)
    return fig


PLOTLY_CONFIG = {"displayModeBar": False, "locale": "tr"}


# --------------------------------------------------------------------------
# Sayfa düzeni bileşenleri
# --------------------------------------------------------------------------
# Renkler temadan bağımsız: metin rengi miras alınır, çizgiler yarı saydam gri.
_CSS = """
<style>
[data-testid="stMainBlockContainer"], .block-container { padding-top: 2.25rem; padding-bottom: 2rem; }
.pg-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: .25rem .75rem; margin: 0 0 .25rem; }
.pg-head h1 { font-size: 1.25rem; font-weight: 650; margin: 0; padding: 0; line-height: 1.3; }
.pg-head span { font-size: .85rem; opacity: .65; }
.kpi-card { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  border: 1px solid rgba(128,128,128,.28); border-radius: .5rem; overflow: hidden; margin: .25rem 0 1rem; }
.kpi-card .kpi { padding: .7rem 1rem .8rem; display: flex; flex-direction: column; gap: .15rem; min-width: 0;
  box-shadow: -1px 0 0 rgba(128,128,128,.22), 0 -1px 0 rgba(128,128,128,.22); }
.kpi .k { font-size: .8rem; opacity: .7; line-height: 1.3; overflow-wrap: anywhere; }
.kpi .k small { font-size: .72rem; opacity: .85; margin-left: .25rem; padding: 0 .3rem;
  border: 1px solid rgba(128,128,128,.35); border-radius: .25rem; }
.kpi .v { font-size: clamp(1.2rem, 1.9vw, 1.65rem); font-weight: 650; line-height: 1.2; white-space: nowrap; }
.kpi .d { font-size: .78rem; line-height: 1.35; overflow-wrap: anywhere; }
.kpi .d.up { color: #1a9e47; } .kpi .d.down { color: #d64545; }
.kpi .n { font-size: .74rem; opacity: .6; line-height: 1.35; overflow-wrap: anywhere; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    """Küçük, tek satırlık sayfa başlığı (raporlama alanını üstte bırakır)."""
    sub = f"<span>{escape(subtitle)}</span>" if subtitle else ""
    st.markdown(f'<div class="pg-head"><h1>{escape(title)}</h1>{sub}</div>', unsafe_allow_html=True)


def kpi_card(items: list[dict]) -> None:
    """Tek kart içinde çok sütunlu KPI şeridi.

    items: {label, value, tag?, delta?, delta_note?, note?}
      delta: yüzde değişim (float) -> yeşil/kırmızı ok ile gösterilir
    """
    cells = []
    for it in items:
        tag = f"<small>{escape(it['tag'])}</small>" if it.get("tag") else ""
        parts = [f'<div class="k">{escape(it["label"])}{tag}</div>', f'<div class="v">{escape(it["value"])}</div>']
        if it.get("delta") is not None:
            d = it["delta"]
            cls, arrow = ("up", "▲") if d >= 0 else ("down", "▼")
            note = f" {escape(it.get('delta_note', ''))}" if it.get("delta_note") else ""
            parts.append(f'<div class="d {cls}">{arrow} {escape(pct(d))}{note}</div>')
        if it.get("note"):
            parts.append(f'<div class="n">{escape(it["note"])}</div>')
        cells.append(f'<div class="kpi">{"".join(parts)}</div>')
    st.markdown(f'<div class="kpi-card">{"".join(cells)}</div>', unsafe_allow_html=True)

"""Sayfa blokları: başlıklı çerçeve, grafik/tablo sekmeleri."""

from contextlib import contextmanager

import plotly.graph_objects as go
import streamlit as st

from core.style import PLOTLY_CONFIG


@contextmanager
def block(title: str):
    """Başlıklı, çerçeveli bölüm. İlgili alt görseller aynı blokta toplanır."""
    with st.container(border=True):
        st.markdown(f"**{title}**")
        yield


def chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def table(data, height: int | None = None) -> None:
    kw = {"height": height} if height else {}
    st.dataframe(data, width="stretch", hide_index=True, **kw)


def chart_or_table(fig: go.Figure, data, height: int | None = None, labels=("Grafik", "Tablo")) -> None:
    """Aynı verinin grafik ve tablo görünümü (sekmeli)."""
    t1, t2 = st.tabs([f":material/bar_chart: {labels[0]}", f":material/table: {labels[1]}"])
    with t1:
        chart(fig)
    with t2:
        table(data, height)

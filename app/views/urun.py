"""4 · Ürün & Tedarik — D1 ABC analizi, D2 haftalık talep tahmini, D3 kitap fiyat endeksi ve TÜFE."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.analytics import ABC_LIMITS, abc, forecast_weekly, price_index
from core.blocks import block, chart_or_table, table
from core.data import amount_col, load_cpi, load_transactions, unit_label
from core.filters import filter_bar, selected_dates
from core.style import BLUE, MONEY_AXIS, MONTHS_TR, ORANGE, kpi_card, layout, num, page_header, pct
from core.tables import styled
from core.trend import time_series

PAGE = "urun"
page_header("Ürün & Tedarik")

df = filter_bar(load_transactions(), page=PAGE, fields=["date", "main_category"])
start, end = selected_dates(PAGE)
amt = amount_col()

p = abc(df, amt)
cls = p.groupby("Class").agg(Ürün=("StockCode", "size"), Ciro=("Sales", "sum"), Adet=("Quantity", "sum"))
cls = cls.reindex(["A", "B", "C"]).fillna(0)
weekly = time_series(df, [amt, "Quantity"], start, end)[0] if (end - start).days >= 60 else None
pi = price_index(df, load_cpi())

kpi_card([
    dict(label="Ürün çeşidi", value=num(len(p)), note=f"{num(df['Category'].nunique())} alt kategori"),
    dict(label="A sınıfı ürün", value=num(cls.loc["A", "Ürün"]),
         note=f"Ürünlerin {pct(cls.loc['A', 'Ürün'] / len(p) * 100)}'i cironun %{ABC_LIMITS[0]}'i"),
    dict(label="Satılan adet", value=num(df["Quantity"].sum()),
         note=f"Haftalık ort. {num(weekly['Quantity'].mean())}" if weekly is not None and len(weekly) else None),
    dict(label="Kitap fiyat değişimi", value=pct(pi["Kitap"].iloc[-1] - 100, sign=True),
         note=f"TÜFE {pct(pi['TÜFE'].iloc[-1] - 100, sign=True)} · {pi['Period'].iloc[0].strftime('%m.%Y')}→"
              f"{pi['Period'].iloc[-1].strftime('%m.%Y')}"),
])

# ---------------------------------------------------------------- D1 · ABC
with block("ABC analizi: ürünlerin ciroya katkısı"):
    x = p["Rank"] / len(p) * 100
    fig = go.Figure(go.Scatter(x=x, y=p["CumShare"], mode="lines", line=dict(color=BLUE, width=2),
                               customdata=p["Rank"],
                               hovertemplate="İlk %{customdata:,} ürün (%{x:.2f}%) → cironun %{y:.1f}%'i<extra></extra>"))
    for lim in ABC_LIMITS:
        fig.add_hline(y=lim, line=dict(color="rgba(128,128,128,.6)", dash="dot", width=1))
    for label, y in [("A", ABC_LIMITS[0] / 2), ("B", sum(ABC_LIMITS) / 2), ("C", (ABC_LIMITS[1] + 100) / 2)]:
        fig.add_annotation(xref="paper", x=0.01, y=y, text=f"<b>{label}</b>", showarrow=False)
    layout(fig, height=320, xaxis=dict(type="log", title="Ürün payı (%, log ölçek)",
                                       tickvals=[0.01, 0.1, 1, 10, 100], ticktext=["0,01", "0,1", "1", "10", "100"]),
           yaxis=dict(title="Kümülatif ciro (%)", range=[0, 102], ticksuffix="%"))

    t = cls.reset_index().rename(columns={"Class": "Sınıf"})
    t["Ürün payı (%)"] = t["Ürün"] / len(p) * 100
    t["Ciro payı (%)"] = t["Ciro"] / t["Ciro"].sum() * 100
    t = t[["Sınıf", "Ürün", "Ürün payı (%)", "Ciro", "Ciro payı (%)", "Adet"]]
    chart_or_table(fig, styled(t, integer=["Ürün", "Adet"], money=["Ciro"], pct=["Ürün payı (%)", "Ciro payı (%)"]))

    with st.expander("En çok ciro yapan 50 ürün"):
        top = p.head(50)[["Rank", "Description", "Category", "Class", "Quantity", "Sales", "CumShare"]]
        top = top.rename(columns={"Rank": "Sıra", "Description": "Ürün", "Category": "Alt kategori", "Class": "Sınıf",
                                  "Quantity": "Adet", "Sales": "Ciro", "CumShare": "Kümülatif pay (%)"})
        table(styled(top, integer=["Sıra", "Adet"], money=["Ciro"], pct=["Kümülatif pay (%)"]), height=420)
    st.caption(f"A: cironun ilk %{ABC_LIMITS[0]}'ini yapan ürünler (stok önceliği), B: sonraki "
               f"%{ABC_LIMITS[1] - ABC_LIMITS[0]}, C: kalan %{100 - ABC_LIMITS[1]} (uzun kuyruk). Seçili kategori ve "
               f"tarih aralığına göre yeniden hesaplanır.")

# ---------------------------------------------------------------- D2 · Talep tahmini
with block(f"Haftalık talep tahmini ({unit_label()} ciro)"):
    y = weekly[amt] if weekly is not None else pd.Series(dtype=float)
    if len(y) < 20:
        st.info("Tahmin için en az 20 tam haftalık bir aralık seçin.", icon=":material/timeline:")
    else:
        h = st.slider("Tahmin ufku (hafta)", 4, 12, 8, key="fc_horizon")
        fc = forecast_weekly(tuple(y.round(2)), h)
        fdates = pd.date_range(y.index[-1] + pd.Timedelta(days=7), periods=h, freq="7D")
        lastx, lasty = y.index[-1], y.iloc[-1]

        fig = go.Figure([
            go.Scatter(x=[lastx, *fdates, *fdates[::-1], lastx], y=[lasty, *fc["hi"], *fc["lo"][::-1], lasty],
                       fill="toself", fillcolor="rgba(42,120,214,0.15)", line=dict(width=0), hoverinfo="skip",
                       name="~%80 tahmin aralığı"),
            go.Scatter(x=y.index[-fc["holdout"]:], y=fc["backtest"], mode="lines",
                       line=dict(color=ORANGE, width=1.5, dash="dot"), name="Geri test",
                       hovertemplate="%{x|%d.%m.%Y} haftası<br>Geri test tahmini %{y:,.0f} ₺<extra></extra>"),
            go.Scatter(x=y.index, y=y.values, mode="lines+markers", line=dict(color=BLUE, width=2), marker=dict(size=5),
                       name="Gerçekleşen", hovertemplate="%{x|%d.%m.%Y} haftası<br>%{y:,.0f} ₺<extra></extra>"),
            go.Scatter(x=[lastx, *fdates], y=[lasty, *fc["mean"]], mode="lines+markers",
                       line=dict(color=BLUE, width=2, dash="dash"), marker=dict(size=5), name="Tahmin",
                       hovertemplate="%{x|%d.%m.%Y} haftası<br>Tahmin %{y:,.0f} ₺<extra></extra>"),
        ])
        fig.add_vline(x=lastx, line=dict(color="rgba(128,128,128,.6)", dash="dot", width=1))
        layout(fig, height=340, legend=True, yaxis=dict(**MONEY_AXIS, rangemode="tozero"),
               xaxis=dict(tickformat="%d.%m", showgrid=False))

        hist = pd.DataFrame({"Hafta başı": y.index, "Tür": "Gerçekleşen", "Ciro": y.values,
                             "Alt sınır": np.nan, "Üst sınır": np.nan})
        fut = pd.DataFrame({"Hafta başı": fdates, "Tür": "Tahmin", "Ciro": fc["mean"],
                            "Alt sınır": fc["lo"], "Üst sınır": fc["hi"]})
        t = pd.concat([hist, fut], ignore_index=True)
        t["Önceki haftaya göre"] = t["Ciro"].pct_change() * 100
        t["Hafta başı"] = t["Hafta başı"].dt.strftime("%d.%m.%Y")
        t = t.iloc[::-1]   # en yeni üstte
        chart_or_table(fig, styled(t, money=["Ciro", "Alt sınır", "Üst sınır"], change=["Önceki haftaya göre"]),
                       height=420)

        if fc["scores"][fc["model"]] > 30:
            st.warning(f"Geri test hatası yüksek (MAPE %{num(fc['scores'][fc['model']], 1)}): bu seçim için haftalık "
                       "talep çok oynak, tahmin yalnızca kaba bir seviye göstergesi olarak okunmalı.",
                       icon=":material/warning:")
        with st.expander("Model karşılaştırması (geri test)"):
            sc = pd.DataFrame({"Model": list(fc["scores"]), "MAPE (%)": list(fc["scores"].values())})
            sc["Seçildi"] = np.where(sc["Model"] == fc["model"], "✔", "")
            table(styled(sc.sort_values("MAPE (%)"), dec1=["MAPE (%)"]))
        st.caption(
            f"Seçilen model: **{fc['model']}** (son {fc['holdout']} haftalık geri testte MAPE "
            f"%{num(fc['scores'][fc['model']], 1)}, adaylar arasında en düşük). Dört aday aynı haftaları tahmin eder, "
            "en az hata yapan tüm veriyle yeniden kurulur. Turuncu noktalı çizgi geri test tahminidir. "
            "Tek yıllık veride mevsimsellik öğrenilemez; tahmin yakın vadeli seviyeyi yansıtır.")

# ---------------------------------------------------------------- D3 · Fiyat endeksi
with block("Kitap fiyat endeksi ve TÜFE"):
    if len(pi) < 2:
        st.info("Fiyat endeksi için en az iki aylık bir aralık seçin.", icon=":material/price_change:")
    else:
        mlab = [MONTHS_TR[pp.month - 1] for pp in pi["Period"]]
        fig = go.Figure([
            go.Scatter(x=mlab, y=pi["TÜFE"], name="TÜFE", mode="lines+markers", line=dict(color=ORANGE, width=2),
                       marker=dict(size=7), hovertemplate="%{x}: %{y:.1f}<extra>TÜFE</extra>"),
            go.Scatter(x=mlab, y=pi["Kitap"], name="Kitap fiyat endeksi", mode="lines+markers",
                       line=dict(color=BLUE, width=2), marker=dict(size=7),
                       hovertemplate="%{x}: %{y:.1f}<extra>Kitap</extra>"),
        ])
        layout(fig, height=320, legend=True, yaxis=dict(title=f"{mlab[0]} = 100"), xaxis=dict(showgrid=False))

        t = pd.DataFrame({"Ay": [pp.strftime("%m.%Y") for pp in pi["Period"]], "Kitap endeksi": pi["Kitap"],
                          "TÜFE": pi["TÜFE"], "Fark (puan)": pi["Kitap"] - pi["TÜFE"],
                          "Kitap aylık değişim": pi["Kitap"].pct_change() * 100,
                          "TÜFE aylık değişim": pi["TÜFE"].pct_change() * 100, "Eşleşen ürün": pi["Ürün"]})
        chart_or_table(fig, styled(t, dec1=["Kitap endeksi", "TÜFE", "Fark (puan)"], integer=["Eşleşen ürün"],
                                   change=["Kitap aylık değişim", "TÜFE aylık değişim"]))
        gap = pi["Kitap"].iloc[-1] - pi["TÜFE"].iloc[-1]
        st.caption(f"Her ay, hem taban ayda hem o ayda satılan aynı ürünlerin liste fiyatı oranlarının geometrik "
                   f"ortalaması (nominal fiyat). Dönem sonunda kitap fiyatları TÜFE'nin "
                   f"{num(abs(gap), 1)} puan {'altında' if gap < 0 else 'üstünde'}: ürünler reel olarak "
                   f"{'ucuzladı' if gap < 0 else 'pahalandı'}.")

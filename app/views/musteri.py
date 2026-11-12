"""3 · Müşteri & Pazarlama — C1 Pareto, C2 RFM ısı haritası, C7 birliktelik kuralları.

RFM skorları seçili filtreye göre yeniden hesaplanır (referans: seçili bitiş
tarihinin ertesi günü). Kapsam kararı gereği müşterilere churn/trend etiketi
verilmez; değer grubu ve alım düzeni yıllık veriden gelen tanımlayıcı alanlardır.
"""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.analytics import association, rfm
from core.blocks import block, chart_or_table, table
from core.data import amount_col, load_transactions, unit_label
from core.filters import filter_bar, selected_dates
from core.style import BLUE, DIVERGING, SEQUENTIAL, kpi_card, layout, money, num, page_header, pct
from core.tables import styled

PAGE = "musteri"
page_header("Müşteri & Pazarlama")

df = filter_bar(load_transactions(), page=PAGE, fields=["date", "city", "value_group", "pattern"])
start, end = selected_dates(PAGE)
amt = amount_col()
ref = pd.Timestamp(end) + pd.Timedelta(days=1)
r = rfm(df, amt, ref)
n = len(r)

# ---------------------------------------------------------------- Pareto verisi
mon = r["Monetary"].sort_values(ascending=False).to_numpy()
cum = np.cumsum(mon) / mon.sum() * 100
top20 = cum[max(math.ceil(n * 0.2) - 1, 0)]

kpi_card([
    dict(label="Aktif müşteri", value=num(n), note=f"{num(df['City'].nunique())} şehir"),
    dict(label="Müşteri başı ciro", tag=unit_label(), value=money(mon.sum() / n),
         note=f"Ortanca {money(np.median(mon))}"),
    dict(label="Müşteri başı fatura", value=num(r["Frequency"].mean(), 1),
         note=f"Ortanca {num(r['Frequency'].median())}"),
    dict(label="En iyi %20 müşterinin payı", value=pct(top20), note="Ciro yoğunlaşması"),
    dict(label="Son alımdan bu yana", value=f"{num(r['Recency'].median())} gün",
         note=f"Ortanca · referans {end:%d.%m.%Y}"),
])

# ---------------------------------------------------------------- C1 · Pareto
with block("Müşteri yoğunlaşması (Pareto)"):
    x = np.arange(1, n + 1) / n * 100
    fig = go.Figure([
        go.Scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color="rgba(128,128,128,.6)", dash="dash", width=1),
                   hoverinfo="skip", name="Eşit dağılım"),
        go.Scatter(x=x, y=cum, mode="lines", line=dict(color=BLUE, width=2), fill="tonexty",
                   fillcolor="rgba(42,120,214,0.10)", name="Kümülatif ciro",
                   hovertemplate="En iyi %{x:.1f}% müşteri → cironun %{y:.1f}%'i<extra></extra>"),
        go.Scatter(x=[20], y=[top20], mode="markers+text", marker=dict(size=9, color=BLUE),
                   text=[f"%20 → {pct(top20, 0)}"], textposition="middle right", hoverinfo="skip"),
    ])
    layout(fig, height=320, xaxis=dict(title="Müşteri payı (%)", range=[0, 100], ticksuffix="%"),
           yaxis=dict(title="Kümülatif ciro (%)", range=[0, 102], ticksuffix="%"))

    rows = []
    for k in range(1, 11):
        hi = math.ceil(n * k / 10)
        lo = math.ceil(n * (k - 1) / 10)
        rows.append({"Müşteri dilimi": f"%{(k - 1) * 10}–%{k * 10}", "Müşteri": hi - lo,
                     "Dilim cirosu": mon[lo:hi].sum(), "Dilim payı (%)": mon[lo:hi].sum() / mon.sum() * 100,
                     "Kümülatif pay (%)": cum[hi - 1]})
    t = pd.DataFrame(rows)
    chart_or_table(fig, styled(t, integer=["Müşteri"], money=["Dilim cirosu"],
                               pct=["Dilim payı (%)", "Kümülatif pay (%)"]))
    st.caption("Müşteriler seçili dönemdeki cirolarına göre büyükten küçüğe sıralanır. "
               "Eğri kesikli çizgiden ne kadar uzaksa ciro o kadar az müşteride toplanmıştır.")

# ---------------------------------------------------------------- C2 · RFM
with block("RFM: yakınlık × sıklık"):
    piv_rev = r.pivot_table(index="R", columns="F", values="Monetary", aggfunc="sum", fill_value=0)
    piv_cnt = r.pivot_table(index="R", columns="F", values="CustomerID", aggfunc="count", fill_value=0)
    piv_rev = piv_rev.reindex(index=range(5, 0, -1), columns=range(1, 6), fill_value=0)
    piv_cnt = piv_cnt.reindex(index=range(5, 0, -1), columns=range(1, 6), fill_value=0)
    share = piv_rev / piv_rev.values.sum() * 100

    fig = go.Figure(go.Heatmap(
        z=share.values, x=[f"F{f}" for f in share.columns], y=[f"R{v}" for v in share.index],
        text=piv_cnt.values, texttemplate="%{text}", colorscale=SEQUENTIAL, xgap=3, ygap=3,
        colorbar=dict(thickness=10, len=0.9, outlinewidth=0, ticksuffix="%", title=dict(text="Ciro payı", side="top")),
        hovertemplate="%{y} · %{x}<br>%{text} müşteri<br>Cironun %{z:.1f}%'i<extra></extra>"))
    layout(fig, height=340, xaxis=dict(title="Sıklık skoru (F) →", showgrid=False, side="top"),
           yaxis=dict(title="Yakınlık skoru (R)", showgrid=False))

    cells = r.groupby(["R", "F"]).agg(Müşteri=("CustomerID", "size"), Ciro=("Monetary", "sum"),
                                      Ort_Recency=("Recency", "median"), Ort_Frequency=("Frequency", "median"))
    cells["Ciro payı (%)"] = cells["Ciro"] / cells["Ciro"].sum() * 100
    cells = cells.reset_index().sort_values(["R", "F"], ascending=False).rename(
        columns={"Ort_Recency": "Ortanca gün", "Ort_Frequency": "Ortanca fatura"})
    chart_or_table(fig, styled(cells, integer=["R", "F", "Müşteri", "Ortanca gün", "Ortanca fatura"],
                               money=["Ciro"], pct=["Ciro payı (%)"]), height=420)

    bounds = []
    for s in range(5, 0, -1):
        row = {"Skor": s}
        for col, score in [("Recency", "R"), ("Frequency", "F"), ("Monetary", "M")]:
            v = r.loc[r[score] == s, col]
            row[col] = f"{num(v.min())} – {num(v.max())}" if len(v) else "–"
        bounds.append(row)
    with st.expander("Skor sınırları"):
        table(pd.DataFrame(bounds).rename(columns={"Recency": "Son alımdan gün", "Frequency": "Fatura sayısı",
                                                 "Monetary": f"Ciro ({unit_label()}, ₺)"}))
    st.caption("Hücredeki sayı müşteri adedi, renk o hücrenin ciro payıdır. Skorlar seçili dönemdeki müşteriler "
               "beşe bölünerek verilir (5 = en yakın / en sık). Müşterilere etiket verilmez.")

# ---------------------------------------------------------------- C7 · Birliktelik kuralları
with block("Birlikte alınan kategoriler (pazar sepeti analizi)"):
    c1, c2 = st.columns([1, 1])
    level = c1.radio("Seviye", ["Ana kategori", "Alt kategori (en sık 25)"], horizontal=True, key="assoc_level")
    min_sup = c2.slider("Minimum destek (%)", 0.5, 10.0, 1.0, 0.5, key="assoc_support",
                        help="Kural tablosunda gösterilecek çiftlerin, tüm faturalar içindeki en düşük payı.")
    lift, rules = association(df, "MainCategory" if level.startswith("Ana") else "Category",
                              top_n=None if level.startswith("Ana") else 25)

    # Renk: log2(lift), 1 (bağımsızlık) ortada. Ölçek verinin gerçek aralığına göre kurulur;
    # 1'in altı (kırmızı) yalnızca veride gerçekten varsa görünür.
    with np.errstate(divide="ignore"):
        z = np.log2(lift.values)
    finite = z[np.isfinite(z)]
    zlo, zhi = min(finite.min(), -0.05), max(finite.max(), 0.05)
    tick_lifts = [v for v in [0.25, 0.5, 0.75, 0.9, 1, 1.5, 2, 3, 4, 6, 8] if zlo <= np.log2(v) <= zhi]
    fig = go.Figure(go.Heatmap(
        z=z, x=lift.columns, y=lift.index, customdata=lift.values, zmid=0, zmin=zlo, zmax=zhi,
        colorscale=DIVERGING, xgap=1, ygap=1,
        colorbar=dict(thickness=10, len=0.9, outlinewidth=0, tickvals=list(np.log2(tick_lifts)),
                      ticktext=[num(v, 2).rstrip("0").rstrip(",") for v in tick_lifts],
                      title=dict(text="Lift", side="top")),
        hovertemplate="%{y} + %{x}<br>Lift %{customdata:.2f}<extra></extra>"))
    layout(fig, height=max(420, 22 * len(lift) + 140), xaxis=dict(showgrid=False, tickangle=-45, tickfont=dict(size=10)),
           yaxis=dict(autorange="reversed", showgrid=False, tickfont=dict(size=10)))

    shown = rules[rules["Destek (%)"] >= min_sup] if len(rules) else rules
    chart_or_table(fig, styled(shown, integer=["Birlikte fatura"], dec2=["Lift"],
                               pct=["Destek (%)", "Güven A→B (%)", "Güven B→A (%)"]),
                   height=420, labels=("Lift ısı haritası", f"Kurallar ({num(len(shown))})"))
    basket = df.groupby("InvoiceNo")["MainCategory"].nunique().mean()
    note = ("Lift = iki kategorinin birlikte görülme sıklığı / bağımsız olsalardı beklenen sıklık. "
            "1: tesadüf düzeyi · 1'in üstü (mavi): beklenenden sık birlikte · 1'in altı (kırmızı): beklenenden seyrek, "
            "farklı müşteri kitleleri. "
            f"Faturalarda ortalama {num(basket, 1)} ana kategori bulunduğundan (B2B toplu sipariş) çiftlerin çoğu "
            "1'in üstündedir; asıl ayırt edici olan diğerlerine göre belirgin yüksek değerlerdir.")
    if len(shown):
        best = shown.iloc[0]
        note = (f"Destek ≥ %{num(min_sup, 1)} olan çiftlerde en güçlü birliktelik: **{best['Kategori A']} + "
                f"{best['Kategori B']}** (lift {num(best['Lift'], 2)}; A alanların %{num(best['Güven A→B (%)'], 1)}'i "
                f"B de alıyor). " + note)
    st.caption(note)

"""2 · Satış — ciro trendi, B3 kategori mevsimselliği, B4 gün × ay, B5 il haritası, B6 COVID dönemleri.

Karşılaştırmalar "günlük ortalama" üzerinden yapılır: bir ayın ya da dönemin
seçili aralığa giren gün sayısı farklı olabileceğinden toplam yerine gün başı
ciro kullanılır (kısmi aylar da adil karşılaştırılır).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.blocks import block, chart, chart_or_table, table
from core.data import amount_col, load_transactions, unit_label
from core.filters import filter_bar, selected_dates
from core.geo import load_provinces, province_key
from core.style import (BLUE, DIVERGING, MONEY_AXIS, MONTHS_TR, ORANGE, SEQUENTIAL, WEEKDAYS_TR,
                        kpi_card, layout, money, num, page_header, pct)
from core.tables import styled
from core.trend import DAILY_MAX_DAYS, first_last_month_change, time_series

PAGE = "satis"
PHASES = ["COVID Öncesi", "Kapanma", "Normalleşme"]
page_header("Satış")

df = filter_bar(load_transactions(), page=PAGE, fields=["date", "main_category", "city"])
start, end = selected_dates(PAGE)
amt = amount_col()
days = pd.date_range(start, end)

# ---------------------------------------------------------------- KPI
by_main = df.groupby("MainCategory", observed=True)[amt].sum().sort_values(ascending=False)
by_city = df.groupby("City", observed=True)[amt].sum().sort_values(ascending=False)
total = df[amt].sum()
chg = first_last_month_change(df, amt, start, end)
kpi_card([
    dict(label="Net ciro", tag=unit_label(), value=money(total),
         delta=chg[0] if chg else None, delta_note=f"{chg[1]} (tam ay)" if chg else "",
         note=None if chg else "Ay karşılaştırması için en az iki tam ay seçin"),
    dict(label="Satılan adet", value=num(df["Quantity"].sum()), note=f"{num(df['StockCode'].nunique())} farklı ürün"),
    dict(label="Fatura", value=num(df["InvoiceNo"].nunique()),
         note=f"Ort. sepet {money(total / df['InvoiceNo'].nunique())}"),
    dict(label="Lider kategori", value=by_main.index[0], note=f"Cironun {pct(by_main.iloc[0] / total * 100)}'i"),
    dict(label="Lider şehir", value=by_city.index[0], note=f"Cironun {pct(by_city.iloc[0] / total * 100)}'i"),
])

# ---------------------------------------------------------------- Ciro trendi
ts, freq = time_series(df, [amt], start, end)
daily = freq == "D"
with block(f"{'Günlük' if daily else 'Haftalık'} ciro trendi ({unit_label()})"):
    hover = "%{x|%d.%m.%Y}" + ("" if daily else " haftası")
    fig = go.Figure(go.Scatter(x=ts.index, y=ts[amt], mode="lines+markers", line=dict(color=BLUE, width=2),
                               marker=dict(size=5), hovertemplate=hover + "<br>%{y:,.0f} ₺<extra></extra>"))
    layout(fig, height=300, yaxis=dict(**MONEY_AXIS, rangemode="tozero"), xaxis=dict(tickformat="%d.%m", showgrid=False))

    t = pd.DataFrame({("Gün" if daily else "Hafta başı"): ts.index.strftime("%d.%m.%Y"), "Ciro": ts[amt].values})
    t["Önceki döneme göre"] = ts[amt].pct_change().replace([np.inf, -np.inf], np.nan).values * 100
    chart_or_table(fig, styled(t, money=["Ciro"], change=["Önceki döneme göre"]), height=320)
    st.caption(f"{DAILY_MAX_DAYS} günden kısa aralıklar günlük, uzun aralıklar haftalık (Pazartesi başlangıçlı) "
               f"gösterilir{'' if daily else '; aralığın kenarındaki eksik haftalar dahil edilmez'}.")

# ---------------------------------------------------------------- B3 · Kategori mevsimselliği
with block("Kategori mevsimselliği"):
    months = pd.period_range(start, end, freq="M")
    if len(months) < 3:
        st.info("Mevsimsellik için en az 3 aylık bir aralık seçin.", icon=":material/calendar_month:")
    else:
        drill = df["MainCategory"].astype(str).nunique() == 1
        dim = "Category" if drill else "MainCategory"

        days_in = pd.Series(1, index=days).groupby(days.month).sum()       # ay başına aralıktaki gün
        g = df.groupby([dim, df["InvoiceDate"].dt.month], observed=True)[amt].sum().unstack(fill_value=0)
        g = g.reindex(columns=days_in.index, fill_value=0)
        totals = g.sum(axis=1).sort_values(ascending=False)
        rows = totals.index[:15] if drill else totals.index
        idx = g.loc[rows].div(days_in, axis=1).div(totals[rows] / days_in.sum(), axis=0) * 100
        mcols = [MONTHS_TR[m - 1] for m in idx.columns]

        fig = go.Figure(go.Heatmap(
            z=idx.values, x=mcols, y=list(idx.index), zmid=100, zmin=0, zmax=200, colorscale=DIVERGING,
            xgap=2, ygap=2, colorbar=dict(thickness=10, len=0.9, title=dict(text="Endeks", side="top"), outlinewidth=0),
            hovertemplate="%{y} · %{x}<br>Endeks %{z:.0f} (100 = ortalama gün)<extra></extra>"))
        layout(fig, height=max(260, 26 * len(rows) + 60),
               yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(showgrid=False, side="top"))

        t = idx.copy()
        t.columns = mcols
        t.insert(0, "Ciro", totals[rows])
        t = t.reset_index().rename(columns={dim: "Alt kategori" if drill else "Ana kategori"})
        chart_or_table(fig, styled(t, money=["Ciro"], index_cols=mcols), height=min(560, 36 * len(t) + 40))

        big = totals[rows][totals[rows] / totals.sum() >= 0.02].index
        note = ("Tek ana kategori seçili: alt kategoriler (ilk 15). " if drill
                else "Bir ana kategori seçilirse alt kategorilere iner. ")
        note += "Endeks: kategorinin o aydaki günlük ortalama cirosu / yıllık günlük ortalaması × 100."
        if len(big):
            s = idx.loc[big].stack()
            pk, lw = s.idxmax(), s.idxmin()
            note += (f" Cironun ≥%2'sini yapan gruplarda en güçlü tepe **{pk[0]}, {MONTHS_TR[pk[1] - 1]}** "
                     f"({num(s[pk])}); en derin dip **{lw[0]}, {MONTHS_TR[lw[1] - 1]}** ({num(s[lw])}).")
        st.caption(note)

# ---------------------------------------------------------------- B4 · Gün × ay
with block("Haftanın günü × ay: ortalama günlük ciro"):
    cal = pd.DataFrame({"wd": days.dayofweek, "m": days.month})
    n_days = cal.groupby(["wd", "m"]).size()
    s = df.groupby([df["InvoiceDate"].dt.dayofweek, df["InvoiceDate"].dt.month])[amt].sum()
    s.index.names = ["wd", "m"]
    avg = (s.reindex(n_days.index, fill_value=0) / n_days).unstack()
    mcols = [MONTHS_TR[m - 1] for m in avg.columns]
    fig = go.Figure(go.Heatmap(
        z=avg.values, x=mcols, y=[WEEKDAYS_TR[w] for w in avg.index], colorscale=SEQUENTIAL,
        xgap=2, ygap=2, colorbar=dict(thickness=10, len=0.9, outlinewidth=0, tickformat=",.0f"),
        hovertemplate="%{y} · %{x}<br>Ortalama %{z:,.0f} ₺ / gün<extra></extra>"))
    layout(fig, height=300, yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(showgrid=False))

    t = avg.copy()
    t.columns = mcols
    t.insert(0, "Gün", [WEEKDAYS_TR[w] for w in t.index])
    chart_or_table(fig, styled(t, money=mcols))
    wd_avg = s.groupby(level="wd").sum() / cal.groupby("wd").size()
    st.caption(f"En yoğun gün **{WEEKDAYS_TR[wd_avg.idxmax()]}** (ortalama {money(wd_avg.max())}/gün). "
               "Hücre: o ayın ilgili günlerinde ortalama günlük ciro. Sevkiyat ve depo vardiya planı için.")

# ---------------------------------------------------------------- B5 · İl haritası
with block("İllere göre ciro"):
    geo = load_provinces()
    known = by_city.drop("Bilinmiyor", errors="ignore")
    keys = [province_key(c) for c in known.index]
    share = known.values / total * 100
    all_keys = [f["id"] for f in geo["features"]]

    vmin, vmax = np.log10(max(known.min(), 1)), np.log10(known.max())
    ticks = [v for v in range(int(np.floor(vmin)), int(np.ceil(vmax)) + 1)]
    labels = {2: "100", 3: "1 bin", 4: "10 bin", 5: "100 bin", 6: "1 M", 7: "10 M", 8: "100 M"}
    fig = go.Figure([
        go.Choropleth(geojson=geo, locations=all_keys, z=[0] * len(all_keys), showscale=False, hoverinfo="skip",
                      colorscale=[[0, "rgba(128,128,128,0.12)"], [1, "rgba(128,128,128,0.12)"]],
                      marker_line_color="rgba(128,128,128,0.5)", marker_line_width=0.5),
        go.Choropleth(geojson=geo, locations=keys, z=np.log10(known.values), colorscale=SEQUENTIAL,
                      zmin=vmin, zmax=vmax, marker_line_color="rgba(255,255,255,0.7)", marker_line_width=0.6,
                      customdata=[[str(c), float(v), float(s)] for c, v, s in zip(known.index, known.values, share)],
                      colorbar=dict(orientation="h", thickness=10, len=0.5, x=0.5, xanchor="center", y=-0.02,
                                    yanchor="top", outlinewidth=0, title=dict(text="Ciro (₺)", side="top"),
                                    tickvals=ticks, ticktext=[labels.get(v, str(v)) for v in ticks]),
                      hovertemplate="%{customdata[0]}<br>%{customdata[1]:,.0f} ₺ · cironun %{customdata[2]:.1f}%'i"
                                    "<extra></extra>"),
    ])
    # Türkiye sınırları sabit: harita bloğun genişliğini doldurur (en-boy oranı ~2,4:1)
    fig.update_geos(visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)",
                    lonaxis_range=[25.6, 44.9], lataxis_range=[35.7, 42.2], domain=dict(x=[0, 1], y=[0.06, 1]))
    layout(fig, height=540, margin=dict(l=0, r=0, t=0, b=0))

    c = df.groupby("City", observed=True).agg(Ciro=(amt, "sum"), Müşteri=("CustomerID", "nunique"),
                                              Fatura=("InvoiceNo", "nunique"))
    c = c.sort_values("Ciro", ascending=False)
    c["Pay (%)"] = c["Ciro"] / total * 100
    c["Müşteri başı ciro"] = c["Ciro"] / c["Müşteri"]
    c = c.reset_index().rename(columns={"City": "İl"})
    c.insert(0, "Sıra", range(1, len(c) + 1))
    chart_or_table(fig, styled(c, money=["Ciro", "Müşteri başı ciro"], integer=["Sıra", "Müşteri", "Fatura"],
                               pct=["Pay (%)"]), height=420, labels=("Harita", "Tablo"))
    unknown = by_city.get("Bilinmiyor", 0)
    st.caption(f"Renk ölçeği logaritmiktir (lider il {known.index[0]}, ciro payı {pct(known.iloc[0] / total * 100)}). "
               f"{num(len(known))} ile satış var; gri iller satışsız."
               + (f" İli bilinmeyen satırlar: {money(unknown)} ({pct(unknown / total * 100)})." if unknown else ""))

# ---------------------------------------------------------------- B6 · COVID dönemleri
with block("COVID dönemleri: satış günü başına ciro"):
    present = [p for p in PHASES if p in set(df["CovidPhase"].astype(str))]
    if len(present) < 2:
        st.info("Dönem karşılaştırması için seçili aralık en az iki dönemi kapsamalı "
                "(Öncesi: –10.03 · Kapanma: 11.03–31.05 · Normalleşme: 01.06–).", icon=":material/coronavirus:")
    else:
        sales_days = df.groupby("CovidPhase", observed=True)["InvoiceDate"].nunique().reindex(present)
        ph = df.groupby("CovidPhase", observed=True)[amt].sum().reindex(present) / sales_days
        fig = go.Figure(go.Bar(
            x=present, y=ph.values, marker_color=[ORANGE if p == "Kapanma" else BLUE for p in present], width=0.45,
            text=[money(v) for v in ph.values], textposition="outside", cliponaxis=False,
            hovertemplate="%{x}<br>%{y:,.0f} ₺ / satış günü<extra></extra>"))
        layout(fig, height=280, yaxis=dict(**MONEY_AXIS, range=[0, ph.max() * 1.2]), xaxis=dict(showgrid=False))
        chart(fig)
        st.caption(" · ".join(f"{p}: {pct((v / ph.iloc[0] - 1) * 100, sign=True)}" for p, v in ph.iloc[1:].items())
                   + f" ({present[0]} dönemine göre). Dönemlerin gün sayısı farklı olduğu için gün başı ciro kullanılır.")

        st.markdown("Ana kategorilerde dönem değişimi")
        cc = df.groupby(["MainCategory", "CovidPhase"], observed=True)[amt].sum().unstack().reindex(columns=present)
        cc = cc.div(sales_days, axis=1)
        t = pd.DataFrame({"Ana kategori": cc.index.astype(str)})
        for p in present:
            t[f"{p} (gün başı)"] = cc[p].values
        for p in present[1:]:
            t[f"{p} değişim"] = ((cc[p] / cc[present[0]] - 1) * 100).values
        t = t.sort_values(f"{present[1]} değişim")
        table(styled(t, money=[f"{p} (gün başı)" for p in present], change=[f"{p} değişim" for p in present[1:]]),
              height=min(600, 36 * len(t) + 40))
        st.caption(f"Tablo {present[1].lower()} döneminde en çok düşen kategoriden başlar.")

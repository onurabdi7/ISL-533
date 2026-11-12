"""5 · Veri Kalitesi — F2 rapor tabloları + uç satış ve dönemsel indirim sekmesi.

Raporlar kod.py Adım 2-3'te üretilen CSV'lerden okunur. Uç satış ve indirim
bayrakları (is_outlier, DiscountBand) Adım 3'te Tukey yöntemiyle belirlenmiştir.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.blocks import block, chart_or_table, table
from core.data import gross_col, amount_col, load_report, load_transactions, unit_label
from core.style import (BLUE, MONTHS_TR, ORANGE, SEQUENTIAL, kpi_card, layout, money, num, page_header, pct)
from core.tables import styled

page_header("Veri Kalitesi")

log = load_report("cleaning_log")
missing = load_report("missing")
invalid = load_report("invalid")
thr = load_report("thresholds")

raw, final = int(log["Satır"].iloc[0]), int(log["Satır"].iloc[-1])
dup = int(log.loc[log["Kural"] == "DUPLICATE", "Satır"].iloc[0])
kpi_card([
    dict(label="Ham satır", value=num(raw), note="B2B_Transaction_Data_.xlsx"),
    dict(label="Silinen tekrar", value=num(dup), note=f"Ham verinin {pct(dup / raw * 100, 2)}'i"),
    dict(label="Geçersiz bayraklı", value=num(len(invalid)), note="Analize alınmadı, silinmedi"),
    dict(label="Analiz kümesi", value=num(final), note=f"Ham verinin {pct(final / raw * 100, 2)}'i"),
    dict(label="Eksik değerli sütun", value=num(len(missing)), note=", ".join(missing["Sütun"])),
])

tabs = st.tabs(["Temizlik günlüğü", "Eksik veri", "Geçersiz satırlar", "Uç satış & indirim"])

# ---------------------------------------------------------------- Temizlik günlüğü
with tabs[0]:
    table(styled(log, integer=["Satır"], money=["Ciro Etkisi"]))
    st.caption("Usul: bayrakla, raporla, analizden dışla. Fiziksel olarak yalnızca birebir tekrarlı satırlar silindi; "
               "diğer sorunlu satırlar dq_flag ile işaretlenip analiz dışında tutuldu. Bir satır birden fazla kurala "
               "takılabilir. Ciro etkisi nominal (Miktar × Net fiyat).")

# ---------------------------------------------------------------- Eksik veri
with tabs[1]:
    table(styled(missing, integer=["Eksik Satır", "Etkilenen Müşteri", "Etkilenen Ürün"], dec2=["Oran (%)"],
                 money=["Ciro Etkisi"]))
    st.caption("Her müşterinin tek şehri, her ürünün tek kategorisi olduğundan boş değerler başka satırlardan "
               "doldurulamadı; etiketlendi. Rapor tekrarlar silindikten sonraki veri üzerindedir.")

# ---------------------------------------------------------------- Geçersiz satırlar
with tabs[2]:
    cols = ["InvoiceNo", "CustomerID", "InvoiceDate", "Description", "Quantity", "NetPrice", "UnitPrice", "dq_flag"]
    t = invalid[cols].rename(columns={"InvoiceNo": "Fatura", "CustomerID": "Müşteri", "InvoiceDate": "Tarih",
                                      "Description": "Ürün", "Quantity": "Adet", "NetPrice": "Net fiyat",
                                      "UnitPrice": "Liste fiyatı", "dq_flag": "Kural(lar)"})
    table(styled(t, dec2=["Net fiyat", "Liste fiyatı"], integer=["Adet"]))
    st.caption("QTY_MISSING: miktar boş · QTY_ZERO: miktar sıfır · NETPRICE_NONPOSITIVE: net fiyat ≤ 0 · "
               "NETPRICE_GT_UNITPRICE: negatif indirim · UNITPRICE_PLACEHOLDER: liste fiyatı < 0,01.")

# ---------------------------------------------------------------- Uç satış & indirim
with tabs[3]:
    df = load_transactions()
    cats = df.groupby("MainCategory", observed=True)["LineNet"].sum().sort_values(ascending=False).index.tolist()
    sel = st.multiselect("Ana kategori", cats, placeholder="Tümü", key="dq_cats")
    if sel:
        df = df[df["MainCategory"].isin(sel)]
    amt, gross = amount_col(), gross_col()
    total = df[amt].sum()
    out = df[df["is_outlier"]]
    hi_d, lo_d = df["DiscountBand"] == "Yüksek İndirim", df["DiscountBand"] == "Düşük İndirim"
    line_thr = thr["Üst Sınır"].iloc[0]
    kpi_card([
        dict(label="Uç satış satırı", value=num(len(out)), note=f"Satır tutarı > {money(line_thr)} (reel)"),
        dict(label="Uç satışların ciro payı", value=pct(out[amt].sum() / total * 100),
             note=f"Satırların {pct(len(out) / len(df) * 100, 2)}'i"),
        dict(label="Ağırlıklı indirim", value=pct((df[gross].sum() - total) / df[gross].sum() * 100),
             note="İndirim tutarı / liste tutarı"),
        dict(label="Yüksek indirimli satır", value=num(hi_d.sum()), note=f"İndirim > %{num(thr['Üst Sınır'].iloc[1] * 100, 0)}"),
        dict(label="Düşük indirimli satır", value=num(lo_d.sum()), note=f"İndirim < %{num(thr['Alt Sınır'].iloc[1] * 100, 0)}"),
    ])

    # Dönemsel indirim
    with block("Dönemsel indirim: aylık ağırlıklı indirim oranı"):
        m = df.groupby("Month").agg(G=(gross, "sum"), N=(amt, "sum"))
        m["Oran"] = (m["G"] - m["N"]) / m["G"] * 100
        mlab = [MONTHS_TR[i - 1] for i in m.index]
        fig = go.Figure(go.Scatter(x=mlab, y=m["Oran"], mode="lines+markers", line=dict(color=BLUE, width=2),
                                   marker=dict(size=7), hovertemplate="%{x}: %{y:.1f}%<extra></extra>"))
        layout(fig, height=260, yaxis=dict(ticksuffix="%", title="Ağırlıklı indirim"), xaxis=dict(showgrid=False))

        t = pd.DataFrame({"Ay": mlab, "Liste tutarı": m["G"].values, "Net ciro": m["N"].values,
                          "İndirim tutarı": (m["G"] - m["N"]).values, "İndirim oranı (%)": m["Oran"].values,
                          "Önceki aya göre": m["Oran"].diff().values})
        chart_or_table(fig, styled(t, money=["Liste tutarı", "Net ciro", "İndirim tutarı"], pct=["İndirim oranı (%)"],
                                   change_pp=["Önceki aya göre"]))

        st.markdown("Ana kategori × ay")
        cm = df.groupby(["MainCategory", "Month"], observed=True).agg(G=(gross, "sum"), N=(amt, "sum"))
        cm = ((cm["G"] - cm["N"]) / cm["G"] * 100).unstack()
        cm = cm.loc[[c for c in cats if c in cm.index]]
        cm.columns = [MONTHS_TR[i - 1] for i in cm.columns]
        fig = go.Figure(go.Heatmap(
            z=cm.values, x=list(cm.columns), y=list(cm.index), colorscale=SEQUENTIAL, xgap=2, ygap=2,
            colorbar=dict(thickness=10, len=0.9, outlinewidth=0, ticksuffix="%"),
            hovertemplate="%{y} · %{x}<br>İndirim %{z:.1f}%<extra></extra>"))
        layout(fig, height=max(240, 26 * len(cm) + 60), yaxis=dict(autorange="reversed", showgrid=False),
               xaxis=dict(showgrid=False, side="top"))
        tt = cm.reset_index().rename(columns={"MainCategory": "Ana kategori"})
        chart_or_table(fig, styled(tt, pct=list(cm.columns)), height=min(600, 36 * len(tt) + 40))
        st.caption("Ağırlıklı indirim = (liste tutarı − net ciro) / liste tutarı. Tabloda indirim artışı kırmızı "
                   "(marj kaybı), azalışı yeşil gösterilir.")

    # Uç satışlar
    with block("Uç satışlar: belge serisine göre"):
        s = df.groupby("DocSeries", observed=True).agg(Satır=("InvoiceNo", "size"), Ciro=(amt, "sum"))
        so = out.groupby("DocSeries", observed=True).agg(Uç_satır=("InvoiceNo", "size"), Uç_ciro=(amt, "sum"))
        s = s.join(so).fillna(0)
        s["Uç ciro payı (%)"] = s["Uç_ciro"] / s["Ciro"] * 100
        s = s[s["Satır"] > 0].sort_values("Uç ciro payı (%)", ascending=False)
        fig = go.Figure(go.Bar(
            x=s.index.astype(str), y=s["Uç ciro payı (%)"], width=0.5,
            marker_color=[ORANGE if v > 50 else BLUE for v in s["Uç ciro payı (%)"]],
            text=[pct(v) for v in s["Uç ciro payı (%)"]], textposition="outside", cliponaxis=False,
            hovertemplate="%{x}: cironun %{y:.1f}%'i uç satırlardan<extra></extra>"))
        layout(fig, height=260, yaxis=dict(ticksuffix="%", range=[0, max(100, s["Uç ciro payı (%)"].max() * 1.15)]),
               xaxis=dict(showgrid=False))
        t = s.reset_index().rename(columns={"DocSeries": "Belge serisi", "Uç_satır": "Uç satır", "Uç_ciro": "Uç ciro"})
        chart_or_table(fig, styled(t, integer=["Satır", "Uç satır"], money=["Ciro", "Uç ciro"], pct=["Uç ciro payı (%)"]))

        st.markdown(f"En büyük 200 uç satır ({unit_label()})")
        top = out.nlargest(200, amt)[["InvoiceNo", "InvoiceDate", "CustomerID", "Description", "MainCategory",
                                     "Quantity", "NetPrice", amt, "DiscountRate", "DocSeries"]].copy()
        top["InvoiceDate"] = top["InvoiceDate"].dt.strftime("%d.%m.%Y")
        top["DiscountRate"] *= 100
        top = top.rename(columns={"InvoiceNo": "Fatura", "InvoiceDate": "Tarih", "CustomerID": "Müşteri",
                                  "Description": "Ürün", "MainCategory": "Ana kategori", "Quantity": "Adet",
                                  "NetPrice": "Net birim fiyat", amt: "Satır tutarı", "DiscountRate": "İndirim (%)",
                                  "DocSeries": "Seri"})
        table(styled(top, integer=["Adet"], money=["Satır tutarı"], dec2=["Net birim fiyat"], pct=["İndirim (%)"]),
              height=380)
        st.caption("Uç satış: reel satır tutarı, log ölçeğinde Tukey üst sınırını (k=3) aşan satırlar. Silinmez; "
                   "B2B toplu alımları olabilir. DPE/DPF serilerinde payın yüksek olması toplu alım kanalına işaret eder.")

    with st.expander("Eşik yöntemi"):
        table(styled(thr, integer=["Satır"], dec2=["Alt Sınır", "Üst Sınır", "Satır (%)", "Ciro Payı (%)"]))

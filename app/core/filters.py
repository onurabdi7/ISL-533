"""Sayfa bazlı filtre şeridi.

Her sayfa kendi filtre setini kullanır; seçimler sayfaya özeldir ve sayfalar
arasında gezinirken korunur.

Kalıcılık notu: Streamlit, o çalıştırmada çizilmeyen widget'ların durumunu
siler. Bu yüzden değerler widget anahtarından ("_w_...") ayrı, kalıcı bir
anahtarda ("flt_...") tutulur; widget her çizimde kalıcı değerden başlatılır.

Tarih filtresi iki ayrı alandır (Başlangıç / Bitiş). Varsayılan aralık verinin
kapsadığı tam aylardır (01.01 – 31.12), böylece "tam ay" karşılaştırmaları
varsayılan görünümde Ocak'ı da içerir.
"""

from datetime import date

import pandas as pd
import streamlit as st

# alan kodu -> (sütun, etiket, widget türü)
FIELDS = {
    "date": ("InvoiceDate", "Tarih", "date"),
    "main_category": ("MainCategory", "Ana kategori", "multiselect"),
    "city": ("City", "Şehir", "multiselect"),
    "value_group": ("ValueGroup", "Değer grubu", "pills"),
    "pattern": ("PurchasePattern", "Alım düzeni", "pills"),
}
ORDER = {
    "ValueGroup": ["Yüksek Değer", "Orta Değer", "Düşük Değer"],
    "PurchasePattern": ["Düzenli", "Dönemsel", "Seyrek", "Tek Seferlik"],
}


# --------------------------------------------------------------------------
# Durum anahtarları ve varsayılanlar
# --------------------------------------------------------------------------
def _keys(page: str, name: str) -> tuple[str, str]:
    """name: alan kodu ya da 'date_start' / 'date_end'"""
    return f"flt_{page}_{name}", f"_w_{page}_{name}"


def data_bounds(df: pd.DataFrame) -> tuple[date, date]:
    """Verinin kapsadığı tam ayların ilk ve son günü."""
    lo = df["InvoiceDate"].min().to_period("M").start_time.date()
    hi = df["InvoiceDate"].max().to_period("M").end_time.date()
    return lo, hi


def _state_names(fields: list[str]) -> list[str]:
    names = []
    for f in fields:
        names += ["date_start", "date_end"] if f == "date" else [f]
    return names


def _defaults(df: pd.DataFrame, fields: list[str]) -> dict:
    d = {}
    if "date" in fields:
        d["date_start"], d["date_end"] = data_bounds(df)
    for f in fields:
        if f != "date":
            d[f] = []
    return d


def _options(df: pd.DataFrame, col: str) -> list[str]:
    if col in ORDER:
        return ORDER[col]
    # Çok seçenekli listeler ciroya göre sıralanır (en önemli üstte)
    return df.groupby(col, observed=True)["LineNet"].sum().sort_values(ascending=False).index.tolist()


# --------------------------------------------------------------------------
# Geri çağrımlar
# --------------------------------------------------------------------------
def _reset(page: str, defaults: dict) -> None:
    for name, value in defaults.items():
        keep, widget = _keys(page, name)
        st.session_state[keep] = value
        st.session_state[widget] = value


def _sync(page: str, name: str) -> None:
    keep, widget = _keys(page, name)
    value = st.session_state[widget]
    if name in ("date_start", "date_end") and value is None:   # alan temizlendiyse eski değer kalır
        return
    st.session_state[keep] = value

    # Başlangıç bitişten sonraya alınırsa diğer uç aynı güne çekilir
    if name in ("date_start", "date_end"):
        s_keep, e_keep = _keys(page, "date_start")[0], _keys(page, "date_end")[0]
        s, e = st.session_state[s_keep], st.session_state[e_keep]
        if s > e:
            other = e_keep if name == "date_start" else s_keep
            st.session_state[other] = value


# --------------------------------------------------------------------------
# Şerit
# --------------------------------------------------------------------------
def filter_bar(df: pd.DataFrame, page: str, fields: list[str]) -> pd.DataFrame:
    """Sayfanın üstüne filtre şeridini çizer ve filtrelenmiş veriyi döndürür."""
    defaults = _defaults(df, fields)
    for name, value in defaults.items():
        keep, widget = _keys(page, name)
        st.session_state.setdefault(keep, value)
        st.session_state[widget] = st.session_state[keep]

    # Düzen: 1. satır tarih (iki dar alan) + açılır listeler + Sıfırla;
    # 2. satır seçenek düğmeleri (pills) - etiketleri kırpılmasın diye geniş alanda.
    pills = [f for f in fields if FIELDS[f][2] == "pills"]
    slots = []
    for f in fields:
        if f == "date":
            slots += [("date_start", 0.8), ("date_end", 0.8)]
        elif f not in pills:
            slots.append((f, 1.3))
    lo, hi = data_bounds(df)

    def render(name: str) -> None:
        widget = _keys(page, name)[1]
        if name == "date_start":
            st.date_input("Başlangıç", min_value=lo, max_value=hi, format="DD.MM.YYYY",
                          key=widget, on_change=_sync, args=(page, name))
        elif name == "date_end":
            st.date_input("Bitiş", min_value=lo, max_value=hi, format="DD.MM.YYYY",
                          key=widget, on_change=_sync, args=(page, name))
        else:
            column, label, kind = FIELDS[name]
            if kind == "multiselect":
                st.multiselect(label, _options(df, column), key=widget, placeholder="Tümü",
                               on_change=_sync, args=(page, name))
            else:
                st.pills(label, _options(df, column), selection_mode="multi", key=widget,
                         on_change=_sync, args=(page, name), help="Seçim yoksa tümü dahildir.")

    with st.container(border=True):
        cols = st.columns([w for _, w in slots] + [0.5], vertical_alignment="bottom")
        for col_ui, (name, _) in zip(cols, slots):
            with col_ui:
                render(name)
        with cols[-1]:
            st.button("Sıfırla", key=f"reset_{page}", on_click=_reset, args=(page, defaults), width="stretch")
        if pills:
            for col_ui, name in zip(st.columns(len(pills)), pills):
                with col_ui:
                    render(name)

        values = {name: st.session_state[_keys(page, name)[0]] for name in defaults}

        # Filtreleri uygula
        mask = pd.Series(True, index=df.index)
        if "date_start" in values:
            mask &= df["InvoiceDate"].between(pd.Timestamp(values["date_start"]), pd.Timestamp(values["date_end"]))
        for name, v in values.items():
            if not name.startswith("date_") and v:
                mask &= df[FIELDS[name][0]].isin(v)
        out = df[mask]

    if out.empty:
        st.warning("Seçili filtrelerle eşleşen satış yok. Filtreleri genişletin ya da **Sıfırla**'ya basın.")
        st.stop()
    return out


def selected_dates(page: str) -> tuple[date, date] | None:
    """Sayfanın seçili tarih aralığı (tarih filtresi yoksa None)."""
    s = st.session_state.get(_keys(page, "date_start")[0])
    e = st.session_state.get(_keys(page, "date_end")[0])
    return (s, e) if s and e else None

"""Türkiye il sınırları (GeoJSON) ve il adı eşleme.

Kaynak: github.com/cihadturhan/tr-geojson (geo/tr-cities-utf8.json), 81 il.
Veride iller büyük harf ve ASCII'ye yakın yazılmış (ISTANBUL, ELAZIG, K.MARAS);
her iki taraf aynı anahtara indirgenir. Eski adlar için takma ad tablosu kullanılır.
"""

import json

import streamlit as st

from core.data import DATA_DIR

_TR = str.maketrans("ÇĞİÖŞÜçğıöşüâÂîÎûÛ", "CGIOSUCGIOSUAAIIUU")
ALIASES = {"ICEL": "MERSIN", "K.MARAS": "KAHRAMANMARAS"}


def province_key(name: str) -> str:
    k = name.translate(_TR).upper().strip()
    return ALIASES.get(k, k)


@st.cache_data(show_spinner=False)
def load_provinces() -> dict:
    with open(DATA_DIR / "ref_tr_provinces.geojson", encoding="utf-8") as f:
        geo = json.load(f)
    for feat in geo["features"]:
        feat["id"] = province_key(feat["properties"]["name"])
    return geo

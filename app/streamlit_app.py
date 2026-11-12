"""ISL 533 - ÖDEV-I | B2B Kitap Dağıtıcısı Akıllı Gösterge Paneli (giriş dosyası).

Çalıştırma (repo kökünden):
    streamlit run app/streamlit_app.py

Sayfa yapısı st.navigation ile kurulur; her sayfa views/ altındadır.
Nominal/Reel birim seçimi kenar çubuğunda globaldir; sayfa filtreleri
her sayfanın üstündedir (core/filters.py).
"""

import streamlit as st

from core.data import UNIT_KEY, UNIT_NOMINAL, UNIT_REAL
from core.style import inject_css

st.set_page_config(page_title="B2B Kitap Dağıtım Paneli", page_icon=":material/menu_book:", layout="wide")
inject_css()

pages = st.navigation([
    st.Page("views/satis.py", title="Satış", icon=":material/trending_up:", default=True),
    st.Page("views/musteri.py", title="Müşteri & Pazarlama", icon=":material/groups:"),
    st.Page("views/urun.py", title="Ürün & Tedarik", icon=":material/inventory_2:"),
    st.Page("views/kalite.py", title="Veri Kalitesi", icon=":material/fact_check:"),
    st.Page("views/kilavuz.py", title="Kullanım Kılavuzu", icon=":material/help:"),
])

with st.sidebar:
    st.radio(
        "Tutar birimi", [UNIT_REAL, UNIT_NOMINAL], key=UNIT_KEY, horizontal=True,
        help="Reel: tutarlar TÜİK TÜFE (2003=100) ile Aralık 2020 fiyatlarına taşınır. "
             "Nominal: faturadaki tutarlar.",
    )
    st.caption("Reel = Aralık 2020 fiyatlarıyla (TÜFE)")
    st.divider()
    st.caption("Veri: 02.01–31.12.2020 · 657.920 geçerli satır · 1.201 müşteri")

pages.run()

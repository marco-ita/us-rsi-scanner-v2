import streamlit as st
import pandas as pd
import os


st.set_page_config(page_title="US Market Scanner - Ultra Fast", layout="wide")

st.title("📈 Scanner USA - RSI & Trend Calibrato (SMA 40 / 200)")
st.caption("Dashboard istantanea alimentata da pre-elaborazione dati.")

@st.cache_data(ttl=3600)
def load_data():
    file_path = "market_data.csv"
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame()

df_raw = load_data()

if df_raw.empty:
    st.error("⚠️ File `market_data.csv` non trovato o vuoto. Esegui prima lo script `update_data.py` per generare i dati.")
else:
    # Sidebar Filters
    st.sidebar.header("Opzioni Visualizzazione")
    show_all = st.sidebar.checkbox("Mostra TUTTI i titoli (inclusi RSI neutri)", value=False)
    
    if show_all:
        df = df_raw.copy()
    else:
        df = df_raw[df_raw["Stato RSI"].str.contains("Ipervenduto|Ipercomprato", regex=True)].copy()

    col1, col2, col3 = st.columns(3)
    totale = len(df_raw)
    ipervenduti = len(df_raw[df_raw['RSI 14'] <= 30])
    ipercomprati = len(df_raw[df_raw['RSI 14'] >= 70])
    
    col1.metric("Totale Asset Monitorati", totale)
    col2.metric("Ipervenduto (RSI ≤ 30) 🟢", ipervenduti)
    col3.metric("Ipercomprato (RSI ≥ 70) 🔴", ipercomprati)

    st.markdown("---")

    st.sidebar.header("Filtri Avanzati")
    search_query = st.sidebar.text_input("Cerca Ticker o Nome Società:", "").strip()
    
    rsi_options = list(df["Stato RSI"].unique())
    filtro_rsi = st.sidebar.multiselect("Stato RSI:", options=rsi_options, default=rsi_options)
    
    trend200_options = list(df["Trend SMA 200"].unique())
    filtro_trend200 = st.sidebar.multiselect("Trend SMA 200:", options=trend200_options, default=trend200_options)

    df_filtered = df[
        (df["Stato RSI"].isin(filtro_rsi)) & 
        (df["Trend SMA 200"].isin(filtro_trend200))
    ]
    
    if search_query:
        df_filtered = df_filtered[
            df_filtered["Ticker"].str.contains(search_query.upper(), case=False, na=False) |
            df_filtered["Nome Asset"].str.contains(search_query, case=False, na=False)
        ]

    st.subheader(f"Risultati ({len(df_filtered)} asset)")
    st.dataframe(
        df_filtered,
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker"),
            "Nome Asset": st.column_config.TextColumn("Nome Società / Asset"),
            "RSI 14": st.column_config.NumberColumn("RSI (14)", format="%.2f"),
            "Prezzo ($)": st.column_config.NumberColumn("Prezzo", format="$%.2f"),
            "SMA 40 ($)": st.column_config.NumberColumn("SMA 40", format="$%.2f"),
            "Trend SMA 40": st.column_config.TextColumn("Trend SMA 40 (15gg)"),
            "SMA 200 ($)": st.column_config.NumberColumn("SMA 200", format="$%.2f"),
            "Trend SMA 200": st.column_config.TextColumn("Trend SMA 200 (35gg)"),
            "Posizione Medie": st.column_config.TextColumn("Posizione Relativa"),
        },
        use_container_width=True,
        hide_index=True
    )

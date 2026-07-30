import streamlit as st
import pandas as pd

st.set_page_config(page_title="US Market RSI Scanner", layout="wide")

st.title("📈 Scanner RSI - Mercato Azionario USA")
st.caption("Aggiornato automaticamente ogni giorno alla chiusura di Wall Street.")

@st.cache_data(ttl=3600)
def load_data():
    try:
        return pd.read_csv("rsi_market_data.csv")
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("I dati non sono ancora stati generati. Attendi il primo completamento di GitHub Actions.")
else:
    col1, col2, col3, col4 = st.columns(4)
    totale = len(df)
    ipervenduti = len(df[df['RSI_14'] <= 30])
    ipercomprati = len(df[df['RSI_14'] >= 70])
    
    col1.metric("Totale Asset Scansionati", totale)
    col2.metric("Ipervenduti (RSI ≤ 30)", ipervenduti)
    col3.metric("Ipercomprati (RSI ≥ 70)", ipercomprati)
    col4.metric("Asset Neutri", totale - (ipervenduti + ipercomprati))

    st.markdown("---")

    st.sidebar.header("Filtri")
    search_ticker = st.sidebar.text_input("Cerca Ticker Specifico:", "").upper()
    
    filtro_stato = st.sidebar.multiselect(
        "Filtra per Stato RSI:",
        options=df["Stato"].unique(),
        default=df["Stato"].unique()
    )
    
    rsi_range = st.sidebar.slider(
        "Seleziona Range RSI:",
        min_value=0.0,
        max_value=100.0,
        value=(0.0, 100.0)
    )

    df_filtered = df[
        (df["Stato"].isin(filtro_stato)) &
        (df["RSI_14"] >= rsi_range[0]) &
        (df["RSI_14"] <= rsi_range[1])
    ]
    
    if search_ticker:
        df_filtered = df_filtered[df_filtered["Ticker"].str.contains(search_ticker)]

    st.subheader(f"Risultati ({len(df_filtered)} asset trovati)")
    
    st.dataframe(
        df_filtered,
        column_config={
            "RSI_14": st.column_config.NumberColumn("RSI (14)", format="%.2f"),
            "Prezzo": st.column_config.NumberColumn("Prezzo ($)", format="$%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )
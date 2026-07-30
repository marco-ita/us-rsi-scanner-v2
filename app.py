import streamlit as st
import pandas as pd
import time

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="US Stock RSI Extreme Scanner",
    page_icon="📈",
    layout="wide"
)

# Titolo dell'applicazione
st.title("📈 US Stock Market Scanner (eToro SMMA - RSI Estremi ≤ 30 o ≥ 70)")
st.write("Dashboard di analisi in tempo reale sui titoli del mercato USA in condizione di **Ipervenduto (RSI ≤ 30)** o **Ipercomprato (RSI ≥ 70)** con parametri eToro (SMMA 40 & 200).")

# Pulsante di ricaricamento forzato nella barra laterale
st.sidebar.header("Opzioni Dashboard")
if st.sidebar.button("🔄 Forza Ricaricamento Dati"):
    st.cache_data.clear()
    st.rerun()

# Funzione per caricare i dati con svuotamento cache ogni 60 secondi
@st.cache_data(ttl=60)
def load_data():
    raw_url = f"https://raw.githubusercontent.com/marco-ita/us-rsi-scanner-v2/main/market_data.csv?v={int(time.time())}"
    try:
        df = pd.read_csv(raw_url)
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento del file CSV da GitHub: {e}")
        return pd.DataFrame()

# Caricamento effettivo dei dati dal CSV generato da GitHub Actions
df = load_data()

if not df.empty:
    # Filtri secondari nella barra laterale
    st.sidebar.subheader("Filtri Dati")
    
    all_tickers = df['Ticker'].unique().tolist()
    selected_tickers = st.sidebar.multiselect("Seleziona Ticker:", options=all_tickers, default=all_tickers)
    
    if 'Stato RSI' in df.columns:
        all_rsi_states = df['Stato RSI'].unique().tolist()
        selected_rsi_states = st.sidebar.multiselect("Stato RSI:", options=all_rsi_states, default=all_rsi_states)
        df_filtered = df[(df['Ticker'].isin(selected_tickers)) & (df['Stato RSI'].isin(selected_rsi_states))]
    else:
        df_filtered = df[df['Ticker'].isin(selected_tickers)]

    # Mostra statistiche veloci
    col1, col2, col3 = st.columns(3)
    col1.metric("Totale Asset in Segnale Estremo", len(df_filtered))
    
    if 'Stato RSI' in df.columns:
        ipervenduti = len(df_filtered[df_filtered['Stato RSI'].str.contains('Ipervenduto', na=False)])
        col2.metric("In Ipervenduto (RSI ≤ 30)", ipervenduti)
        
        ipercomprati = len(df_filtered[df_filtered['Stato RSI'].str.contains('Ipercomprato', na=False)])
        col3.metric("In Ipercomprato (RSI ≥ 70)", ipercomprati)

    st.markdown("---")

    # Tabella principale dei dati
    st.subheader("Risultati Scansione Mercato USA")
    st.dataframe(
        df_filtered,
        use_container_width=True,
        hide_index=True
    )

    st.caption("I dati vengono aggiornati automaticamente dal workflow di GitHub Actions.")
else:
    st.info("Al momento nessun titolo del mercato USA si trova in condizione di Ipervenduto (RSI ≤ 30) o Ipercomprato (RSI ≥ 70).")

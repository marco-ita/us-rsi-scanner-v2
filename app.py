import streamlit as st
import pandas as pd

# 1. Configurazione della Pagina
st.set_page_config(
    page_title="Market Scanner Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Funzione di caricamento dati con Caching
@st.cache_data(ttl=1800)  # Aggiorna la cache ogni 30 minuti
def load_market_data():
    try:
        df = pd.read_csv('market_data.csv', encoding='utf-8')
        
        # Pulizia/Assicurazione tipi di dato
        numeric_cols = ['Prezzo ($)', 'RSI 14', 'SMA 40 ($)', 'SMA 200 ($)']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Errore durante la lettura del file CSV: {e}")
        return None

# Caricamento Dati
df = load_market_data()

# 3. Interfaccia e Gestione Errori Iniziale
if df is None:
    st.error("⚠️ Il file `market_data.csv` non è stato trovato nel repository GitHub.")
    st.info("Assicurati di aver fatto il commit e push del file `market_data.csv` nella stessa directory di `app.py`.")
    st.stop()

# 4. Header e Statistiche Rapide
st.title("📈 Global Market Scanner & Indicators")
st.markdown("Analisi tecnica avanzata su azionario ed ETF eToro/Yahoo Finance.")

total_assets = len(df)
ipervenduti = len(df[df['Stato RSI'].str.contains('Ipervenduto', na=False)])
ipercomprati = len(df[df['Stato RSI'].str.contains('Ipercomprato', na=False)])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Totale Asset Monitorati", f"{total_assets:,}")
col2.metric("Asset in Ipervenduto (RSI ≤ 30)", f"{ipervenduti}", delta_color="normal")
col3.metric("Asset in Ipercomprato (RSI ≥ 70)", f"{ipercomprati}", delta_color="inverse")
col4.metric("Mercati Coperti", f"{df['Mercato'].nunique()}")

st.markdown("---")

# 5. Sidebar per Filtri
st.sidebar.header("🔍 Filtri di Ricerca")

# Filtro Testuale (Nome o Ticker)
search_query = st.sidebar.text_input("Cerca per Ticker o Nome Asset", "").strip().upper()

# Filtro Tipo Asset
tipo_options = sorted(df['Tipo Asset'].dropna().unique().tolist())
selected_tipo = st.sidebar.multiselect("Tipo Asset", tipo_options, default=tipo_options)

# Filtro Paese
paese_options = sorted(df['Paese'].dropna().unique().tolist())
selected_paese = st.sidebar.multiselect("Paese / Area", paese_options, default=[])

# Filtro Mercato
mercato_options = sorted(df['Mercato'].dropna().unique().tolist())
selected_mercato = st.sidebar.multiselect("Mercato di Quotazione", mercato_options, default=[])

# Filtro Stato RSI
rsi_options = sorted(df['Stato RSI'].dropna().unique().tolist())
selected_rsi = st.sidebar.multiselect("Stato RSI 14", rsi_options, default=[])

# Filtro Relazione Prezzo / Medie
rel_options = sorted(df['Relazione Prezzo/Medie'].dropna().unique().tolist())
selected_rel = st.sidebar.multiselect("Relazione Prezzo / Medie", rel_options, default=[])

# Range Slider RSI
min_rsi, max_rsi = float(df['RSI 14'].min()), float(df['RSI 14'].max())
selected_rsi_range = st.sidebar.slider(
    "Valore RSI 14",
    min_value=0.0,
    max_value=100.0,
    value=(0.0, 100.0),
    step=1.0
)

# 6. Applica Filtri al DataFrame
filtered_df = df.copy()

if search_query:
    filtered_df = filtered_df[
        filtered_df['Ticker Yahoo'].astype(str).str.contains(search_query, case=False, na=False) |
        filtered_df['Simbolo eToro'].astype(str).str.contains(search_query, case=False, na=False) |
        filtered_df['Nome Asset'].astype(str).str.contains(search_query, case=False, na=False)
    ]

if selected_tipo:
    filtered_df = filtered_df[filtered_df['Tipo Asset'].isin(selected_tipo)]

if selected_paese:
    filtered_df = filtered_df[filtered_df['Paese'].isin(selected_paese)]

if selected_mercato:
    filtered_df = filtered_df[filtered_df['Mercato'].isin(selected_mercato)]

if selected_rsi:
    filtered_df = filtered_df[filtered_df['Stato RSI'].isin(selected_rsi)]

if selected_rel:
    filtered_df = filtered_df[filtered_df['Relazione Prezzo/Medie'].isin(selected_rel)]

filtered_df = filtered_df[
    (filtered_df['RSI 14'] >= selected_rsi_range[0]) & 
    (filtered_df['RSI 14'] <= selected_rsi_range[1])
]

# 7. Tabella Risultati e Ordinamento
st.subheader(f"📊 Risultati Filtrati ({len(filtered_df)} di {total_assets})")

if filtered_df.empty:
    st.warning("Nessun asset corrisponde ai criteri di filtro selezionati.")
else:
    # Selezione Colonne da Mostrare
    column_order = [
        'Ticker Yahoo', 'Simbolo eToro', 'Nome Asset', 'Tipo Asset', 'Mercato', 'Paese',
        'Prezzo ($)', 'RSI 14', 'Stato RSI', 'Relazione Prezzo/Medie', 
        'Distanza da SMA 200 (%)', 'SMA 40 ($)', 'Trend SMA 40', 'SMA 200 ($)', 'Trend SMA 200'
    ]
    
    existing_cols = [c for c in column_order if c in filtered_df.columns]
    
    st.dataframe(
        filtered_df[existing_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Prezzo ($)": st.column_config.NumberColumn(format="$ %.2f"),
            "RSI 14": st.column_config.NumberColumn(format="%.2f"),
            "SMA 40 ($)": st.column_config.NumberColumn(format="$ %.2f"),
            "SMA 200 ($)": st.column_config.NumberColumn(format="$ %.2f"),
        }
    )

    # Tasto per Scaricare i Risultati Filtrati in CSV
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Scarica Risultati Filtrati (CSV)",
        data=csv_data,
        file_name="market_data_filtered.csv",
        mime="text/csv",
    )

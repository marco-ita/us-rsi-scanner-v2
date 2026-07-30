import streamlit as st
import pandas as pd
import yfinance as yf
import requests

st.set_page_config(page_title="US Market RSI Scanner", layout="wide")

st.title("📈 Scanner RSI - Mercato Azionario USA")
st.caption("Filtra gli asset in ipercomprato o ipervenduto in tempo reale.")

@st.cache_data(ttl=14400) # Mantiene i dati in cache per 4 ore
def get_us_tickers():
    url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=0&download=true"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            rows = res.json().get('data', {}).get('rows', [])
            if rows:
                df = pd.DataFrame(rows)
                tickers = df['symbol'].dropna().astype(str).tolist()
                return [t.replace('/', '-').replace('^', '-') for t in tickers if t.isalnum() or '-' in t or '.' in t]
    except Exception:
        pass
    # Fallback sui principali ticker USA
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "NFLX", "AMD", "INTC", "BAC", "JPM", "V", "DIS"]

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=14400)
def fetch_market_rsi():
    tickers = get_us_tickers()
    chunk_size = 300
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_chunks = (len(tickers) // chunk_size) + 1

    for idx, i in enumerate(range(0, len(tickers), chunk_size)):
        chunk = tickers[i:i+chunk_size]
        status_text.text(f"Scansione mercato in corso... (Blocco {idx+1} di {total_chunks})")
        try:
            data = yf.download(chunk, period="2mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in chunk:
                try:
                    df_ticker = data if len(chunk) == 1 else data[ticker].dropna()
                    if len(df_ticker) >= 15 and 'Close' in df_ticker.columns:
                        close_prices = df_ticker['Close']
                        if isinstance(close_prices, pd.DataFrame):
                            close_prices = close_prices.iloc[:, 0]
                        
                        rsi_series = calculate_rsi(close_prices, 14)
                        if not rsi_series.empty:
                            last_rsi = float(rsi_series.iloc[-1])
                            last_price = float(close_prices.iloc[-1])
                            
                            if not (pd.isna(last_rsi) or pd.isna(last_price)):
                                status = "Neutro"
                                if last_rsi <= 30: status = "Ipervenduto (RSI ≤ 30)"
                                elif last_rsi >= 70: status = "Ipercomprato (RSI ≥ 70)"
                                
                                results.append({
                                    "Ticker": ticker,
                                    "Prezzo": round(last_price, 2),
                                    "RSI_14": round(last_rsi, 2),
                                    "Stato": status
                                })
                except Exception:
                    continue
        except Exception:
            continue
        
        progress_bar.progress(min((idx + 1) / total_chunks, 1.0))

    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results)

# Caricamento dati
with st.spinner("Connessione ai mercati in corso..."):
    df = fetch_market_rsi()

if df.empty:
    st.error("Impossibile recuperare i dati al momento. Riprova più tardi.")
else:
    # Metriche
    col1, col2, col3, col4 = st.columns(4)
    totale = len(df)
    ipervenduti = len(df[df['RSI_14'] <= 30])
    ipercomprati = len(df[df['RSI_14'] >= 70])
    
    col1.metric("Totale Asset Scansionati", totale)
    col2.metric("Ipervenduti (RSI ≤ 30)", ipervenduti)
    col3.metric("Ipercomprato (RSI ≥ 70)", ipercomprati)
    col4.metric("Neutri", totale - (ipervenduti + ipercomprati))

    st.markdown("---")

    # Filtri
    st.sidebar.header("Filtri")
    search_ticker = st.sidebar.text_input("Cerca Ticker:", "").upper()
    filtro_stato = st.sidebar.multiselect("Stato RSI:", options=df["Stato"].unique(), default=df["Stato"].unique())
    rsi_range = st.sidebar.slider("Range RSI:", 0.0, 100.0, (0.0, 100.0))

    df_filtered = df[
        (df["Stato"].isin(filtro_stato)) &
        (df["RSI_14"] >= rsi_range[0]) &
        (df["RSI_14"] <= rsi_range[1])
    ]
    
    if search_ticker:
        df_filtered = df_filtered[df_filtered["Ticker"].str.contains(search_ticker)]

    st.subheader(f"Risultati ({len(df_filtered)} asset)")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

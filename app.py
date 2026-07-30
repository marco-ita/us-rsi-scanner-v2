import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests

st.set_page_config(page_title="US Market Scanner - RSI & Calculus SMA Trend", layout="wide")

st.title("📈 Scanner USA - RSI & Trend Scientifico (Derivata Prima e Seconda)")
st.caption("Classificazione avanzata della traiettoria delle SMA (Crescita, Declino, Inizio Rimbalzo, Inizio Inversione).")

@st.cache_data(ttl=14400)
def get_us_tickers_with_names():
    url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=0&download=true"
    headers = {'User-Agent': 'Mozilla/5.0'}
    ticker_name_map = {}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            rows = res.json().get('data', {}).get('rows', [])
            if rows:
                for r in rows:
                    raw_symbol = str(r.get('symbol', '')).strip()
                    name = str(r.get('name', 'N/D')).strip()
                    if raw_symbol:
                        clean_symbol = raw_symbol.replace('/', '-').replace('^', '-')
                        if clean_symbol.isalnum() or '-' in clean_symbol or '.' in clean_symbol:
                            ticker_name_map[clean_symbol] = name
                return ticker_name_map
    except Exception:
        pass
    
    fallback = {
        "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation", "GOOGL": "Alphabet Inc.",
        "AMZN": "Amazon.com Inc.", "NVDA": "NVIDIA Corporation", "TSLA": "Tesla Inc.",
        "META": "Meta Platforms Inc.", "NFLX": "Netflix Inc.", "AMD": "Advanced Micro Devices Inc.",
        "INTC": "Intel Corporation", "BAC": "Bank of America Corp", "JPM": "JPMorgan Chase & Co.",
        "V": "Visa Inc.", "DIS": "The Walt Disney Company"
    }
    return fallback

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_derivative_trend(sma_series, window=5):
    """
    Calcola Pendenza (Derivata 1a) e Curvatura/Accelerazione (Derivata 2a) della SMA.
    """
    clean_sma = sma_series.dropna()
    if len(clean_sma) < (window + 2):
        return "N/D"
    
    # Prendiamo gli ultimi dati per il calcolo
    y = clean_sma.iloc[-(window+2):].values
    
    # Derivata Prima (Velocità / Pendenza)
    d1 = np.diff(y)
    
    # Derivata Seconda (Accelerazione / Curvatura)
    d2 = np.diff(d1)
    
    recent_slope = d1[-1] / y[-2] * 100        # Pendenza percentuale recente
    recent_accel = d2[-1] / y[-2] * 100        # Curvatura/Accelerazione recente
    
    threshold_slope = 0.05  # Tolleranza minima per considerare la media "piatta"
    
    if recent_slope > threshold_slope:
        if recent_accel < -0.01:
            return "Inizio Declino / Curva Giù ⚠️"  # Inversione Ribassista
        return "Forte Crescita 📈"
    elif recent_slope < -threshold_slope:
        if recent_accel > 0.01:
            return "Inizio Rimbalzo / Curva Su 🔄"   # Inversione Rialzista
        return "Forte Declino 📉"
    else:
        return "Zero Pendenza / Piatta ➡️"

@st.cache_data(ttl=14400)
def fetch_filtered_market():
    ticker_map = get_us_tickers_with_names()
    tickers = list(ticker_map.keys())
    chunk_size = 300
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_chunks = (len(tickers) // chunk_size) + 1

    for idx, i in enumerate(range(0, len(tickers), chunk_size)):
        chunk = tickers[i:i+chunk_size]
        status_text.text(f"Analisi Derivate SMA 40/200 ed RSI Wilder... (Blocco {idx+1} di {total_chunks})")
        try:
            data = yf.download(chunk, period="1y", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in chunk:
                try:
                    df_ticker = data if len(chunk) == 1 else data[ticker].dropna()
                    
                    if len(df_ticker) >= 205 and 'Close' in df_ticker.columns:
                        close_prices = df_ticker['Close']
                        if isinstance(close_prices, pd.DataFrame):
                            close_prices = close_prices.iloc[:, 0]
                        
                        rsi_series = calculate_rsi(close_prices, 14)
                        last_rsi = float(rsi_series.iloc[-1])
                        
                        if pd.isna(last_rsi):
                            continue
                        
                        is_oversold = last_rsi <= 30
                        is_overbought = last_rsi >= 70
                        
                        if not (is_oversold or is_overbought):
                            continue

                        # Calcolo Medie Mobili
                        sma40_series = close_prices.rolling(window=40).mean()
                        sma200_series = close_prices.rolling(window=200).mean()
                        
                        last_price = float(close_prices.iloc[-1])
                        last_sma40 = float(sma40_series.iloc[-1])
                        last_sma200 = float(sma200_series.iloc[-1])
                        
                        # Calcolo Trend via Derivata Seconda
                        trend_sma40 = calculate_derivative_trend(sma40_series)
                        trend_sma200 = calculate_derivative_trend(sma200_series)
                        
                        # Posizione Relativa
                        pos_relative = "SMA 40 sopra SMA 200 🟢" if last_sma40 > last_sma200 else "SMA 40 sotto SMA 200 🔴"
                        rsi_status = "Ipervenduto (RSI ≤ 30) 🟢" if is_oversold else "Ipercomprato (RSI ≥ 70) 🔴"
                        company_name = ticker_map.get(ticker, "N/D")

                        results.append({
                            "Ticker": ticker,
                            "Nome Asset": company_name,
                            "Prezzo ($)": round(last_price, 2),
                            "RSI 14": round(last_rsi, 2),
                            "Stato RSI": rsi_status,
                            "SMA 40 ($)": round(last_sma40, 2) if not pd.isna(last_sma40) else None,
                            "Trend SMA 40": trend_sma40,
                            "SMA 200 ($)": round(last_sma200, 2) if not pd.isna(last_sma200) else None,
                            "Trend SMA 200": trend_sma200,
                            "Posizione Medie": pos_relative
                        })
                except Exception:
                    continue
        except Exception:
            continue
        
        progress_bar.progress(min((idx + 1) / total_chunks, 1.0))

    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results)

# Caricamento Dati
with st.spinner("Calcolo derivate e scansione di mercato in corso..."):
    df = fetch_filtered_market()

if df.empty:
    st.info("Nessun asset attualmente in zona di Ipercomprato (≥70) o Ipervenduto (≤30).")
else:
    col1, col2, col3 = st.columns(3)
    totale = len(df)
    ipervenduti = len(df[df['RSI 14'] <= 30])
    ipercomprati = len(df[df['RSI 14'] >= 70])
    
    col1.metric("Totale Asset Filtrati", totale)
    col2.metric("Ipervenduto (RSI ≤ 30) 🟢", ipervenduti)
    col3.metric("Ipercomprato (RSI ≥ 70) 🔴", ipercomprati)

    st.markdown("---")

    # Filtri Laterali
    st.sidebar.header("Filtri Avanzati")
    search_query = st.sidebar.text_input("Cerca Ticker o Nome Società:", "").strip()
    filtro_rsi = st.sidebar.multiselect("Stato RSI:", options=df["Stato RSI"].unique(), default=df["Stato RSI"].unique())
    filtro_trend40 = st.sidebar.multiselect("Trend SMA 40:", options=df["Trend SMA 40"].unique(), default=df["Trend SMA 40"].unique())

    df_filtered = df[
        (df["Stato RSI"].isin(filtro_rsi)) & 
        (df["Trend SMA 40"].isin(filtro_trend40))
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
            "Trend SMA 40": st.column_config.TextColumn("Trend / Curvatura SMA 40"),
            "SMA 200 ($)": st.column_config.NumberColumn("SMA 200", format="$%.2f"),
            "Trend SMA 200": st.column_config.TextColumn("Trend / Curvatura SMA 200"),
            "Posizione Medie": st.column_config.TextColumn("Posizione Relativa"),
        },
        use_container_width=True,
        hide_index=True
    )

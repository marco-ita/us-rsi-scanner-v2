import streamlit as st
import pandas as pd
import yfinance as yf
import requests

st.set_page_config(page_title="US Market Scanner - RSI Wilder & SMA", layout="wide")

st.title("📈 Scanner USA - RSI Official Wilder & Medie Mobili")
st.caption("Estrae TUTTI gli asset con RSI ≤ 30 o RSI ≥ 70 (Calcolo coincidente con Investing.com ed eToro).")

@st.cache_data(ttl=14400)
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
    # Fallback ticker principali
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "NFLX", "AMD", "INTC", "BAC", "JPM", "V", "DIS"]

def calculate_rsi(series, period=14):
    """
    Calcola l'RSI a 14 periodi utilizzando l'Esponenziale di J. Welles Wilder (RMA/EWM).
    Formula identica a quella utilizzata da TradingView, Investing.com ed eToro.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Smoothing Esponenziale di Wilder (alpha = 1/14)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

@st.cache_data(ttl=14400)
def fetch_filtered_market():
    tickers = get_us_tickers()
    chunk_size = 300
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_chunks = (len(tickers) // chunk_size) + 1

    for idx, i in enumerate(range(0, len(tickers), chunk_size)):
        chunk = tickers[i:i+chunk_size]
        status_text.text(f"Scansione mercati e calcolo RSI Wilder + SMA 40/200... (Blocco {idx+1} di {total_chunks})")
        try:
            # Scarichiamo 1 anno di dati per permettere il corretto 'warm-up' dell'RSI e della SMA 200
            data = yf.download(chunk, period="1y", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in chunk:
                try:
                    df_ticker = data if len(chunk) == 1 else data[ticker].dropna()
                    
                    if len(df_ticker) >= 200 and 'Close' in df_ticker.columns:
                        close_prices = df_ticker['Close']
                        if isinstance(close_prices, pd.DataFrame):
                            close_prices = close_prices.iloc[:, 0]
                        
                        # Calcolo RSI con formula ufficiale Wilder
                        rsi_series = calculate_rsi(close_prices, 14)
                        last_rsi = float(rsi_series.iloc[-1])
                        
                        if pd.isna(last_rsi):
                            continue
                        
                        # FILTRO REGOLA: Prendiamo SOLO Ipervenduto (<=30) o Ipercomprato (>=70)
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
                        
                        rsi_status = "Ipervenduto (RSI ≤ 30) 🟢" if is_oversold else "Ipercomprato (RSI ≥ 70) 🔴"

                        results.append({
                            "Ticker": ticker,
                            "Prezzo ($)": round(last_price, 2),
                            "RSI 14 (Wilder)": round(last_rsi, 2),
                            "Stato RSI": rsi_status,
                            "SMA 40 ($)": round(last_sma40, 2) if not pd.isna(last_sma40) else None,
                            "SMA 200 ($)": round(last_sma200, 2) if not pd.isna(last_sma200) else None
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
with st.spinner("Connessione e scansione indicatori in corso..."):
    df = fetch_filtered_market()

if df.empty:
    st.info("Nessun asset attualmente in zona di Ipercomprato (≥70) o Ipervenduto (≤30).")
else:
    # Metriche di Riepilogo
    col1, col2, col3 = st.columns(3)
    totale = len(df)
    ipervenduti = len(df[df['RSI 14 (Wilder)'] <= 30])
    ipercomprati = len(df[df['RSI 14 (Wilder)'] >= 70])
    
    col1.metric("Totale Asset Filtrati", totale)
    col2.metric("Ipervenduto (RSI ≤ 30) 🟢", ipervenduti)
    col3.metric("Ipercomprato (RSI ≥ 70) 🔴", ipercomprati)

    st.markdown("---")

    # Filtri laterali veloci
    st.sidebar.header("Filtri")
    search_ticker = st.sidebar.text_input("Cerca Ticker:", "").upper()
    filtro_rsi = st.sidebar.multiselect("Stato RSI:", options=df["Stato RSI"].unique(), default=df["Stato RSI"].unique())

    df_filtered = df[df["Stato RSI"].isin(filtro_rsi)]
    
    if search_ticker:
        df_filtered = df_filtered[df_filtered["Ticker"].str.contains(search_ticker)]

    # Tabella Risultati
    st.subheader(f"Risultati ({len(df_filtered)} asset)")
    st.dataframe(
        df_filtered,
        column_config={
            "RSI 14 (Wilder)": st.column_config.NumberColumn("RSI (14)", format="%.2f"),
            "Prezzo ($)": st.column_config.NumberColumn("Prezzo", format="$%.2f"),
            "SMA 40 ($)": st.column_config.NumberColumn("SMA 40", format="$%.2f"),
            "SMA 200 ($)": st.column_config.NumberColumn("SMA 200", format="$%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )

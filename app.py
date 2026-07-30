import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import time

st.set_page_config(page_title="US Market Scanner - Anti-Block Engine", layout="wide")

st.title("📈 Scanner USA - RSI & Trend Calibrato")
st.caption("Engine ottimizzato compatibile con Python 3.14.")

@st.cache_data(ttl=14400)
def get_sp500_tickers_with_names():
    """
    Recupera i ticker dell'S&P 500 direttamente da Wikipedia.
    """
    ticker_name_map = {}
    try:
        url_sp500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = requests.get(url_sp500, headers=headers, timeout=10)
        tables = pd.read_html(req.text)
        df_sp = tables[0]
        for _, row in df_sp.iterrows():
            sym = str(row['Symbol']).replace('.', '-')
            name = str(row['Security'])
            ticker_name_map[sym] = name
    except Exception:
        ticker_name_map = {
            "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation", "GOOGL": "Alphabet Inc.",
            "AMZN": "Amazon.com Inc.", "NVDA": "NVIDIA Corporation", "TSLA": "Tesla Inc.",
            "META": "Meta Platforms Inc.", "NFLX": "Netflix Inc.", "AMD": "Advanced Micro Devices Inc.",
            "INTC": "Intel Corporation", "BAC": "Bank of America Corp", "JPM": "JPMorgan Chase & Co.",
            "V": "Visa Inc.", "DIS": "The Walt Disney Company", "PYPL": "PayPal Holdings Inc.",
            "PFE": "Pfizer Inc.", "NKE": "NIKE Inc.", "XOM": "Exxon Mobil Corp", "KO": "The Coca-Cola Co"
        }
    return ticker_name_map

def calculate_rsi(series, period=14):
    """ Formula ufficiale Wilder's RMA """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    avg_loss = avg_loss.replace(0, 1e-9)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_calibrated_trend(sma_series, window, slope_threshold):
    """ Calcola pendenza e derivata seconda della SMA """
    try:
        clean_sma = sma_series.dropna()
        if len(clean_sma) < (window + 2):
            return "Zero Pendenza / Piatta ➡️"
        
        y = clean_sma.iloc[-(window+2):].values
        if len(y) < 2 or y[0] == 0:
            return "Zero Pendenza / Piatta ➡️"
        
        total_change_pct = ((y[-1] - y[0]) / y[0]) * 100
        
        d1 = np.diff(y)
        accel = (np.diff(d1)[-1] / y[-2]) * 100 if len(d1) >= 2 and y[-2] != 0 else 0.0
        
        if abs(total_change_pct) < slope_threshold:
            return "Zero Pendenza / Piatta ➡️"
        
        if total_change_pct > slope_threshold:
            if accel < -0.01:
                return "Inizio Declino / Curva Giù ⚠️"
            return "Forte Crescita 📈"
        else:
            if accel > 0.01:
                return "Inizio Rimbalzo / Curva Su 🔄"
            return "Forte Declino 📉"
    except Exception:
        return "Zero Pendenza / Piatta ➡️"

@st.cache_data(ttl=14400)
def fetch_filtered_market(show_all_rsi=False):
    ticker_map = get_sp500_tickers_with_names()
    tickers = list(ticker_map.keys())
    
    chunk_size = 50
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_chunks = max(1, (len(tickers) // chunk_size) + 1)

    for idx, i in enumerate(range(0, len(tickers), chunk_size)):
        chunk = tickers[i:i+chunk_size]
        status_text.text(f"Scansione sicura in corso... Blocco {idx+1} di {total_chunks}")
        
        try:
            # threads=False risolve il crash del threading su Python 3.14 / Streamlit
            data = yf.download(
                chunk,
                period="1y",
                interval="1d",
                group_by='ticker',
                threads=False,
                progress=False
            )
            
            if not data.empty:
                for ticker in chunk:
                    try:
                        if len(chunk) == 1:
                            df_ticker = data
                        else:
                            if ticker not in data.columns.levels[0]:
                                continue
                            df_ticker = data[ticker]
                        
                        if df_ticker is None or df_ticker.empty:
                            continue
                        
                        df_ticker = df_ticker.dropna(subset=['Close'])
                        if len(df_ticker) < 200:
                            continue
                        
                        close_prices = df_ticker['Close']
                        if isinstance(close_prices, pd.DataFrame):
                            close_prices = close_prices.iloc[:, 0]
                        
                        rsi_series = calculate_rsi(close_prices, 14)
                        if rsi_series.empty:
                            continue
                            
                        last_rsi = float(rsi_series.iloc[-1])
                        if pd.isna(last_rsi):
                            continue
                        
                        is_oversold = last_rsi <= 30
                        is_overbought = last_rsi >= 70
                        
                        if not show_all_rsi and not (is_oversold or is_overbought):
                            continue

                        sma40_series = close_prices.rolling(window=40).mean()
                        sma200_series = close_prices.rolling(window=200).mean()
                        
                        last_price = float(close_prices.iloc[-1])
                        last_sma40 = float(sma40_series.dropna().iloc[-1]) if not sma40_series.dropna().empty else None
                        last_sma200 = float(sma200_series.dropna().iloc[-1]) if not sma200_series.dropna().empty else None
                        
                        if last_sma40 is None or last_sma200 is None:
                            continue

                        trend_sma40 = calculate_calibrated_trend(sma40_series, window=15, slope_threshold=0.5)
                        trend_sma200 = calculate_calibrated_trend(sma200_series, window=35, slope_threshold=1.0)
                        
                        pos_relative = "SMA 40 sopra SMA 200 🟢" if last_sma40 > last_sma200 else "SMA 40 sotto SMA 200 🔴"
                        
                        if last_rsi <= 30:
                            rsi_status = "Ipervenduto (RSI ≤ 30) 🟢"
                        elif last_rsi >= 70:
                            rsi_status = "Ipercomprato (RSI ≥ 70) 🔴"
                        else:
                            rsi_status = "Neutro / Moderato ⚪"

                        company_name = ticker_map.get(ticker, "N/D")

                        results.append({
                            "Ticker": ticker,
                            "Nome Asset": company_name,
                            "Prezzo ($)": round(last_price, 2),
                            "RSI 14": round(last_rsi, 2),
                            "Stato RSI": rsi_status,
                            "SMA 40 ($)": round(last_sma40, 2),
                            "Trend SMA 40": trend_sma40,
                            "SMA 200 ($)": round(last_sma200, 2),
                            "Trend SMA 200": trend_sma200,
                            "Posizione Medie": pos_relative
                        })
                    except Exception:
                        continue
        except Exception:
            pass
        
        progress_bar.progress(min((idx + 1) / total_chunks, 1.0))

    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results)

# Sidebar
st.sidebar.header("Opzioni di Scansione")
show_all = st.sidebar.checkbox("Mostra TUTTI i titoli S&P 500 (inclusi RSI neutri)", value=False)

# Esecuzione
df = fetch_filtered_market(show_all_rsi=show_all)

if df.empty:
    st.info("Nessun asset attualmente in zona di Ipercomprato (≥70) o Ipervenduto (≤30). Prova ad attivare la spunta 'Mostra TUTTI i titoli' nella barra laterale.")
else:
    col1, col2, col3 = st.columns(3)
    totale = len(df)
    ipervenduti = len(df[df['RSI 14'] <= 30])
    ipercomprati = len(df[df['RSI 14'] >= 70])
    
    col1.metric("Totale Asset Estratti", totale)
    col2.metric("Ipervenduto (RSI ≤ 30) 🟢", ipervenduti)
    col3.metric("Ipercomprato (RSI ≥ 70) 🔴", ipercomprati)

    st.markdown("---")

    # Filtri Laterali
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

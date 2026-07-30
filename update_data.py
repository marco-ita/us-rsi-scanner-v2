import urllib.request
import json
import pandas as pd
import yfinance as yf
import numpy as np

def calculate_smma(series, window):
    """
    Calcola la Smoothed Moving Average (SMMA / Wilder's Smoothing)
    utilizzata esattamente dai grafici di eToro e TradingView.
    """
    smma = pd.Series(index=series.index, dtype='float64')
    if len(series) < window:
        return smma
    
    # Primo valore = media aritmetica dei primi 'window' elementi
    smma.iloc[window - 1] = series.iloc[:window].mean()
    
    # Algoritmo ricorsivo di eToro
    for i in range(window, len(series)):
        smma.iloc[i] = (smma.iloc[i - 1] * (window - 1) + series.iloc[i]) / window
        
    return smma

def calculate_rsi(series, window=14):
    """Calcola l'RSI a 14 periodi."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_all_us_tickers():
    """
    Recupera l'elenco completo e dinamico dei ticker quotati sul mercato USA (NASDAQ / NYSE)
    tramite l'API ufficiale di NASDAQ Screener.
    """
    print("Download dinamico dei ticker dall'API NASDAQ...")
    url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        rows = data['data']['table']['rows']
        # Estraiamo solo i ticker azionari puliti (solo lettere, senza warrant/azioni speciali)
        tickers = [r['symbol'] for r in rows if r['symbol'].isalpha()]
        print(f"Ottenuti {len(tickers)} ticker azionari USA dall'API NASDAQ.")
        return list(set(tickers))
    except Exception as e:
        print(f"Impossibile contattare l'API NASDAQ ({e}). Utilizzo fallback su paniere S&P 500.")
        try:
            tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
            return tables[0]['Symbol'].str.replace('.', '-', regex=False).tolist()
        except Exception as e2:
            print(f"Errore anche nel fallback: {e2}")
            return ["TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX", "AMD", "INTC"]

def run_update():
    tickers = get_all_us_tickers()
    print(f"Inizio scansione mercato USA su {len(tickers)} asset...")

    results = []
    
    # Processiamo a blocchi per ottimizzare il download dei dati da Yahoo Finance
    chunk_size = 100
    ticker_chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]

    for chunk in ticker_chunks:
        try:
            data = yf.download(chunk, period="5y", interval="1d", auto_adjust=False, group_by='ticker', progress=False)

            for ticker in chunk:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if ticker not in data.columns.levels[0]:
                            continue
                        df = data[ticker].dropna().copy()
                    else:
                        df = data.dropna().copy()

                    if df.empty or len(df) < 200:
                        continue

                    close = df['Close']
                    
                    # 1. Calcolo RSI
                    rsi_series = calculate_rsi(close, 14)
                    rsi_val = rsi_series.iloc[-1]
                    
                    # FILTRO OPERATIVO: Escludiamo chi ha RSI compreso tra 30.1 e 69.9
                    if 30 < rsi_val < 70:
                        continue

                    # 2. Calcolo SMMA 40 e SMMA 200 (Formula eToro)
                    smma_40_series = calculate_smma(close, 40)
                    smma_200_series = calculate_smma(close, 200)

                    last_close = close.iloc[-1]
                    smma_40_val = smma_40_series.iloc[-1]
                    smma_200_val = smma_200_series.iloc[-1]

                    # 3. Pendenza / Trend eToro (confrontato con 5 giorni fa)
                    smma_40_prev = smma_40_series.iloc[-6]
                    smma_200_prev = smma_200_series.iloc[-6]

                    trend_40 = "In Declino 🔴" if smma_40_val < smma_40_prev else "In Crescita 🟢"
                    trend_200 = "In Declino 🔴" if smma_200_val < smma_200_prev else "In Crescita 🟢"

                    # 4. Posizione Medie eToro
                    pos_medie = "SMA 40 SOPRA SMA 200 🟢" if smma_40_val > smma_200_val else "SMA 40 SOTTO SMA 200 🔴"

                    # 5. Stato RSI
                    if rsi_val <= 30:
                        rsi_state = "Ipervenduto (RSI ≤ 30) 🟢"
                    else:
                        rsi_state = "Ipercomprato (RSI ≥ 70) 🔴"

                    results.append({
                        'Ticker': ticker,
                        'Nome Asset': ticker,
                        'Prezzo ($)': round(float(last_close), 2),
                        'RSI 14': round(float(rsi_val), 2),
                        'Stato RSI': rsi_state,
                        'SMA 40 ($)': round(float(smma_40_val), 2),
                        'Trend SMA 40': trend_40,
                        'SMA 200 ($)': round(float(smma_200_val), 2),
                        'Trend SMA 200': trend_200,
                        'Posizione Medie': pos_medie
                    })
                except Exception as e_inner:
                    continue
        except Exception as e_chunk:
            print(f"Errore nell'elaborazione del blocco: {e_chunk}")

    res_df = pd.DataFrame(results)
    res_df.to_csv('market_data.csv', index=False)
    print(f"Scansione completata con successo! Trovati {len(results)} asset in condizione estrema (RSI ≤ 30 o RSI ≥ 70).")

if __name__ == "__main__":
    run_update()

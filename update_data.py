import urllib.request
import urllib.parse
import json
import time
import random
import pandas as pd
import numpy as np
import requests
import yfinance as yf

# Lista di User-Agent reali da browser desktop (Windows / Mac / Linux)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
]

def get_browser_session():
    """
    Crea una sessione Requests configurata per simulare perfettamente un browser reale
    con cookie di sessione validi da Yahoo Finance.
    """
    session = requests.Session()
    user_agent = random.choice(USER_AGENTS)
    
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    })
    
    # Chiamata civetta alla home page di Yahoo per raccogliere i cookie iniziali
    try:
        session.get("https://finance.yahoo.com", timeout=10)
    except Exception:
        pass
        
    return session

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

# ---------------------------------------------------------
# MAPPATURA E CATALOGO ETORO GLOBALE
# ---------------------------------------------------------

def clean_and_format_symbol(symbol):
    """STEP 1: Formattazione standard dei ticker."""
    if not symbol or symbol.startswith("ETORI"):
        return None

    if ".CVR" in symbol or ".OLD" in symbol or "OLD" in symbol:
        return None

    if symbol.endswith(".US"):
        symbol = symbol[:-3]

    parts = symbol.split(".")
    if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isalpha():
        return f"{parts[0]}-{parts[1]}"

    suffix_mapping = {
        ".MI": ".MI", ".DE": ".DE", ".PA": ".PA", ".L": ".L",
        ".AS": ".AS", ".MC": ".MC", ".SW": ".SW",
        ".HK": ".HK", ".T": ".T", ".SI": ".SI", ".AX": ".AX"
    }

    for etoro_suff, yahoo_suff in suffix_mapping.items():
        if symbol.endswith(etoro_suff):
            base_symbol = symbol.replace(etoro_suff, "")
            return f"{base_symbol}{yahoo_suff}"

    return symbol

def extract_symbol_from_images(images_list):
    """STEP 2: Estrazione dello slug dall'URI avatar eToro."""
    if not images_list or not isinstance(images_list, list):
        return None
    
    for img in images_list:
        uri = img.get('Uri', '') if isinstance(img, dict) else ''
        if 'market-avatars/' in uri:
            try:
                raw_slug = uri.split('market-avatars/')[1].split('/')[0]
                if raw_slug:
                    return clean_and_format_symbol(raw_slug.upper())
            except Exception:
                continue
    return None

def get_etoro_catalog():
    """Scarica il catalogo globale eToro."""
    print("Download dinamico del catalogo globale dall'API di eToro...")
    url = "https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments"
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        instruments = data.get('InstrumentDisplayDatas', []) if isinstance(data, dict) else data
        ticker_map = {}
        
        for item in instruments:
            type_id = item.get('InstrumentTypeID')
            symbol_raw = item.get('SymbolFull') or item.get('Symbol')
            name = item.get('InstrumentDisplayName', symbol_raw)
            
            if not symbol_raw or type_id not in [5, 6]:
                continue

            clean_sym = clean_and_format_symbol(symbol_raw)
            uri_sym = extract_symbol_from_images(item.get('Images', []))

            final_ticker = clean_sym or uri_sym
            if final_ticker:
                ticker_map[final_ticker] = name

        print(f"Ottenuti {len(ticker_map)} ticker unici dal catalogo eToro.")
        return ticker_map
    except Exception as e:
        print(f"Errore nel caricamento del catalogo eToro: {e}")
        return {}

# ---------------------------------------------------------
# ESECUZIONE DELLA SCANSIONE ANTI-RATE-LIMIT
# ---------------------------------------------------------

def run_update():
    ticker_map = get_etoro_catalog()
    if not ticker_map:
        print("Nessun ticker disponibile. Interruzione.")
        return

    tickers = list(ticker_map.keys())
    print(f"Inizio scansione globale su {len(tickers)} asset con Sessione Browser simulata...")

    results = []
    
    # Dimensione del blocco ottimizzata per simulare richieste web
    chunk_size = 50
    ticker_chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]

    # Inizializziamo la prima sessione browser
    session = get_browser_session()

    for chunk_idx, chunk in enumerate(ticker_chunks, 1):
        # Ogni 10 blocchi rigeneriamo la sessione e l'User-Agent
        if chunk_idx % 10 == 0:
            session = get_browser_session()

        # Pausa randomica tra 1 e 2.5 secondi per simulare il comportamento umano
        time.sleep(random.uniform(1.0, 2.5))
        
        data = None
        for attempt in range(3):
            try:
                # Iniettiamo la nostra sessione browser mascherata dentro yfinance
                data = yf.download(
                    chunk, 
                    period="2y", 
                    interval="1d", 
                    auto_adjust=False, 
                    group_by='ticker', 
                    progress=False,
                    session=session
                )
                if data is not None and not data.empty:
                    break
            except Exception:
                # Se fallisce, rigeneriamo la sessione e aspettiamo un po'
                session = get_browser_session()
                time.sleep(3.0)

        if data is None or data.empty:
            continue

        for ticker in chunk:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if ticker not in data.columns.levels[0]:
                        continue
                    df = data[ticker].dropna(how='all').copy()
                else:
                    df = data.dropna(how='all').copy()

                close = df['Close'].dropna() if 'Close' in df else pd.Series()

                if close.empty or len(close) < 200:
                    continue

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

                asset_name = ticker_map.get(ticker, ticker)

                results.append({
                    'Ticker': ticker,
                    'Nome Asset': asset_name,
                    'Prezzo ($)': round(float(last_close), 2),
                    'RSI 14': round(float(rsi_val), 2),
                    'Stato RSI': rsi_state,
                    'SMA 40 ($)': round(float(smma_40_val), 2),
                    'Trend SMA 40': trend_40,
                    'SMA 200 ($)': round(float(smma_200_val), 2),
                    'Trend SMA 200': trend_200,
                    'Posizione Medie': pos_medie
                })
            except Exception:
                continue

    res_df = pd.DataFrame(results)
    res_df.to_csv('market_data.csv', index=False)
    print(f"Scansione completata con successo! Trovati {len(results)} asset in condizione estrema e salvati in market_data.csv.")

if __name__ == "__main__":
    run_update()

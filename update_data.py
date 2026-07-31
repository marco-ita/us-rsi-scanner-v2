import urllib.request
import urllib.parse
import json
import time
import random
import pandas as pd
import numpy as np
import requests
import yfinance as yf

# Lista di User-Agent di browser desktop reali
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15'
]

def get_browser_session():
    """
    Inizializza una sessione HTTP con cookie e header reali di Yahoo Finance.
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    try:
        session.get("https://finance.yahoo.com", timeout=10)
    except Exception:
        pass
    return session

def calculate_smma(series, window):
    """
    Calcola la Smoothed Moving Average (SMMA / Wilder's Smoothing)
    utilizzata nei grafici di eToro e TradingView.
    """
    smma = pd.Series(index=series.index, dtype='float64')
    if len(series) < window:
        return smma
    
    smma.iloc[window - 1] = series.iloc[:window].mean()
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

def clean_and_format_symbol(symbol):
    """
    Filtra rigorosamente ticker non validi, CVR, opzioni e contratti obsoleti
    che fanno fallire le chiamate e generano il Rate Limit.
    """
    if not symbol or symbol.startswith("ETORI"):
        return None

    # Scarta spazzatura anagrafica nota nei log
    bad_tokens = [".CVR", ".OLD", "OLD", "DRM.", "CA1", "CA2", "PUT", "CALL", "CVR", "DORMANT", "MERGER", "ESCROW"]
    if any(token in symbol.upper() for token in bad_tokens):
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
    """Estrae lo slug pulito dall'URI eToro."""
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
    """Scarica ed estrae il catalogo pulito da eToro."""
    print("1. Download dinamico del catalogo globale da eToro...")
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
            
            # Solo Azioni (5) ed ETF (6)
            if not symbol_raw or type_id not in [5, 6]:
                continue

            clean_sym = clean_and_format_symbol(symbol_raw)
            uri_sym = extract_symbol_from_images(item.get('Images', []))

            final_ticker = clean_sym or uri_sym
            if final_ticker:
                ticker_map[final_ticker] = name

        print(f"Ottenuti {len(ticker_map)} ticker validi e filtrati dal catalogo eToro.")
        return ticker_map
    except Exception as e:
        print(f"Errore nel caricamento del catalogo eToro: {e}")
        return {}

def run_update():
    ticker_map = get_etoro_catalog()
    if not ticker_map:
        print("Nessun ticker disponibile. Interruzione.")
        return

    tickers = list(ticker_map.keys())
    print(f"2. Inizio scansione su {len(tickers)} asset con protezione Anti-Rate-Limit Avanzata...")

    results = []
    
    # Blocco da 25 ticker per minimizzare il carico per singola richiesta
    chunk_size = 25
    ticker_chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]

    session = get_browser_session()

    for chunk_idx, chunk in enumerate(ticker_chunks, 1):
        # Rigenera la sessione ogni 15 blocchi
        if chunk_idx % 15 == 0:
            session = get_browser_session()

        # Pausa cautelativa casuale tra un blocco e l'altro
        time.sleep(random.uniform(2.0, 3.5))

        data = None
        rate_limit_hits = 0

        # Tentativi con Exponential Backoff Reale
        while rate_limit_hits < 4:
            try:
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
            except Exception as e:
                err_msg = str(e)
                if "Rate" in err_msg or "Too Many" in err_msg or "429" in err_msg:
                    rate_limit_hits += 1
                    # LETARGO ANTI-RATE-LIMIT: Aspetta 45 secondi se Yahoo invia il blocco
                    sleep_time = 45 * rate_limit_hits
                    print(f"⚠️ Rate Limit sul blocco {chunk_idx}/{len(ticker_chunks)}. Letargo di raffreddamento di {sleep_time}s...")
                    time.sleep(sleep_time)
                    session = get_browser_session() # Nuova sessione pulita
                else:
                    time.sleep(3)
                    break

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
                
                # FILTRO OPERATIVO: Mantieni solo RSI <= 30 o RSI >= 70
                if 30 < rsi_val < 70:
                    continue

                # 2. Calcolo SMMA 40 e SMMA 200
                smma_40_series = calculate_smma(close, 40)
                smma_200_series = calculate_smma(close, 200)

                last_close = close.iloc[-1]
                smma_40_val = smma_40_series.iloc[-1]
                smma_200_val = smma_200_series.iloc[-1]

                # 3. Pendenza / Trend eToro (Confronto con 5 giorni fa - Logica Originale)
                smma_40_prev = smma_40_series.iloc[-6]
                smma_200_prev = smma_200_series.iloc[-6]

                trend_40 = "In Declino 🔴" if smma_40_val < smma_40_prev else "In Crescita 🟢"
                trend_200 = "In Declino 🔴" if smma_200_val < smma_200_prev else "In Crescita 🟢"

                # 4. Posizione Medie
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
    print(f"Scansione completata! Trovati {len(results)} asset in condizione estrema e salvati in market_data.csv.")

if __name__ == "__main__":
    run_update()

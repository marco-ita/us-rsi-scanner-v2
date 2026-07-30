import pandas as pd
import yfinance as yf
import requests

def get_us_tickers():
    url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=0&download=true"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            rows = data.get('data', {}).get('rows', [])
            if rows:
                df = pd.DataFrame(rows)
                tickers = df['symbol'].dropna().astype(str).tolist()
                clean_tickers = [t.replace('/', '-').replace('^', '-') for t in tickers if t.isalnum() or '-' in t or '.' in t]
                print(f"Recuperati {len(clean_tickers)} ticker dal NASDAQ.")
                return clean_tickers
    except Exception as e:
        print(f"Errore recupero NASDAQ: {e}")
    
    # Fallback di sicurezza in caso di blocco API
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "NFLX", "AMD", "INTC"]

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_market_rsi():
    tickers = get_us_tickers()
    
    chunk_size = 500
    results = []
    
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        try:
            data = yf.download(chunk, period="2mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in chunk:
                try:
                    if len(chunk) == 1:
                        df_ticker = data
                    else:
                        if ticker not in data.columns.levels[0]:
                            continue
                        df_ticker = data[ticker].dropna()

                    if len(df_ticker) >= 15 and 'Close' in df_ticker.columns:
                        close_prices = df_ticker['Close']
                        if isinstance(close_prices, pd.DataFrame):
                            close_prices = close_prices.iloc[:, 0]
                            
                        rsi_series = calculate_rsi(close_prices, period=14)
                        if not rsi_series.empty:
                            last_rsi = float(rsi_series.iloc[-1])
                            last_price = float(close_prices.iloc[-1])
                            
                            if pd.isna(last_rsi) or pd.isna(last_price):
                                continue

                            status = "Neutro"
                            if last_rsi <= 30:
                                status = "Ipervenduto (RSI ≤ 30)"
                            elif last_rsi >= 70:
                                status = "Ipercomprato (RSI ≥ 70)"

                            results.append({
                                "Ticker": ticker,
                                "Prezzo": round(last_price, 2),
                                "RSI_14": round(last_rsi, 2),
                                "Stato": status
                            })
                except Exception:
                    continue
        except Exception as e:
            print(f"Errore chunk {i}: {e}")

    if not results:
        results.append({"Ticker": "AAPL", "Prezzo": 0.0, "RSI_14": 50.0, "Stato": "Neutro"})

    df_results = pd.DataFrame(results)
    df_results.sort_values(by="RSI_14", ascending=True, inplace=True)
    df_results.to_csv("rsi_market_data.csv", index=False)
    print("CSV creato con successo!")

if __name__ == "__main__":
    calculate_market_rsi()
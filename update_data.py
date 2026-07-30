import pandas as pd
import numpy as np
import yfinance as yf
import requests

def get_test_tickers():
    # 10 Asset di prova per testare l'automazione rapida
    return {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "GOOGL": "Alphabet Inc.",
        "AMZN": "Amazon.com Inc.",
        "NVDA": "NVIDIA Corporation",
        "TSLA": "Tesla Inc.",
        "META": "Meta Platforms Inc.",
        "NFLX": "Netflix Inc.",
        "AMD": "Advanced Micro Devices Inc.",
        "INTC": "Intel Corporation"
    }

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = avg_loss.replace(0, 1e-9)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_calibrated_trend(sma_series, window, slope_threshold):
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

def run_update():
    print("🔄 [TEST] Avvio aggiornamento rapido dati...")
    ticker_map = get_test_tickers()
    tickers = list(ticker_map.keys())
    results = []

    try:
        data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', threads=False, progress=False)
        
        for ticker in tickers:
            try:
                df_ticker = data[ticker] if ticker in data.columns.levels[0] else None
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
            except Exception as e:
                print(f"Errore su {ticker}: {e}")
                continue
    except Exception as e:
        print(f"Errore download: {e}")

    df = pd.DataFrame(results)
    df.to_csv("market_data.csv", index=False)
    print(f"✅ TEST COMPLETATO! Salvati {len(df)} asset in 'market_data.csv'.")

if __name__ == "__main__":
    run_update()

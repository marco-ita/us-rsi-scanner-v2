import yfinance as yf
import pandas as pd
import numpy as np

def calculate_smma(series, window):
    """
    Calcola la Smoothed Moving Average (SMMA / Wilder's Smoothing)
    utilizzata da eToro e TradingView.
    """
    smma = pd.Series(index=series.index, dtype='float64')
    if len(series) < window:
        return smma
    
    # Valore iniziale = media aritmetica dei primi 'window' elementi
    smma.iloc[window - 1] = series.iloc[:window].mean()
    
    # Algoritmo ricorsivo di eToro
    for i in range(window, len(series)):
        smma.iloc[i] = (smma.iloc[i - 1] * (window - 1) + series.iloc[i]) / window
        
    return smma

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def run_update():
    tickers = ["TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX", "AMD"]
    
    # Scarichiamo 5 anni di dati per avere la memoria storica completa per la SMMA di eToro
    data = yf.download(tickers, period="5y", interval="1d", auto_adjust=False, group_by='ticker', progress=False)

    results = []

    for ticker in tickers:
        try:
            df = data[ticker].dropna().copy()
            if df.empty:
                continue

            close = df['Close']
            
            # 1. Calcolo Medie Standard (SMA)
            df['SMA_40_Std'] = close.rolling(window=40).mean()
            df['SMA_200_Std'] = close.rolling(window=200).mean()
            
            # 2. Calcolo Medie eToro (SMMA / Smoothed)
            df['SMMA_40_eToro'] = calculate_smma(close, 40)
            df['SMMA_200_eToro'] = calculate_smma(close, 200)

            # 3. Calcolo RSI
            df['RSI'] = calculate_rsi(close, 14)

            # Estrazione ultimi valori
            last_close = close.iloc[-1]
            rsi_val = df['RSI'].iloc[-1]
            
            sma_40_std = df['SMA_40_Std'].iloc[-1]
            sma_200_std = df['SMA_200_Std'].iloc[-1]
            
            smma_40_etoro = df['SMMA_40_eToro'].iloc[-1]
            smma_200_etoro = df['SMMA_200_eToro'].iloc[-1]

            # Pendenza eToro (confrontata con 5 giorni fa)
            smma_40_prev = df['SMMA_40_eToro'].iloc[-6]
            smma_200_prev = df['SMMA_200_eToro'].iloc[-6]

            trend_40 = "In Declino 🔴" if smma_40_etoro < smma_40_prev else "In Crescita 🟢"
            trend_200 = "In Declino 🔴" if smma_200_etoro < smma_200_prev else "In Crescita 🟢"

            # Posizione Medie eToro
            pos_medie = "SMMA 40 SOPRA SMMA 200 🟢" if smma_40_etoro > smma_200_etoro else "SMMA 40 SOTTO SMMA 200 🔴"

            # Stato RSI
            if rsi_val <= 30:
                rsi_state = "Ipervenduto (RSI ≤ 30) 🟢"
            elif rsi_val >= 70:
                rsi_state = "Ipercomprato (RSI ≥ 70) 🔴"
            else:
                rsi_state = "Neutro ⚪"

            results.append({
                'Ticker': ticker,
                'Nome Asset': ticker,
                'Prezzo ($)': round(last_close, 2),
                'RSI 14': round(rsi_val, 2),
                'Stato RSI': rsi_state,
                'SMA 40 Standard ($)': round(sma_40_std, 2),
                'SMMA 40 eToro ($)': round(smma_40_etoro, 2),
                'Trend 40 eToro': trend_40,
                'SMA 200 Standard ($)': round(sma_200_std, 2),
                'SMMA 200 eToro ($)': round(smma_200_etoro, 2),
                'Trend 200 eToro': trend_200,
                'Posizione Medie eToro': pos_medie
            })
        except Exception as e:
            print(f"Errore su {ticker}: {e}")

    res_df = pd.DataFrame(results)
    res_df.to_csv('market_data.csv', index=False)
    print("market_data.csv aggiornato con tutte le colonne affiancate!")

if __name__ == "__main__":
    run_update()


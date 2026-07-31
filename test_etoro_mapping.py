import urllib.request
import json
import yfinance as yf
import pandas as pd

def test_etoro_to_yahoo():
    url = "https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print("1. Scarico metadati da eToro API...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"Errore nella chiamata all'API eToro: {e}")
        return

    instruments = data.get('InstrumentDisplayDatas', []) if isinstance(data, dict) else data
    print(f"Trovati {len(instruments)} strumenti totali nel JSON di eToro.\n")

    # Prendiamo un campione di test significativo (es. primi 30 strumenti)
    sample = instruments[:30]
    
    success = 0
    failed = 0

    print("2. Verifica compatibilità con Yahoo Finance:")
    print("-" * 60)

    for item in sample:
        # Estrazione dati dal JSON di eToro
        symbol = item.get('SymbolFull') or item.get('Symbol') or item.get('InstrumentDisplayName')
        name = item.get('InstrumentDisplayName', 'Sconosciuto')
        
        if not symbol:
            continue

        # Tentativo di estrazione dati da Yahoo Finance
        try:
            ticker_data = yf.Ticker(symbol)
            hist = ticker_data.history(period="5d")
            
            if not hist.empty:
                print(f"🟢 OK: eToro '{symbol}' ({name}) -> Trovato su Yahoo Finance! Prezzo: {round(hist['Close'].iloc[-1], 2)}$")
                success += 1
            else:
                print(f"🔴 FALLITO: eToro '{symbol}' ({name}) -> Nessun dato restituito da Yahoo Finance")
                failed += 1
        except Exception as e:
            print(f"🔴 ERRORE: eToro '{symbol}' ({name}) -> Errore: {e}")
            failed += 1

    print("-" * 60)
    print(f"Riepilogo Test: {success} trovati con successo, {failed} falliti su un campione di {len(sample)}.")

if __name__ == "__main__":
    test_etoro_to_yahoo()

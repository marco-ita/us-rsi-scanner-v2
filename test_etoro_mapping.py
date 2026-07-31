import urllib.request
import json
import yfinance as yf

def test_etoro_to_yahoo():
    url = "https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Chrome/120.0.0.0)'
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
    print(f"Trovati {len(instruments)} strumenti totali nel JSON di eToro.")

    # FILTRO FONDAMENTALE: Selezioniamo SOLO Azioni e ETF
    # Su eToro: InstrumentTypeID 5 = Stocks, 6 = ETF (o controlliamo l'oggetto)
    stocks_and_etfs = []
    for item in instruments:
        # Verifichiamo se è Azione o ETF tramite ID tipo o descrizione
        type_id = item.get('InstrumentTypeID')
        if type_id in [5, 6] or item.get('InstrumentType') in ['Stocks', 'ETFs']:
            stocks_and_etfs.append(item)

    print(f"Filtrati con successo {len(stocks_and_etfs)} tra Azioni ed ETF mondiali!\n")

    # Prendiamo un campione significativo di 30 vere AZIONI / ETF
    sample = stocks_and_etfs[:30]
    
    success = 0
    failed = 0

    print("2. Verifica compatibilità Azioni/ETF con Yahoo Finance:")
    print("-" * 60)

    for item in sample:
        symbol = item.get('SymbolFull') or item.get('Symbol')
        name = item.get('InstrumentDisplayName', 'Sconosciuto')
        
        if not symbol:
            continue

        try:
            ticker_data = yf.Ticker(symbol)
            hist = ticker_data.history(period="5d")
            
            if not hist.empty:
                print(f"🟢 OK: eToro '{symbol}' ({name}) -> Trovato! Prezzo: {round(hist['Close'].iloc[-1], 2)}$")
                success += 1
            else:
                print(f"🔴 FALLITO: eToro '{symbol}' ({name}) -> Nessun dato su Yahoo")
                failed += 1
        except Exception as e:
            print(f"🔴 ERRORE: eToro '{symbol}' ({name}) -> {e}")
            failed += 1

    print("-" * 60)
    print(f"Riepilogo Test: {success} trovati con successo, {failed} falliti su un campione di {len(sample)} Azioni/ETF.")

if __name__ == "__main__":
    test_etoro_to_yahoo()

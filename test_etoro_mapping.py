import urllib.request
import json
import yfinance as yf

def clean_and_map_symbol(symbol, exchange_id=None):
    """
    Pulisce e mappa il simbolo eToro nel formato standard riconosciuto da Yahoo Finance.
    """
    if not symbol or symbol.startswith("ETORI"):
        return None  # Scarta gli Smart Portfolios interni

    # 1. Rimuove il suffisso .US dai titoli americani
    if symbol.endswith(".US"):
        symbol = symbol[:-3]

    # 2. Mappatura dei suffissi per borse internazionali / europee
    # Se il simbolo contiene già un punto seguito dal paese eToro, applichiamo la conversione Yahoo
    suffix_mapping = {
        ".MI": ".MI",  # Borsa Italiana (Milano)
        ".DE": ".DE",  # Xetra (Germania)
        ".PA": ".PA",  # Euronext Parigi
        ".L":  ".L",   # London Stock Exchange
        ".AS": ".AS",  # Euronext Amsterdam
        ".MC": ".MC",  # Bolsa de Madrid
        ".SW": ".SW",  # SIX Swiss Exchange
        ".HK": ".HK",  # Hong Kong
        ".T":  ".T"    # Tokyo
    }

    for etoro_suff, yahoo_suff in suffix_mapping.items():
        if symbol.endswith(etoro_suff):
            base_symbol = symbol.replace(etoro_suff, "")
            return f"{base_symbol}{yahoo_suff}"

    return symbol

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

    # Filtriamo Azioni (TypeID 5) ed ETF (TypeID 6)
    usa_assets = []
    intl_assets = []
    etf_assets = []

    for item in instruments:
        type_id = item.get('InstrumentTypeID')
        symbol_raw = item.get('SymbolFull') or item.get('Symbol')
        
        if not symbol_raw or type_id not in [5, 6]:
            continue

        clean_sym = clean_and_map_symbol(symbol_raw)
        if not clean_sym:
            continue

        item_data = {
            'raw_symbol': symbol_raw,
            'clean_symbol': clean_sym,
            'name': item.get('InstrumentDisplayName', 'Sconosciuto'),
            'type': 'ETF' if type_id == 6 else 'Stock'
        }

        # Catalogazione per creare un campione bilanciato
        if type_id == 6:
            etf_assets.append(item_data)
        elif "." in clean_sym:
            intl_assets.append(item_data)
        else:
            usa_assets.append(item_data)

    print(f"Catalogati: {len(usa_assets)} Azioni USA, {len(intl_assets)} Azioni Internazionali, {len(etf_assets)} ETF.\n")

    # Creiamo un campione di test bilanciato: 10 USA, 15 Internazionali, 10 ETF
    sample = usa_assets[:10] + intl_assets[:15] + etf_assets[:10]
    
    success = 0
    failed = 0

    print("2. Verifica compatibilità bilanciata con Yahoo Finance:")
    print("=" * 70)

    for item in sample:
        sym = item['clean_symbol']
        raw_sym = item['raw_symbol']
        name = item['name']
        asset_type = item['type']

        try:
            ticker_data = yf.Ticker(sym)
            hist = ticker_data.history(period="5d")
            
            if not hist.empty:
                last_price = round(float(hist['Close'].iloc[-1]), 2)
                print(f"🟢 OK [{asset_type}]: eToro '{raw_sym}' -> Yahoo '{sym}' ({name}) | Prezzo: {last_price}")
                success += 1
            else:
                print(f"🔴 FALLITO [{asset_type}]: eToro '{raw_sym}' -> Yahoo '{sym}' ({name}) | Nessun dato")
                failed += 1
        except Exception as e:
            print(f"🔴 ERRORE [{asset_type}]: eToro '{raw_sym}' -> Yahoo '{sym}' ({name}) | {e}")
            failed += 1

    print("=" * 70)
    print(f"Riepilogo Test Globale: {success} trovati con successo, {failed} falliti su {len(sample)} testati.")

if __name__ == "__main__":
    test_etoro_to_yahoo()

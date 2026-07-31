import urllib.request
import json
import time
import yfinance as yf

def clean_and_format_symbol(symbol):
    """
    Pulisce e converte i ticker eToro nel formato esatto di Yahoo Finance.
    """
    if not symbol or symbol.startswith("ETORI"):
        return None

    # Scartiamo CVR (diritti) e vecchi ticker (.OLD)
    if ".CVR" in symbol or ".OLD" in symbol:
        return None

    # 1. Gestione titoli USA con suffisso .US
    if symbol.endswith(".US"):
        symbol = symbol[:-3]

    # 2. Conversione fondamentale per classi azionarie USA (es. BRK.B -> BRK-B)
    # Se il punto è seguito da una sola lettera (es. .A, .B), Yahoo usa il trattino
    parts = symbol.split(".")
    if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isalpha():
        return f"{parts[0]}-{parts[1]}"

    # 3. Mappatura borse internazionali
    suffix_mapping = {
        ".MI": ".MI",  # Milano
        ".DE": ".DE",  # Xetra
        ".PA": ".PA",  # Parigi
        ".L":  ".L",   # Londra
        ".AS": ".AS",  # Amsterdam
        ".MC": ".MC",  # Madrid
        ".SW": ".SW"   # Svizzera
    }

    for etoro_suff, yahoo_suff in suffix_mapping.items():
        if symbol.endswith(etoro_suff):
            base_symbol = symbol.replace(etoro_suff, "")
            return f"{base_symbol}{yahoo_suff}"

    return symbol

def search_yahoo_by_name(company_name):
    """
    Ricerca intelligente: Se il ticker fallisce, cerca il nome della società su Yahoo Finance.
    """
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(company_name)}&quotesCount=1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        quotes = data.get('quotes', [])
        if quotes:
            return quotes[0].get('symbol')
    except Exception:
        pass
    return None

def test_etoro_to_yahoo():
    url = "https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print("1. Scarico metadati da eToro API...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"Errore API eToro: {e}")
        return

    instruments = data.get('InstrumentDisplayDatas', []) if isinstance(data, dict) else data

    # Selezioniamo Azioni ed ETF
    test_list = []
    for item in instruments:
        type_id = item.get('InstrumentTypeID')
        symbol_raw = item.get('SymbolFull') or item.get('Symbol')
        
        if not symbol_raw or type_id not in [5, 6]:
            continue

        clean_sym = clean_and_format_symbol(symbol_raw)
        if not clean_sym:
            continue

        test_list.append({
            'raw_symbol': symbol_raw,
            'clean_symbol': clean_sym,
            'name': item.get('InstrumentDisplayName', ''),
            'type': 'ETF' if type_id == 6 else 'Stock'
        })

    # Campione mirato inclusivo di Berkshire Hathaway (BRK.B)
    sample = [t for t in test_list if "BRK" in t['raw_symbol'] or "BERKSHIRE" in t['name'].upper()]
    # Integriamo con altri titoli vari per il test
    sample += test_list[:25]
    
    print(f"2. Avvio Test su {len(sample)} asset (incluso Berkshire Hathaway)...")
    print("=" * 75)

    success = 0
    failed = 0

    for item in sample:
        sym = item['clean_symbol']
        raw_sym = item['raw_symbol']
        name = item['name']

        # Pausa di 0.2s per evitare il rate-limiting di Yahoo
        time.sleep(0.2)

        try:
            ticker_data = yf.Ticker(sym)
            hist = ticker_data.history(period="5d")
            
            if not hist.empty:
                last_price = round(float(hist['Close'].iloc[-1]), 2)
                print(f"🟢 OK: eToro '{raw_sym}' -> Yahoo '{sym}' ({name}) | Prezzo: {last_price}$")
                success += 1
            else:
                # Tentativo di Ricerca Intelligente per Nome se il ticker diretto fallisce
                fallback_sym = search_yahoo_by_name(name)
                if fallback_sym:
                    hist_fb = yf.Ticker(fallback_sym).history(period="5d")
                    if not hist_fb.empty:
                        last_price = round(float(hist_fb['Close'].iloc[-1]), 2)
                        print(f"🟡 RECUPERATO con Ricerca Intelligente! '{name}' -> Yahoo '{fallback_sym}' | Prezzo: {last_price}$")
                        success += 1
                        continue

                print(f"🔴 FALLITO: eToro '{raw_sym}' -> Yahoo '{sym}' ({name})")
                failed += 1
        except Exception as e:
            print(f"🔴 ERRORE: eToro '{raw_sym}' -> {e}")
            failed += 1

    print("=" * 75)
    print(f"Riepilogo Test: {success} trovati, {failed} falliti su {len(sample)} testati.")

if __name__ == "__main__":
    test_etoro_to_yahoo()

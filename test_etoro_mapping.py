import urllib.request
import json
import time
import yfinance as yf

def clean_and_format_symbol(symbol):
    if not symbol or symbol.startswith("ETORI"):
        return None

    if ".CVR" in symbol or ".OLD" in symbol or "OLD" in symbol:
        return None

    # 1. Rimozione .US dai titoli USA
    if symbol.endswith(".US"):
        symbol = symbol[:-3]

    # 2. Classi azionarie USA (es. BRK.B -> BRK-B)
    parts = symbol.split(".")
    if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isalpha():
        return f"{parts[0]}-{parts[1]}"

    # 3. Mappatura borse internazionali ed ASIATICHE
    suffix_mapping = {
        # Europa
        ".MI": ".MI",  # Milano
        ".DE": ".DE",  # Xetra (Germania)
        ".PA": ".PA",  # Parigi
        ".L":  ".L",   # Londra
        ".AS": ".AS",  # Amsterdam
        ".MC": ".MC",  # Madrid
        ".SW": ".SW",  # Svizzera
        
        # Asia & Pacifico
        ".HK": ".HK",  # Hong Kong
        ".T":  ".T",   # Tokyo (Giappone)
        ".SI": ".SI",  # Singapore
        ".AX": ".AX"   # Australia
    }

    for etoro_suff, yahoo_suff in suffix_mapping.items():
        if symbol.endswith(etoro_suff):
            base_symbol = symbol.replace(etoro_suff, "")
            return f"{base_symbol}{yahoo_suff}"

    return symbol

def search_yahoo_by_name(company_name):
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

    usa_stocks = []
    europe_stocks = []
    asia_stocks = []
    etfs = []

    asia_suffixes = [".HK", ".T", ".SI", ".AX"]

    for item in instruments:
        type_id = item.get('InstrumentTypeID')
        symbol_raw = item.get('SymbolFull') or item.get('Symbol')
        
        if not symbol_raw or type_id not in [5, 6]:
            continue

        clean_sym = clean_and_format_symbol(symbol_raw)
        if not clean_sym:
            continue

        asset_info = {
            'raw_symbol': symbol_raw,
            'clean_symbol': clean_sym,
            'name': item.get('InstrumentDisplayName', ''),
            'type': 'ETF' if type_id == 6 else 'Stock'
        }

        # Catalogazione mirata per garantire test bilanciato
        if type_id == 6:
            etfs.append(asset_info)
        elif any(clean_sym.endswith(s) for s in asia_suffixes):
            asia_stocks.append(asset_info)
        elif "." in clean_sym:
            europe_stocks.append(asset_info)
        else:
            usa_stocks.append(asset_info)

    print(f"Trovati su eToro: {len(usa_stocks)} Azioni USA, {len(europe_stocks)} Azioni Europee, {len(asia_stocks)} Azioni Asiatiche, {len(etfs)} ETF.")

    # ESTRAGGIAMO UN MIX COMPLETO: 10 USA, 10 Europee, 10 Asiatiche, 10 ETF
    sample = usa_stocks[:10] + europe_stocks[:10] + asia_stocks[:10] + etfs[:10]
    
    print(f"\n2. Avvio Test Globale su {len(sample)} asset (USA + Europa + ASIA + ETF)...")
    print("=" * 85)

    success = 0
    failed = 0

    for item in sample:
        sym = item['clean_symbol']
        raw_sym = item['raw_symbol']
        name = item['name']
        asset_type = item['type']

        time.sleep(0.2)

        try:
            ticker_data = yf.Ticker(sym)
            hist = ticker_data.history(period="5d")
            
            if not hist.empty:
                last_price = round(float(hist['Close'].iloc[-1]), 2)
                print(f"🟢 OK [{asset_type}]: eToro '{raw_sym}' -> Yahoo '{sym}' ({name}) | Prezzo: {last_price}")
                success += 1
            else:
                fallback_sym = search_yahoo_by_name(name)
                if fallback_sym:
                    hist_fb = yf.Ticker(fallback_sym).history(period="5d")
                    if not hist_fb.empty:
                        last_price = round(float(hist_fb['Close'].iloc[-1]), 2)
                        print(f"🟡 RECUPERATO INTELIGENTE [{asset_type}]: '{name}' -> Yahoo '{fallback_sym}' | Prezzo: {last_price}")
                        success += 1
                        continue

                print(f"🔴 FALLITO [{asset_type}]: eToro '{raw_sym}' -> Yahoo '{sym}' ({name})")
                failed += 1
        except Exception as e:
            print(f"🔴 ERRORE [{asset_type}]: eToro '{raw_sym}' -> {e}")
            failed += 1

    print("=" * 85)
    print(f"Riepilogo Test Mondiale: {success} trovati, {failed} falliti su {len(sample)} testati.")

if __name__ == "__main__":
    test_etoro_to_yahoo()

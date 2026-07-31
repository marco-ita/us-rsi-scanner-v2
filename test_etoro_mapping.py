import urllib.request
import urllib.parse
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

    # 3. Mappatura borse internazionali
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
    """
    IDEA MARCO (LIVELLO 2): Estrae lo slug reale del ticker direttamente dalle URI delle immagini eToro.
    Es. da '.../market-avatars/lin.de/50x50.png' estrae 'LIN.DE'.
    """
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

def search_yahoo_by_name(company_name):
    """
    LIVELLO 3: Fallback finale su Yahoo pulendo i suffissi legali.
    """
    if not company_name:
        return None

    clean_name = company_name
    legal_suffixes = ["Aktiengesellschaft", "AG", "Inc.", "Inc", "Corp.", "Corporation", "S.p.A.", "PLC", "Group", "Ltd", "NV", "SA"]
    for suffix in legal_suffixes:
        clean_name = clean_name.replace(suffix, "").strip()

    try:
        keywords = clean_name.split()[0] if clean_name.split() else company_name
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(keywords)}&quotesCount=1"
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
    
    print("1. Scarico metadati dal database eToro...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"Errore API eToro: {e}")
        return

    instruments = data.get('InstrumentDisplayDatas', []) if isinstance(data, dict) else data

    usa_stocks, europe_stocks, asia_stocks, etfs = [], [], [], []
    asia_suffixes = [".HK", ".T", ".SI", ".AX"]

    for item in instruments:
        type_id = item.get('InstrumentTypeID')
        symbol_raw = item.get('SymbolFull') or item.get('Symbol')
        
        if not symbol_raw or type_id not in [5, 6]:
            continue

        clean_sym = clean_and_format_symbol(symbol_raw)
        uri_sym = extract_symbol_from_images(item.get('Images', []))

        asset_info = {
            'raw_symbol': symbol_raw,
            'clean_symbol': clean_sym,
            'uri_symbol': uri_sym,
            'name': item.get('InstrumentDisplayName', ''),
            'type': 'ETF' if type_id == 6 else 'Stock'
        }

        if type_id == 6:
            etfs.append(asset_info)
        elif clean_sym and any(clean_sym.endswith(s) for s in asia_suffixes):
            asia_stocks.append(asset_info)
        elif clean_sym and "." in clean_sym:
            europe_stocks.append(asset_info)
        else:
            usa_stocks.append(asset_info)

    sample = usa_stocks[:8] + europe_stocks[:12] + asia_stocks[:8] + etfs[:8]
    
    print(f"\n2. Avvio Test con Architettura a 3 Livelli su {len(sample)} asset...")
    print("=" * 85)

    success, failed = 0, 0

    for item in sample:
        sym = item['clean_symbol']
        uri_sym = item['uri_symbol']
        raw_sym = item['raw_symbol']
        name = item['name']
        asset_type = item['type']

        time.sleep(0.15)

        # STEP 1: Tentativo con il SymbolFull formattato
        try:
            if sym:
                hist = yf.Ticker(sym).history(period="5d")
                if not hist.empty:
                    last_price = round(float(hist['Close'].iloc[-1]), 2)
                    print(f"🟢 OK (Step 1 Simbolo): eToro '{raw_sym}' -> Yahoo '{sym}' ({name}) | Prezzo: {last_price}")
                    success += 1
                    continue

            # STEP 2 (IDEA MARCO): Tentativo con lo Slug estratto dalla URI delle immagini!
            if uri_sym and uri_sym != sym:
                hist_uri = yf.Ticker(uri_sym).history(period="5d")
                if not hist_uri.empty:
                    last_price = round(float(hist_uri['Close'].iloc[-1]), 2)
                    print(f"🔵 RECUPERATO da URI Avatar (Step 2): eToro '{raw_sym}' -> Trovato da URI '{uri_sym}' ({name}) | Prezzo: {last_price}")
                    success += 1
                    continue

            # STEP 3: Fallback finale per Nome
            fallback_sym = search_yahoo_by_name(name)
            if fallback_sym:
                hist_fb = yf.Ticker(fallback_sym).history(period="5d")
                if not hist_fb.empty:
                    last_price = round(float(hist_fb['Close'].iloc[-1]), 2)
                    print(f"🟡 RECUPERATO da Nome (Step 3): '{name}' -> Yahoo '{fallback_sym}' | Prezzo: {last_price}")
                    success += 1
                    continue

            print(f"🔴 FALLITO: eToro '{raw_sym}' -> Yahoo '{sym}' ({name})")
            failed += 1

        except Exception as e:
            print(f"🔴 ERRORE: eToro '{raw_sym}' -> {e}")
            failed += 1

    print("=" * 85)
    print(f"Riepilogo Test Mondiale: {success} trovati, {failed} falliti su {len(sample)} testati.")

if __name__ == "__main__":
    test_etoro_to_yahoo()

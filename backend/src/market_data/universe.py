"""Fixed background basket; keep the original financial/news project scope separate."""
BACKGROUND_SYMBOLS=tuple('ACB BID BSR CTG FPT GAS GVR HDB HPG LPB MBB MCH MSN MWG SAB SHB SSB SSI STB TCB TCX VCB VHM VIB VIC VJC VNM VPB VPL VRE'.split())
UNIVERSE_SOURCE='https://ssiam.com.vn/quy-etf-ssiam-vn30?nav_page=2'
UNIVERSE_OBSERVED_AT='2026-11-05'

def resolve_background(rows):
    mapping={}
    for row in rows:
        symbol=row['symbol']
        if symbol not in BACKGROUND_SYMBOLS:continue
        if symbol in mapping or row['exchange']!='HOSE':
            raise ValueError('Ambiguous background company mapping')
        mapping[symbol]=row['exchange']
    return mapping,sorted(set(BACKGROUND_SYMBOLS)-mapping.keys())

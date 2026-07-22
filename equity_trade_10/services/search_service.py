"""Search service for NSE/BSE stocks.

Provides company name ↔ symbol mapping and search by name, symbol, or sector.
Derives its stock list from Config.DEFAULT_SYMBOLS, ensuring consistency with
the rest of the application.
"""

from __future__ import annotations

import re
from typing import Any

from config import Config


def _normalize_company(symbol: str) -> str:
    """Mirrors normalize_company from live_universe.py."""
    return str(symbol or "").strip().upper().split(".")[0]


def _build_stock_universe() -> list[dict[str, Any]]:
    """Parse Config.DEFAULT_SYMBOLS into a clean list of stock entries.

    Each entry has: symbol (str), name (str), sector (str), exchange (str).
    """
    stocks: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()

    # ── hand‑curated symbol → display-name overrides ──────────────────────
    KNOWN_NAMES: dict[str, str] = {
        "RELIANCE": "Reliance Industries Ltd",
        "TCS": "Tata Consultancy Services Ltd",
        "INFY": "Infosys Ltd",
        "HDFCBANK": "HDFC Bank Ltd",
        "ICICIBANK": "ICICI Bank Ltd",
        "SBIN": "State Bank of India",
        "ITC": "ITC Ltd",
        "LT": "Larsen & Toubro Ltd",
        "MARUTI": "Maruti Suzuki India Ltd",
        "TATAMOTORS": "Tata Motors Ltd",
        "AXISBANK": "Axis Bank Ltd",
        "BHARTIARTL": "Bharti Airtel Ltd",
        "ASIANPAINT": "Asian Paints Ltd",
        "SUNPHARMA": "Sun Pharmaceutical Industries Ltd",
        "WIPRO": "Wipro Ltd",
        "HCLTECH": "HCL Technologies Ltd",
        "BAJFINANCE": "Bajaj Finance Ltd",
        "HINDUNILVR": "Hindustan Unilever Ltd",
        "LICI": "Life Insurance Corporation of India",
        "M&M": "Mahindra & Mahindra Ltd",
        "KOTAKBANK": "Kotak Mahindra Bank Ltd",
        "TITAN": "Titan Company Ltd",
        "NTPC": "NTPC Ltd",
        "ULTRACEMCO": "UltraTech Cement Ltd",
        "ADANIPORTS": "Adani Ports and SEZ Ltd",
        "ONGC": "Oil and Natural Gas Corporation Ltd",
        "ADANIPOWER": "Adani Power Ltd",
        "BEL": "Bharat Electronics Ltd",
        "BAJAJFINSV": "Bajaj Finserv Ltd",
        "JSWSTEEL": "JSW Steel Ltd",
        "HAL": "Hindustan Aeronautics Ltd",
        "ADANIENT": "Adani Enterprises Ltd",
        "BAJAJ-AUTO": "Bajaj Auto Ltd",
        "POWERGRID": "Power Grid Corporation of India Ltd",
        "COALINDIA": "Coal India Ltd",
        "DMART": "Avenue Supermarts Ltd",
        "NESTLEIND": "Nestlé India Ltd",
        "TATASTEEL": "Tata Steel Ltd",
        "VEDL": "Vedanta Ltd",
        "IOC": "Indian Oil Corporation Ltd",
        "HINDALCO": "Hindalco Industries Ltd",
        "EICHERMOT": "Eicher Motors Ltd",
        "SBILIFE": "SBI Life Insurance Company Ltd",
        "SHRIRAMFIN": "Shriram Finance Ltd",
        "GRASIM": "Grasim Industries Ltd",
        "INDIGO": "InterGlobe Aviation Ltd",
        "TVSMOTOR": "TVS Motor Company Ltd",
        "ADANIGREEN": "Adani Green Energy Ltd",
        "DIVISLAB": "Divi's Laboratories Ltd",
        "JIOFIN": "Jio Financial Services Ltd",
        "VBL": "Varun Beverages Ltd",
        "DLF": "DLF Ltd",
        "TECHM": "Tech Mahindra Ltd",
        "BANKBARODA": "Bank of Baroda",
        "HDFCLIFE": "HDFC Life Insurance Company Ltd",
        "BPCL": "Bharat Petroleum Corporation Ltd",
        "PIDILITIND": "Pidilite Industries Ltd",
        "MUTHOOTFIN": "Muthoot Finance Ltd",
        "TRENT": "Trent Ltd",
        "IRFC": "Indian Railway Finance Corporation Ltd",
        "BRITANNIA": "Britannia Industries Ltd",
        "TORNTPHARM": "Torrent Pharmaceuticals Ltd",
        "CHOLAFIN": "Cholamandalam Investment and Finance Company Ltd",
        "PNB": "Punjab National Bank",
        "PFC": "Power Finance Corporation Ltd",
        "UNIONBANK": "Union Bank of India",
        "CANBK": "Canara Bank",
        "TATAPOWER": "Tata Power Company Ltd",
        "AMBUJACEM": "Ambuja Cements Ltd",
        "SIEMENS": "Siemens Ltd",
        "IDEA": "Vodafone Idea Ltd",
        "INDIANB": "Indian Bank",
        "JINDALSTEL": "Jindal Steel & Power Ltd",
        "GODREJCP": "Godrej Consumer Products Ltd",
        "TATACONSUM": "Tata Consumer Products Ltd",
        "INDUSTOWER": "Indus Towers Ltd",
        "HDFCAMC": "HDFC Asset Management Company Ltd",
        "CGPOWER": "CG Power and Industrial Solutions Ltd",
        "CIPLA": "Cipla Ltd",
        "HEROMOTOCO": "Hero MotoCorp Ltd",
        "APOLLOHOSP": "Apollo Hospitals Enterprise Ltd",
        "GAIL": "GAIL (India) Ltd",
        "DRREDDY": "Dr. Reddy's Laboratories Ltd",
        "BOSCHLTD": "Bosch Ltd",
        "ASHOKLEY": "Ashok Leyland Ltd",
        "BHEL": "Bharat Heavy Electricals Ltd",
        "LUPIN": "Lupin Ltd",
        "MARICO": "Marico Ltd",
        "MAZDOCK": "Mazagon Dock Shipbuilders Ltd",
        "UNITDSPR": "United Spirits Ltd",
        "IDBI": "IDBI Bank Ltd",
        "INDHOTEL": "The Indian Hotels Company Ltd",
        "ICICIGI": "ICICI Lombard General Insurance Company Ltd",
        "ZYDUSLIFE": "Zydus Lifesciences Ltd",
        "RECLTD": "REC Ltd",
        "SHREECEM": "Shree Cement Ltd",
        "MANKIND": "Mankind Pharma Ltd",
        "ABCAPITAL": "Aditya Birla Capital Ltd",
        "HINDPETRO": "Hindustan Petroleum Corporation Ltd",
        "JSWENERGY": "JSW Energy Ltd",
        "PERSISTENT": "Persistent Systems Ltd",
        "ICICIPRULI": "ICICI Prudential Life Insurance Company Ltd",
        "DABUR": "Dabur India Ltd",
        "HAVELLS": "Havells India Ltd",
        "SRF": "SRF Ltd",
        "BHARATFORG": "Bharat Forge Ltd",
        "NHPC": "NHPC Ltd",
        "PAYTM": "One97 Communications Ltd",
        "OIL": "Oil India Ltd",
        "AUROPHARMA": "Aurobindo Pharma Ltd",
        "NYKAA": "FSN E-Commerce Ventures Ltd",
        "NAUKRI": "Info Edge (India) Ltd",
        "AUBANK": "AU Small Finance Bank Ltd",
        "NMDC": "NMDC Ltd",
        "TORNTPOWER": "Torrent Power Ltd",
        "LTF": "L&T Finance Ltd",
        "SBICARD": "SBI Cards and Payment Services Ltd",
        "DIXON": "Dixon Technologies (India) Ltd",
        "INDUSINDBK": "IndusInd Bank Ltd",
        "FEDERALBNK": "The Federal Bank Ltd",
        "OFSS": "Oracle Financial Services Software Ltd",
        "FORTIS": "Fortis Healthcare Ltd",
        "NATIONALUM": "National Aluminium Company Ltd",
        "YESBANK": "Yes Bank Ltd",
        "SAIL": "Steel Authority of India Ltd",
        "MCX": "Multi Commodity Exchange of India Ltd",
        "IDFCFIRSTB": "IDFC First Bank Ltd",
        "RVNL": "Rail Vikas Nigam Ltd",
        "JSL": "Jindal Stainless Ltd",
        "COROMANDEL": "Coromandel International Ltd",
        "ATGL": "Adani Total Gas Ltd",
        "PRESTIGE": "Prestige Estates Projects Ltd",
        "PHOENIXLTD": "The Phoenix Mills Ltd",
        "MRF": "MRF Ltd",
        "BIOCON": "Biocon Ltd",
        "UPL": "UPL Ltd",
        "OBEROIRLTY": "Oberoi Realty Ltd",
        "MFSL": "Max Financial Services Ltd",
        "COLPAL": "Colgate-Palmolive (India) Ltd",
        "BERGEPAINT": "Berger Paints India Ltd",
        "APLAPOLLO": "APL Apollo Tubes Ltd",
        "COFORGE": "Coforge Ltd",
        "MOTILALOFS": "Motilal Oswal Financial Services Ltd",
        "IRCTC": "Indian Railway Catering and Tourism Corporation Ltd",
        "MPHASIS": "Mphasis Ltd",
        "PIIND": "PI Industries Ltd",
        "TATACOMM": "Tata Communications Ltd",
        "VOLTAS": "Voltas Ltd",
        "PAGEIND": "Page Industries Ltd",
        "CONCOR": "Container Corporation of India Ltd",
        "ESCORTS": "Escorts Kubota Ltd",
        "ACC": "ACC Ltd",
        "EXIDEIND": "Exide Industries Ltd",
        "JUBLFOOD": "Jubilant FoodWorks Ltd",
        "BANDHANBNK": "Bandhan Bank Ltd",
        "ANGELONE": "Angel One Ltd",
        "IGL": "Indraprastha Gas Ltd",
        "RAMCOCEM": "The Ramco Cements Ltd",
        "LALPATHLAB": "Dr. Lal PathLabs Ltd",
        "SUZLON": "Suzlon Energy Ltd",
        "SUNTV": "Sun TV Network Ltd",
        "IEX": "Indian Energy Exchange Ltd",
        "BATAINDIA": "Bata India Ltd",
        "PVRINOX": "PVR INOX Ltd",
        "METROPOLIS": "Metropolis Healthcare Ltd",
        "AARTIIND": "Aarti Industries Ltd",
        "GRANULES": "Granules India Ltd",
        "CEATLTD": "CEAT Ltd",
        "FINEORG": "Fine Organic Industries Ltd",
        "CROMPTON": "Crompton Greaves Consumer Electricals Ltd",
        "KEC": "KEC International Ltd",
        "KAJARIACER": "Kajaria Ceramics Ltd",
        "RBLBANK": "RBL Bank Ltd",
        "EIDPARRY": "EID Parry (India) Ltd",
        "BALKRISIND": "Balkrishna Industries Ltd",
        "CRISIL": "CRISIL Ltd",
        "GLENMARK": "Glenmark Pharmaceuticals Ltd",
        "ABB": "ABB India Ltd",
        "THERMAX": "Thermax Ltd",
        "ASTERDM": "Aster DM Healthcare Ltd",
        "COCHINSHIP": "Cochin Shipyard Ltd",
        "LTTS": "L&T Technology Services Ltd",
        "HEXAWARE": "Hexaware Technologies Ltd",
        "SCHAEFFLER": "Schaeffler India Ltd",
        "LODHA": "Macrotech Developers Ltd",
        "MAXHEALTH": "Max Healthcare Institute Ltd",
        "ZFCVINDIA": "ZF Commercial Vehicle Control Systems India Ltd",
        "SUPREMEIND": "Supreme Industries Ltd",
        "ASTRAL": "Astral Ltd",
        "GLAXO": "GlaxoSmithKline Pharmaceuticals Ltd",
        "UBL": "United Breweries Ltd",
        "POLYCAB": "Polycab India Ltd",
        "NAM-INDIA": "Nippon Life India Asset Management Ltd",
        "CAMS": "Computer Age Management Services Ltd",
        "NSDL": "National Securities Depository Ltd",
        "OLAELEC": "Ola Electric Mobility Ltd",
    }

    # ── sector classification rules ──────────────────────────────────────
    def _classify_sector(entry_upper: str, symbol: str, name: str) -> str:
        combined = entry_upper + " " + symbol + " " + name.upper()

        if any(k in combined for k in ("BANK", "BANKING")):
            return "Banking"
        if any(k in combined for k in ("FIN", "CAPITAL", "HOUSING FINANCE", "MUTUAL FUND",
                                        "ASSET MANAGEMENT", "NBFC", "MICROFIN")):
            return "Financial Services"
        if any(k in combined for k in ("INSURANCE",)):
            return "Insurance"
        if any(k in combined for k in ("IT ", "SOFTWARE", "CONSULTANCY SVC",
                                        "DIGITAL", "TECHNO", "INFOSYS",
                                        "WIPRO", "HCLTECH", "TCS", "TECH MAHINDRA",
                                        "PERSISTENT", "COFORGE", "MPHASIS",
                                        "LTI", "MINDTREE")):
            return "Information Technology"
        if any(k in combined for k in ("PHARMA", "HEALTHC", "HOSPITAL", "MEDICAL",
                                        "DIAGNOSTIC", "LAB", "LIFESCIENCE")):
            return "Pharma & Healthcare"
        if any(k in combined for k in ("AUTO", "MOTOR", "TYRE", "CAR", "TRACTOR")):
            return "Automobile"
        if any(k in combined for k in ("FMCG", "CONSUMER", "FOOD", "BEVERAGE",
                                        "DAIRY", "TOBACCO")):
            return "FMCG"
        if any(k in combined for k in ("OIL", "GAS", "PETRO", "REFINERY")):
            return "Oil & Gas"
        if any(k in combined for k in ("POWER", "ENERGY", "ELECTRIC")):
            return "Power"
        if any(k in combined for k in ("STEEL", "METAL", "MINING", "ALUMINIUM",
                                        "COPPER", "ZINC")):
            return "Metals & Mining"
        if any(k in combined for k in ("TELECOM", "COMMUNICATION", "MOBI")):
            return "Telecom"
        if any(k in combined for k in ("REALTY", "REAL ESTATE", "PROPERT",
                                        "DEVELOPER")):
            return "Real Estate"
        if any(k in combined for k in ("CEMENT", "CONSTRUCTION", "INFRA",
                                        "ENGINEERING", "BUILD")):
            return "Infrastructure & Construction"
        if any(k in combined for k in ("CHEMICAL", "FERTILIZER", "PESTICIDE",
                                        "AGRO", "CROP")):
            return "Chemicals"
        if any(k in combined for k in ("MEDIA", "ENTERTAINMENT", "FILM",
                                        "TELEVISION", "NEWS", "BROADCAST")):
            return "Media & Entertainment"
        if any(k in combined for k in ("TEXTILE", "APPAREL", "GARMENT", "FASHION")):
            return "Textiles"
        if any(k in combined for k in ("HOTEL", "TOURISM", "HOSPITALITY",
                                        "RESORT")):
            return "Hospitality"
        if any(k in combined for k in ("LOGISTIC", "SHIPPING", "WAREHOUSE",
                                        "FREIGHT")):
            return "Logistics"
        if any(k in combined for k in ("ELECTRICAL", "ELECTRONICS", "SWITCHGEAR",
                                        "CABLE")):
            return "Electrical & Electronics"
        if any(k in combined for k in ("DEFENCE", "AERONAUTICAL", "SHIPBUILD")):
            return "Defence"
        if any(k in combined for k in ("EDUCATION", "LEARNING", "SKILL")):
            return "Education"
        if any(k in combined for k in ("RETAIL", "MART", "STORE")):
            return "Retail"
        if any(k in combined for k in ("SUGAR", "RICE", "MILL", "FLOUR")):
            return "Agri & Food Processing"
        return "Others"

    for raw in Config.DEFAULT_SYMBOLS:
        raw_str = str(raw).strip()
        if not raw_str:
            continue

        symbol = _normalize_company(raw_str)
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)

# Determine human-readable name
        if symbol in KNOWN_NAMES:
            name = KNOWN_NAMES[symbol]
        elif "." in raw_str and raw_str.count(".") >= 2:
            # Looks like "Company Name Ltd..NS" → extract name before the ..
            name = raw_str.rsplit(".", 1)[0].strip()
        elif "." in raw_str:
            name = symbol
        else:
            name = symbol

# Determine exchange
        exchange = "NSE" if raw_str.upper().endswith(".NS") else "BSE"

        sector = _classify_sector(raw_str.upper(), symbol, name)

        stocks.append({
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "exchange": exchange,
        })

    # Sort alphabetically by symbol
    stocks.sort(key=lambda s: s["symbol"])
    return stocks


# ── built once at import time ────────────────────────────────────────────
_STOCK_UNIVERSE: list[dict[str, Any]] | None = None


def _get_universe() -> list[dict[str, Any]]:
    global _STOCK_UNIVERSE
    if _STOCK_UNIVERSE is None:
        _STOCK_UNIVERSE = _build_stock_universe()
    return _STOCK_UNIVERSE


# ── public API ───────────────────────────────────────────────────────────

def get_stock_universe() -> list[dict[str, Any]]:
    """Return the full list of known stocks."""
    return _get_universe()


def search_stocks(query: str, limit: int = 15) -> list[dict[str, Any]]:
    """Case-insensitive partial search across symbol, name, and sector.

    Results are ordered by relevance:
        1. Exact symbol match
        2. Symbol starts with query
        3. Name starts with query
        4. Symbol contains query
        5. Name contains query
        6. Sector contains query
    """
    q = str(query).strip().upper()
    if not q:
        return _get_universe()[:limit]

    stocks = _get_universe()

    class Ranked:
        __slots__ = ("stock", "rank")

        def __init__(self, stock: dict[str, Any], rank: int):
            self.stock = stock
            self.rank = rank

    results: list[Ranked] = []
    for s in stocks:
        sym = s["symbol"]
        name = s["name"].upper() if s["name"] else ""
        sector = s["sector"].upper() if s["sector"] else ""

        if sym == q:
            rank = 0
        elif sym.startswith(q):
            rank = 1
        elif name.startswith(q):
            rank = 2
        elif sym.find(q) >= 0:
            rank = 3
        elif name.find(q) >= 0:
            rank = 4
        elif sector.find(q) >= 0:
            rank = 5
        else:
            continue

        # Boost rank for standard tickers (no spaces in symbol)
        # vs full-name entries (spaces in symbol), so popular
        # stocks like TCS, TITAN always appear before "TAJ GVK HOTELS..."
        is_standard = " " not in sym
        adjusted_rank = rank - 0.5 if is_standard else rank

        results.append(Ranked(s, adjusted_rank))

    results.sort(key=lambda r: (r.rank, r.stock["symbol"]))
    return [r.stock for r in results[:limit]]


def find_symbol(name_or_symbol: str) -> str | None:
    """Convert a company name or partial symbol to a normalized symbol.

    Returns the best-matching symbol, or None if nothing is found.
    Useful for accepting user-friendly names in search inputs.
    """
    q = str(name_or_symbol).strip().upper()
    if not q:
        return None

    stocks = _get_universe()

    # exact symbol match first
    for s in stocks:
        if s["symbol"] == q:
            return s["symbol"]

    # exact name match
    for s in stocks:
        if s["name"] and s["name"].upper() == q:
            return s["symbol"]

    # name contains the query
    for s in stocks:
        if s["name"] and q in s["name"].upper():
            return s["symbol"]
        if q in s["symbol"]:
            return s["symbol"]

    return None


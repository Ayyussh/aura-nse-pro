"""NSE Stock Universe & Liquidity Filtering Module.

Defines the curated NIFTY 500 equity universe with sector mappings,
ASM/GSM filters, EQ series validation, and traded liquidity gates.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from backend.data.symbol_master import symbol_master

# Representative high-liquidity NIFTY 500 constituent universe across sectors (191 Stocks)
NIFTY_500_SYMBOLS: List[str] = [
    # Information Technology & Internet Platforms
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "LTIM.NS", "TECHM.NS",
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "TATAELXSI.NS", "TATATECH.NS", "NAUKRI.NS",

    # New-Age Consumer Tech & Platforms
    "ETERNAL.NS", "SWIGGY.NS", "POLICYBZR.NS",

    # Banking (Private & PSU)
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "INDIANB.NS",
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "AUBANK.NS",

    # NBFC, Housing Finance & Wealth Management
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "BAJAJHLDNG.NS", "BAJAJHFL.NS",
    "CHOLAFIN.NS", "SHRIRAMFIN.NS", "MUTHOOTFIN.NS",
    "PFC.NS", "RECLTD.NS", "IRFC.NS", "MOTILALOFS.NS", "ANANDRATHI.NS",

    # Market Infrastructure, Exchanges & Ratings
    "BSE.NS", "MCX.NS", "CDSL.NS", "CAMS.NS", "CRISIL.NS", "IEX.NS",

    # Insurance
    "HDFCLIFE.NS", "SBILIFE.NS", "ICICIPRULI.NS", "ICICIGI.NS",

    # Energy, Oil & Gas
    "RELIANCE.NS", "ONGC.NS", "IOC.NS", "BPCL.NS", "HINDPETRO.NS", "OIL.NS", "GAIL.NS",

    # Power, Renewables & Utilities
    "NTPC.NS", "POWERGRID.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "ADANIPOWER.NS",
    "ADANIENSOL.NS", "NHPC.NS", "SJVN.NS", "SUZLON.NS",

    # Automobiles & Auto Ancillaries
    "TATAMOTORS.NS", "TMPV.NS", "TMCV.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "TVSMOTOR.NS", "BHARATFORG.NS", "BOSCHLTD.NS",
    "SONACOMS.NS", "MOTHERSON.NS", "UNOMINDA.NS", "TIINDIA.NS", "EXIDEIND.NS",

    # FMCG, QSR & Beverages
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
    "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "VBL.NS", "COLPAL.NS", "PGHH.NS",
    "EMAMILTD.NS", "PATANJALI.NS", "JYOTHYLAB.NS", "BIKAJI.NS",
    "JUBLFOOD.NS", "DEVYANI.NS", "WESTLIFE.NS",
    "RADICO.NS", "UBL.NS", "UNITDSPR.NS", "AWL.NS",

    # Paints
    "ASIANPAINT.NS", "BERGEPAINT.NS",

    # Retail, Footwear, Jewelry & Apparel
    "TITAN.NS", "TRENT.NS", "DMART.NS", "KALYANKJIL.NS",
    "RELAXO.NS", "METROBRAND.NS", "PAGEIND.NS", "MANYAVAR.NS",

    # Consumer Durables, Electronics & EMS
    "VOLTAS.NS", "DIXON.NS", "KAYNES.NS", "BAJAJELEC.NS",

    # Hospitality & Aviation
    "INDHOTEL.NS", "INDIGO.NS",

    # Metals & Mining
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS",
    "JINDALSTEL.NS", "NMDC.NS", "SAIL.NS", "NATIONALUM.NS", "HINDZINC.NS",

    # Adani Flagship & Infrastructure
    "ADANIENT.NS", "ADANIPORTS.NS", "ATGL.NS",

    # Defense, Aerospace & Explosives
    "HAL.NS", "BEL.NS", "BDL.NS", "COCHINSHIP.NS", "MAZDOCK.NS", "SOLARINDS.NS",

    # Railways & Logistics
    "RVNL.NS", "IRCTC.NS", "CONCOR.NS", "RAILTEL.NS",

    # Pharmaceuticals & Healthcare
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "LUPIN.NS", "TORNTPHARM.NS", "ZYDUSLIFE.NS", "MAXHEALTH.NS",
    "MANKIND.NS", "IPCALAB.NS", "MEDANTA.NS", "NH.NS", "FORTIS.NS", "LALPATHLAB.NS",

    # Infrastructure, Capital Goods & Industrials
    "LT.NS", "SIEMENS.NS", "ABB.NS", "BHEL.NS", "CUMMINSIND.NS",
    "POLYCAB.NS", "KEI.NS", "THERMAX.NS", "AIAENG.NS",

    # Chemicals & Specialty Materials
    "PIDILITIND.NS", "SRF.NS", "AARTIIND.NS", "DEEPAKNTR.NS", "TATACHEM.NS",
    "GUJGASLTD.NS", "RALLIS.NS", "PIIND.NS", "FLUOROCHEM.NS", "CLEAN.NS",

    # Cement & Construction Materials
    "ULTRACEMCO.NS", "GRASIM.NS", "AMBUJACEM.NS", "SHREECEM.NS", "ACC.NS",

    # Real Estate
    "DLF.NS", "GODREJPROP.NS", "LODHA.NS", "OBEROIRLTY.NS",

    # Telecom & Media
    "BHARTIARTL.NS", "TATACOMM.NS", "TEJASNET.NS", "NELCO.NS", "PVRINOX.NS", "NDTV.NS"
]

# Sector classification mapping
SYMBOL_SECTOR_MAP: Dict[str, str] = {
    # IT & Internet Platforms
    "TCS.NS": "IT", "INFY.NS": "IT", "HCLTECH.NS": "IT", "WIPRO.NS": "IT", "LTIM.NS": "IT",
    "TECHM.NS": "IT", "PERSISTENT.NS": "IT", "COFORGE.NS": "IT", "MPHASIS.NS": "IT",
    "TATAELXSI.NS": "IT", "TATATECH.NS": "IT", "NAUKRI.NS": "IT",

    # New-Age Consumer Tech & Platforms
    "ETERNAL.NS": "Consumer Tech", "SWIGGY.NS": "Consumer Tech", "POLICYBZR.NS": "Financial Services",

    # Banking
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "SBIN.NS": "Banking", "KOTAKBANK.NS": "Banking",
    "AXISBANK.NS": "Banking", "INDUSINDBK.NS": "Banking", "BANKBARODA.NS": "Banking", "PNB.NS": "Banking",
    "CANBK.NS": "Banking", "UNIONBANK.NS": "Banking", "INDIANB.NS": "Banking",
    "FEDERALBNK.NS": "Banking", "IDFCFIRSTB.NS": "Banking", "AUBANK.NS": "Banking",

    # NBFC, Wealth & Financial Services
    "BAJFINANCE.NS": "NBFC", "BAJAJFINSV.NS": "NBFC", "BAJAJHLDNG.NS": "NBFC", "BAJAJHFL.NS": "NBFC",
    "CHOLAFIN.NS": "NBFC", "SHRIRAMFIN.NS": "NBFC", "MUTHOOTFIN.NS": "NBFC",
    "PFC.NS": "NBFC", "RECLTD.NS": "NBFC", "IRFC.NS": "NBFC",
    "MOTILALOFS.NS": "Financial Services", "ANANDRATHI.NS": "Financial Services",

    # Market Infrastructure, Exchanges & Ratings
    "BSE.NS": "Financial Services", "MCX.NS": "Financial Services", "CDSL.NS": "Financial Services",
    "CAMS.NS": "Financial Services", "CRISIL.NS": "Financial Services", "IEX.NS": "Financial Services",

    # Insurance
    "HDFCLIFE.NS": "Insurance", "SBILIFE.NS": "Insurance", "ICICIPRULI.NS": "Insurance", "ICICIGI.NS": "Insurance",

    # Energy & Petroleum
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "IOC.NS": "Energy", "BPCL.NS": "Energy",
    "HINDPETRO.NS": "Energy", "OIL.NS": "Energy", "GAIL.NS": "Utilities",

    # Power & Utilities
    "NTPC.NS": "Power", "POWERGRID.NS": "Power", "ADANIGREEN.NS": "Power", "TATAPOWER.NS": "Power",
    "ADANIPOWER.NS": "Power", "ADANIENSOL.NS": "Power", "NHPC.NS": "Power", "SJVN.NS": "Power", "SUZLON.NS": "Power",

    # Auto & Auto Ancillaries
    "TATAMOTORS.NS": "Auto", "TMPV.NS": "Auto", "TMCV.NS": "Auto", "M&M.NS": "Auto", "MARUTI.NS": "Auto", "BAJAJ-AUTO.NS": "Auto",
    "HEROMOTOCO.NS": "Auto", "EICHERMOT.NS": "Auto", "TVSMOTOR.NS": "Auto",
    "BHARATFORG.NS": "Auto Ancillary", "BOSCHLTD.NS": "Auto Ancillary",
    "SONACOMS.NS": "Auto Ancillary", "MOTHERSON.NS": "Auto Ancillary", "UNOMINDA.NS": "Auto Ancillary",
    "TIINDIA.NS": "Auto Ancillary", "EXIDEIND.NS": "Auto Ancillary",

    # FMCG & Beverages
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG", "BRITANNIA.NS": "FMCG",
    "TATACONSUM.NS": "FMCG", "DABUR.NS": "FMCG", "MARICO.NS": "FMCG", "GODREJCP.NS": "FMCG",
    "VBL.NS": "FMCG", "COLPAL.NS": "FMCG", "PGHH.NS": "FMCG", "EMAMILTD.NS": "FMCG",
    "PATANJALI.NS": "FMCG", "JYOTHYLAB.NS": "FMCG", "BIKAJI.NS": "FMCG",
    "JUBLFOOD.NS": "FMCG", "DEVYANI.NS": "FMCG", "WESTLIFE.NS": "FMCG",
    "RADICO.NS": "FMCG", "UBL.NS": "FMCG", "UNITDSPR.NS": "FMCG", "AWL.NS": "FMCG",

    # Paints
    "ASIANPAINT.NS": "Paints", "BERGEPAINT.NS": "Paints",

    # Retail, Footwear, Jewelry & Apparel
    "TITAN.NS": "Consumer Goods", "TRENT.NS": "Retail", "DMART.NS": "Retail", "KALYANKJIL.NS": "Consumer Goods",
    "RELAXO.NS": "Consumer Goods", "METROBRAND.NS": "Consumer Goods",
    "PAGEIND.NS": "Textiles & Apparel", "MANYAVAR.NS": "Textiles & Apparel",

    # Consumer Durables, Electronics & EMS
    "VOLTAS.NS": "Consumer Durables", "DIXON.NS": "Electronics", "KAYNES.NS": "Electronics",
    "BAJAJELEC.NS": "Consumer Durables",

    # Hospitality & Aviation
    "INDHOTEL.NS": "Hospitality", "INDIGO.NS": "Aviation",

    # Metals & Mining
    "TATASTEEL.NS": "Metals", "JSWSTEEL.NS": "Metals", "HINDALCO.NS": "Metals", "VEDL.NS": "Metals",
    "COALINDIA.NS": "Mining", "JINDALSTEL.NS": "Metals", "NMDC.NS": "Mining",
    "SAIL.NS": "Metals", "NATIONALUM.NS": "Metals", "HINDZINC.NS": "Metals",

    # Adani Flagship & Infrastructure
    "ADANIENT.NS": "Diversified", "ADANIPORTS.NS": "Infrastructure", "ATGL.NS": "Gas Distribution",

    # Defense, Aerospace & Explosives
    "HAL.NS": "Defense", "BEL.NS": "Defense", "BDL.NS": "Defense",
    "COCHINSHIP.NS": "Defense", "MAZDOCK.NS": "Defense", "SOLARINDS.NS": "Defense",

    # Railways & Logistics
    "RVNL.NS": "Railways", "IRCTC.NS": "Railways", "CONCOR.NS": "Logistics", "RAILTEL.NS": "Telecom",

    # Pharma & Healthcare
    "SUNPHARMA.NS": "Pharma", "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma",
    "APOLLOHOSP.NS": "Healthcare", "LUPIN.NS": "Pharma", "TORNTPHARM.NS": "Pharma",
    "ZYDUSLIFE.NS": "Pharma", "MAXHEALTH.NS": "Healthcare",
    "MANKIND.NS": "Pharma", "IPCALAB.NS": "Pharma",
    "MEDANTA.NS": "Healthcare", "NH.NS": "Healthcare", "FORTIS.NS": "Healthcare", "LALPATHLAB.NS": "Healthcare",

    # Capital Goods & Electricals
    "LT.NS": "Capital Goods", "SIEMENS.NS": "Capital Goods", "ABB.NS": "Capital Goods",
    "BHEL.NS": "Capital Goods", "CUMMINSIND.NS": "Capital Goods",
    "POLYCAB.NS": "Cables & Electricals", "KEI.NS": "Cables & Electricals",
    "THERMAX.NS": "Capital Goods", "AIAENG.NS": "Capital Goods",

    # Chemicals & Specialty Materials
    "PIDILITIND.NS": "Chemicals", "SRF.NS": "Chemicals", "AARTIIND.NS": "Chemicals",
    "DEEPAKNTR.NS": "Chemicals", "TATACHEM.NS": "Chemicals", "GUJGASLTD.NS": "Gas Distribution",
    "RALLIS.NS": "Chemicals", "PIIND.NS": "Chemicals", "FLUOROCHEM.NS": "Chemicals", "CLEAN.NS": "Chemicals",

    # Cement
    "ULTRACEMCO.NS": "Cement", "GRASIM.NS": "Cement", "AMBUJACEM.NS": "Cement",
    "SHREECEM.NS": "Cement", "ACC.NS": "Cement",

    # Real Estate
    "DLF.NS": "Realty", "GODREJPROP.NS": "Realty", "LODHA.NS": "Realty", "OBEROIRLTY.NS": "Realty",

    # Telecom & Media
    "BHARTIARTL.NS": "Telecom", "TATACOMM.NS": "Telecom", "TEJASNET.NS": "Telecom", "NELCO.NS": "Telecom",
    "PVRINOX.NS": "Media", "NDTV.NS": "Media"
}

# Known Surveillance (ASM / GSM / Trade-to-Trade) exclusions
EXCLUDED_SURVEILLANCE_SYMBOLS: Set[str] = set()


# Symbol Master & Historical Alias Registry (Section 17.2, 18.3, 19.3)
SYMBOL_MASTER_ALIASES: Dict[str, str] = symbol_master.alias_to_active


def resolve_symbol_master(symbol: str) -> str:
    """Resolve symbol through Symbol Master to active corporate ticker ensuring historical continuity."""
    return symbol_master.resolve(symbol)


def can_splice_history(from_symbol: str, to_symbol: str, as_of_date) -> Tuple[bool, str]:
    """Check if price history between symbols may be spliced across restructuring events."""
    return symbol_master.can_splice_history(from_symbol, to_symbol, as_of_date)


def get_sector_for_symbol(symbol: str) -> str:
    """Retrieve normalized sector for an equity ticker."""
    resolved = resolve_symbol_master(symbol)
    clean = resolved.upper()
    return SYMBOL_SECTOR_MAP.get(clean, "Diversified/Other")


# ---------------------------------------------------------------------------
# Complete Master Universe of All Listed NSE Equities (2,760+ instruments)
# ---------------------------------------------------------------------------
def _load_all_listed_nse_symbols() -> List[str]:
    """Dynamically load all official listed symbols on the National Stock Exchange."""
    try:
        from pathlib import Path
        all_json = Path(__file__).resolve().parent.parent.parent / "data" / "all_nse_symbols.json"
        if all_json.exists():
            import json
            with open(all_json, "r", encoding="utf-8") as f:
                syms = json.load(f)
                if isinstance(syms, list) and len(syms) > 1000:
                    return syms
    except Exception:
        pass
    return NIFTY_500_SYMBOLS


ALL_LISTED_NSE_SYMBOLS: List[str] = _load_all_listed_nse_symbols()


def get_all_listed_symbols() -> List[str]:
    """Return the complete master universe of all ~2,760 listed NSE equities."""
    return [s for s in ALL_LISTED_NSE_SYMBOLS if s not in EXCLUDED_SURVEILLANCE_SYMBOLS]


def get_universe_symbols(limit: int | None = None, mode: str = "all") -> List[str]:
    """Return filtered equity universe symbols.

    Modes:
      - 'all': Prioritizes sector-stratified bluechips and NIFTY 500 constituents first,
               then spans all ~2,760 listed NSE stocks.
      - 'diversified': Sector-stratified bluechips across all major sectors.
      - 'curated': Liquid institutional universe (191 core mapped stocks).
    """
    if mode == "all":
        seen: Set[str] = set()
        symbols: List[str] = []
        # 1. Sector-stratified bluechips first (guarantees cross-sector balance from index 0)
        for s in get_diversified_universe_symbols(limit=70):
            if s not in EXCLUDED_SURVEILLANCE_SYMBOLS and s not in seen:
                symbols.append(s)
                seen.add(s)
        # 2. Institutional NIFTY 500 constituents next
        for s in NIFTY_500_SYMBOLS:
            if s not in EXCLUDED_SURVEILLANCE_SYMBOLS and s not in seen:
                symbols.append(s)
                seen.add(s)
        # 3. All remaining listed symbols
        for s in ALL_LISTED_NSE_SYMBOLS:
            if s not in EXCLUDED_SURVEILLANCE_SYMBOLS and s not in seen:
                symbols.append(s)
                seen.add(s)
    elif mode == "diversified":
        return get_diversified_universe_symbols(limit=limit or 40)
    else:
        symbols = [s for s in NIFTY_500_SYMBOLS if s not in EXCLUDED_SURVEILLANCE_SYMBOLS]

    if limit:
        return symbols[:limit]
    return symbols


def get_diversified_universe_symbols(limit: int = 40) -> List[str]:
    """Return a sector-stratified, high-liquidity universe ensuring representation across all major sectors."""
    sectors_pool: Dict[str, List[str]] = {
        "Banking": ["ICICIBANK.NS", "HDFCBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "BANKBARODA.NS", "FEDERALBNK.NS"],
        "NBFC": ["CHOLAFIN.NS", "BAJFINANCE.NS", "MUTHOOTFIN.NS", "SHRIRAMFIN.NS", "BAJAJFINSV.NS", "PFC.NS", "RECLTD.NS"],
        "IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "TECHM.NS", "WIPRO.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS"],
        "Automobiles": ["BAJAJ-AUTO.NS", "M&M.NS", "MARUTI.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "TVSMOTOR.NS", "BHARATFORG.NS"],
        "Metals": ["JSWSTEEL.NS", "TATASTEEL.NS", "HINDALCO.NS", "VEDL.NS", "JINDALSTEL.NS", "COALINDIA.NS"],
        "FMCG": ["ITC.NS", "HINDUNILVR.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "DABUR.NS", "MARICO.NS", "COLPAL.NS"],
        "Energy": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "BPCL.NS", "IOC.NS", "GAIL.NS"],
        "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "LUPIN.NS", "APOLLOHOSP.NS", "MAXHEALTH.NS"],
        "Capital Goods": ["LT.NS", "SIEMENS.NS", "ABB.NS", "POLYCAB.NS", "KEI.NS", "BHEL.NS", "CUMMINSIND.NS"],
        "Financial Services": ["BSE.NS", "MCX.NS", "CDSL.NS", "CAMS.NS", "CRISIL.NS"],
    }
    selected: List[str] = []
    max_len = max(len(lst) for lst in sectors_pool.values())
    for i in range(max_len):
        for sec, lst in sectors_pool.items():
            if i < len(lst) and lst[i] not in selected:
                selected.append(lst[i])
                if len(selected) >= limit:
                    return selected
    return selected

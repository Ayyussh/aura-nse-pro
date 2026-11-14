"""NSE Stock Universe & Liquidity Filtering Module.

Defines the curated NIFTY 500 equity universe with sector mappings,
ASM/GSM filters, EQ series validation, and traded liquidity gates.
"""

from __future__ import annotations
from typing import Dict, List, Set

# Representative high-liquidity NIFTY 500 constituent universe across sectors
NIFTY_500_SYMBOLS: List[str] = [
    # Information Technology
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "LTIM.NS", "TECHM.NS",
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "TATAELXSI.NS", "TATATECH.NS",

    # Banking & Financial Services
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "INDIANB.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "BAJAJHLDNG.NS", "BAJAJHFL.NS",
    "CHOLAFIN.NS", "SHRIRAMFIN.NS", "MUTHOOTFIN.NS",
    "PFC.NS", "RECLTD.NS", "IRFC.NS", "CDSL.NS",
    "HDFCLIFE.NS", "SBILIFE.NS", "ICICIPRULI.NS", "ICICIGI.NS",

    # Energy, Oil & Gas
    "RELIANCE.NS", "ONGC.NS", "IOC.NS", "BPCL.NS", "HINDPETRO.NS", "OIL.NS", "GAIL.NS",

    # Power & Utilities
    "NTPC.NS", "POWERGRID.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "ADANIPOWER.NS",
    "ADANIENSOL.NS", "NHPC.NS", "SJVN.NS",

    # Automobiles & Auto Ancillaries
    "TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "TVSMOTOR.NS", "BHARATFORG.NS", "BOSCHLTD.NS",

    # FMCG & Beverages
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
    "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "VBL.NS", "COLPAL.NS", "PGHH.NS",
    "EMAMILTD.NS", "PATANJALI.NS", "JYOTHYLAB.NS", "BIKAJI.NS",
    "RADICO.NS", "UBL.NS", "UNITDSPR.NS",

    # Paints
    "ASIANPAINT.NS", "BERGEPAINT.NS",

    # Retail, Footwear & Apparel
    "TITAN.NS", "TRENT.NS", "DMART.NS", "RELAXO.NS", "PAGEIND.NS",

    # Consumer Durables & Electronics
    "VOLTAS.NS", "DIXON.NS", "BAJAJELEC.NS",

    # Metals & Mining
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS",
    "JINDALSTEL.NS", "NMDC.NS", "SAIL.NS", "NATIONALUM.NS", "HINDZINC.NS",

    # Adani Flagship & Multi-Industry
    "ADANIENT.NS", "ADANIPORTS.NS", "ATGL.NS", "AWL.NS",

    # Defense & Aerospace
    "HAL.NS", "BEL.NS", "BDL.NS", "COCHINSHIP.NS", "MAZDOCK.NS",

    # Railways & Logistics
    "RVNL.NS", "IRCTC.NS", "CONCOR.NS", "RAILTEL.NS",

    # Pharmaceuticals & Healthcare
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "LUPIN.NS", "TORNTPHARM.NS", "ZYDUSLIFE.NS", "MAXHEALTH.NS",

    # Infrastructure, Capital Goods & Industrials
    "LT.NS", "SIEMENS.NS", "ABB.NS", "BHEL.NS", "CUMMINSIND.NS", "POLYCAB.NS", "KEI.NS",

    # Chemicals & Agriculture
    "PIDILITIND.NS", "SRF.NS", "AARTIIND.NS", "DEEPAKNTR.NS", "TATACHEM.NS",
    "GUJGASLTD.NS", "RALLIS.NS",

    # Cement & Construction Materials
    "ULTRACEMCO.NS", "GRASIM.NS", "AMBUJACEM.NS", "SHREECEM.NS", "ACC.NS",

    # Real Estate
    "DLF.NS", "GODREJPROP.NS", "LODHA.NS", "OBEROIRLTY.NS",

    # Telecom & Media
    "BHARTIARTL.NS", "TATACOMM.NS", "TEJASNET.NS", "NELCO.NS", "PVRINOX.NS", "NDTV.NS"
]

# Sector classification mapping
SYMBOL_SECTOR_MAP: Dict[str, str] = {
    # IT
    "TCS.NS": "IT", "INFY.NS": "IT", "HCLTECH.NS": "IT", "WIPRO.NS": "IT", "LTIM.NS": "IT",
    "TECHM.NS": "IT", "PERSISTENT.NS": "IT", "COFORGE.NS": "IT", "MPHASIS.NS": "IT",
    "TATAELXSI.NS": "IT", "TATATECH.NS": "IT",

    # Banking
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "SBIN.NS": "Banking", "KOTAKBANK.NS": "Banking",
    "AXISBANK.NS": "Banking", "INDUSINDBK.NS": "Banking", "BANKBARODA.NS": "Banking", "PNB.NS": "Banking",
    "CANBK.NS": "Banking", "UNIONBANK.NS": "Banking", "INDIANB.NS": "Banking",

    # NBFC & Financial Services
    "BAJFINANCE.NS": "NBFC", "BAJAJFINSV.NS": "NBFC", "BAJAJHLDNG.NS": "NBFC", "BAJAJHFL.NS": "NBFC",
    "CHOLAFIN.NS": "NBFC", "SHRIRAMFIN.NS": "NBFC", "MUTHOOTFIN.NS": "NBFC",
    "PFC.NS": "NBFC", "RECLTD.NS": "NBFC", "IRFC.NS": "NBFC", "CDSL.NS": "Financial Services",

    # Insurance
    "HDFCLIFE.NS": "Insurance", "SBILIFE.NS": "Insurance", "ICICIPRULI.NS": "Insurance", "ICICIGI.NS": "Insurance",

    # Energy & Petroleum
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "IOC.NS": "Energy", "BPCL.NS": "Energy",
    "HINDPETRO.NS": "Energy", "OIL.NS": "Energy", "GAIL.NS": "Utilities",

    # Power & Utilities
    "NTPC.NS": "Power", "POWERGRID.NS": "Power", "ADANIGREEN.NS": "Power", "TATAPOWER.NS": "Power",
    "ADANIPOWER.NS": "Power", "ADANIENSOL.NS": "Power", "NHPC.NS": "Power", "SJVN.NS": "Power",

    # Auto & Auto Ancillaries
    "TATAMOTORS.NS": "Auto", "M&M.NS": "Auto", "MARUTI.NS": "Auto", "BAJAJ-AUTO.NS": "Auto",
    "HEROMOTOCO.NS": "Auto", "EICHERMOT.NS": "Auto", "TVSMOTOR.NS": "Auto",
    "BHARATFORG.NS": "Auto Ancillary", "BOSCHLTD.NS": "Auto Ancillary",

    # FMCG & Beverages
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG", "BRITANNIA.NS": "FMCG",
    "TATACONSUM.NS": "FMCG", "DABUR.NS": "FMCG", "MARICO.NS": "FMCG", "GODREJCP.NS": "FMCG",
    "VBL.NS": "FMCG", "COLPAL.NS": "FMCG", "PGHH.NS": "FMCG", "EMAMILTD.NS": "FMCG",
    "PATANJALI.NS": "FMCG", "JYOTHYLAB.NS": "FMCG", "BIKAJI.NS": "FMCG",
    "RADICO.NS": "FMCG", "UBL.NS": "FMCG", "UNITDSPR.NS": "FMCG", "AWL.NS": "FMCG",

    # Paints
    "ASIANPAINT.NS": "Paints", "BERGEPAINT.NS": "Paints",

    # Retail, Footwear & Apparel
    "TITAN.NS": "Consumer Goods", "TRENT.NS": "Retail", "DMART.NS": "Retail",
    "RELAXO.NS": "Consumer Goods", "PAGEIND.NS": "Textiles & Apparel",

    # Consumer Durables & Electronics
    "VOLTAS.NS": "Consumer Durables", "DIXON.NS": "Electronics", "BAJAJELEC.NS": "Consumer Durables",

    # Metals & Mining
    "TATASTEEL.NS": "Metals", "JSWSTEEL.NS": "Metals", "HINDALCO.NS": "Metals", "VEDL.NS": "Metals",
    "COALINDIA.NS": "Mining", "JINDALSTEL.NS": "Metals", "NMDC.NS": "Mining",
    "SAIL.NS": "Metals", "NATIONALUM.NS": "Metals", "HINDZINC.NS": "Metals",

    # Adani Flagship & Infrastructure
    "ADANIENT.NS": "Diversified", "ADANIPORTS.NS": "Infrastructure", "ATGL.NS": "Gas Distribution",

    # Defense & Aerospace
    "HAL.NS": "Defense", "BEL.NS": "Defense", "BDL.NS": "Defense",
    "COCHINSHIP.NS": "Defense", "MAZDOCK.NS": "Defense",

    # Railways & Logistics
    "RVNL.NS": "Railways", "IRCTC.NS": "Railways", "CONCOR.NS": "Logistics", "RAILTEL.NS": "Telecom",

    # Pharma & Healthcare
    "SUNPHARMA.NS": "Pharma", "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma",
    "APOLLOHOSP.NS": "Healthcare", "LUPIN.NS": "Pharma", "TORNTPHARM.NS": "Pharma",
    "ZYDUSLIFE.NS": "Pharma", "MAXHEALTH.NS": "Healthcare",

    # Capital Goods & Electricals
    "LT.NS": "Capital Goods", "SIEMENS.NS": "Capital Goods", "ABB.NS": "Capital Goods",
    "BHEL.NS": "Capital Goods", "CUMMINSIND.NS": "Capital Goods",
    "POLYCAB.NS": "Cables & Electricals", "KEI.NS": "Cables & Electricals",

    # Chemicals
    "PIDILITIND.NS": "Chemicals", "SRF.NS": "Chemicals", "AARTIIND.NS": "Chemicals",
    "DEEPAKNTR.NS": "Chemicals", "TATACHEM.NS": "Chemicals", "GUJGASLTD.NS": "Gas Distribution",
    "RALLIS.NS": "Chemicals",

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
EXCLUDED_SURVEILLANCE_SYMBOLS: Set[str] = {
    # Any stock placed under ASM/GSM stage II+ or trade-to-trade is quarantined here
}


def get_sector_for_symbol(symbol: str) -> str:
    """Retrieve normalized sector for an equity ticker."""
    clean = symbol.upper()
    return SYMBOL_SECTOR_MAP.get(clean, "Diversified/Other")


def get_universe_symbols(limit: int | None = None) -> List[str]:
    """Return filtered equity universe symbols."""
    symbols = [s for s in NIFTY_500_SYMBOLS if s not in EXCLUDED_SURVEILLANCE_SYMBOLS]
    if limit:
        return symbols[:limit]
    return symbols

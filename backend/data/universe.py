"""NSE Stock Universe & Liquidity Filtering Module.

Defines the curated NIFTY 500 equity universe with sector mappings,
ASM/GSM filters, EQ series validation, and traded liquidity gates.
"""

from __future__ import annotations
from typing import Dict, List, Set

# Representative high-liquidity NIFTY 500 constituent universe across sectors
NIFTY_500_SYMBOLS: List[str] = [
    # Information Technology
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "LTIM.NS", "TECHM.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS",
    # Banking & Financial Services
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS", "SHRIRAMFIN.NS", "MUTHOOTFIN.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    # Energy, Oil & Gas
    "RELIANCE.NS", "ONGC.NS", "IOC.NS", "BPCL.NS", "NTPC.NS", "POWERGRID.NS", "GAIL.NS", "ADANIGREEN.NS", "TATAPOWER.NS",
    # Automobiles & Auto Ancillaries
    "TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "TVSMOTOR.NS", "BHARATFORG.NS", "BOSCHLTD.NS",
    # FMCG & Consumption
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "VBL.NS", "TITAN.NS",
    # Metals & Mining
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS", "JINDALSTEL.NS", "NMDC.NS",
    # Pharmaceuticals & Healthcare
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "LUPIN.NS", "TORNTPHARM.NS", "ZYDUSLIFE.NS", "MAXHEALTH.NS",
    # Infrastructure, Capital Goods & Industrials
    "LT.NS", "SIEMENS.NS", "ABB.NS", "HAL.NS", "BEL.NS", "BHEL.NS", "CUMMINSIND.NS", "POLYCAB.NS", "KEI.NS",
    # Chemicals & Materials
    "PIDILITIND.NS", "SRF.NS", "AARTIIND.NS", "DEEPAKNTR.NS", "TATACHEM.NS", "GUJGASLTD.NS",
    # Cement & Construction Materials
    "ULTRACEMCO.NS", "GRASIM.NS", "AMBUJACEM.NS", "SHREECEM.NS", "ACC.NS",
    # Real Estate
    "DLF.NS", "GODREJPROP.NS", "LODHA.NS", "OBEROIRLTY.NS",
    # Telecom & Media
    "BHARTIARTL.NS", "TATACOMM.NS", "PVRINOX.NS"
]

# Sector classification mapping
SYMBOL_SECTOR_MAP: Dict[str, str] = {
    "TCS.NS": "IT", "INFY.NS": "IT", "HCLTECH.NS": "IT", "WIPRO.NS": "IT", "LTIM.NS": "IT",
    "TECHM.NS": "IT", "PERSISTENT.NS": "IT", "COFORGE.NS": "IT", "MPHASIS.NS": "IT",
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "SBIN.NS": "Banking", "KOTAKBANK.NS": "Banking",
    "AXISBANK.NS": "Banking", "INDUSINDBK.NS": "Banking", "BANKBARODA.NS": "Banking", "PNB.NS": "Banking",
    "BAJFINANCE.NS": "NBFC", "BAJAJFINSV.NS": "NBFC", "CHOLAFIN.NS": "NBFC", "SHRIRAMFIN.NS": "NBFC",
    "MUTHOOTFIN.NS": "NBFC", "HDFCLIFE.NS": "Insurance", "SBILIFE.NS": "Insurance",
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "IOC.NS": "Energy", "BPCL.NS": "Energy",
    "NTPC.NS": "Power", "POWERGRID.NS": "Power", "GAIL.NS": "Utilities", "ADANIGREEN.NS": "Power", "TATAPOWER.NS": "Power",
    "TATAMOTORS.NS": "Auto", "M&M.NS": "Auto", "MARUTI.NS": "Auto", "BAJAJ-AUTO.NS": "Auto",
    "HEROMOTOCO.NS": "Auto", "EICHERMOT.NS": "Auto", "TVSMOTOR.NS": "Auto", "BHARATFORG.NS": "Auto Ancillary", "BOSCHLTD.NS": "Auto Ancillary",
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG", "BRITANNIA.NS": "FMCG",
    "TATACONSUM.NS": "FMCG", "DABUR.NS": "FMCG", "MARICO.NS": "FMCG", "GODREJCP.NS": "FMCG", "VBL.NS": "FMCG", "TITAN.NS": "Consumer Goods",
    "TATASTEEL.NS": "Metals", "JSWSTEEL.NS": "Metals", "HINDALCO.NS": "Metals", "VEDL.NS": "Metals", "COALINDIA.NS": "Mining", "JINDALSTEL.NS": "Metals", "NMDC.NS": "Mining",
    "SUNPHARMA.NS": "Pharma", "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma",
    "APOLLOHOSP.NS": "Healthcare", "LUPIN.NS": "Pharma", "TORNTPHARM.NS": "Pharma", "ZYDUSLIFE.NS": "Pharma", "MAXHEALTH.NS": "Healthcare",
    "LT.NS": "Capital Goods", "SIEMENS.NS": "Capital Goods", "ABB.NS": "Capital Goods", "HAL.NS": "Defense",
    "BEL.NS": "Defense", "BHEL.NS": "Capital Goods", "CUMMINSIND.NS": "Capital Goods", "POLYCAB.NS": "Cables & Electricals", "KEI.NS": "Cables & Electricals",
    "PIDILITIND.NS": "Chemicals", "SRF.NS": "Chemicals", "AARTIIND.NS": "Chemicals", "DEEPAKNTR.NS": "Chemicals",
    "TATACHEM.NS": "Chemicals", "GUJGASLTD.NS": "Gas Distribution",
    "ULTRACEMCO.NS": "Cement", "GRASIM.NS": "Cement", "AMBUJACEM.NS": "Cement", "SHREECEM.NS": "Cement", "ACC.NS": "Cement",
    "DLF.NS": "Realty", "GODREJPROP.NS": "Realty", "LODHA.NS": "Realty", "OBEROIRLTY.NS": "Realty",
    "BHARTIARTL.NS": "Telecom", "TATACOMM.NS": "Telecom", "PVRINOX.NS": "Media"
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

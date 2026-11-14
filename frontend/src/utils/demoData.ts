/**
 * AURA-NSE Pro Institutional Demo & Offline Fallback Data Engine.
 *
 * Ensures the web application renders rich, interactive, realistic market
 * intelligence even when previewed on GitHub Pages without an active local backend.
 */

export const DEMO_MARKET_STATUS = {
  status: "MARKET_CLOSED",
  session: "POST_MARKET",
  current_time_ist: "18:30:00 IST",
  is_trading_day: true,
  next_open_time: "09:15:00 IST",
  exchange: "National Stock Exchange of India (NSE)",
};

export const DEMO_REGIME = {
  regime_label: "GREEN",
  nifty_close: 25144.60,
  nifty_20_ema: 24980.20,
  nifty_50_ema: 24710.50,
  india_vix: 14.82,
  vix_5d_change: -0.65,
  sizing_multiplier: 1.0,
  top_leading_sectors: ["Banking", "Capital Goods", "IT", "Automobiles"],
  regime_notes: "Benchmark consolidating firmly above 20-EMA with benign India VIX below 15. Standard position sizing permitted.",
};

export const DEMO_FII_DII = {
  date: "13-Nov-2026",
  fii: {
    gross_buy_cr: 18339.57,
    gross_sell_cr: 12603.02,
    net_cr: 5736.55,
    action: "NET_BUYER",
  },
  dii: {
    gross_buy_cr: 11745.95,
    gross_sell_cr: 13999.53,
    net_cr: -2253.58,
    action: "NET_SELLER",
  },
  combined_net_cr: 3482.97,
  institutional_sentiment: "STRONG_BULLISH",
  bias_narrative: "FII aggressive accumulation (+₹5,736.55 Cr) absorbed mild domestic profit booking, establishing strong institutional support.",
  derivatives: {
    fii_index_long_ratio_pct: 54.2,
    fii_options_sentiment: "BULLISH",
    market_pcr: 1.12,
  },
  timestamp: "2026-11-14 18:30:00 IST",
  source: "NSE_OFFICIAL",
};

export const DEMO_APPROVED_PREDICTIONS = [
  {
    id: 101,
    symbol: "RELIANCE.NS",
    horizon: "SWING",
    setup_tag: "EMA_Pullback",
    status: "OPEN",
    planned_entry_price: 1520.0,
    entry_price: 1520.0,
    stop_loss: 1485.0,
    target_price: 1595.0,
    quantity: 35,
    capital_required: 53200.0,
    total_risk_rupees: 1225.0,
    time_limit_days: 10,
    win_probability: 0.68,
    win_prob_lower: 0.62,
    win_prob_upper: 0.74,
    ev_r: 0.42,
    charges_rupees: 184.20,
    verdict: "APPROVED",
    llm_confidence: 85.0,
    reasoning: {
      bull_arguments: [
        "Tested 20-day EMA on above-average volume with bullish hammer candle.",
        "Refining margins expanding; telecom ARPU expected to trend higher.",
        "Energy sector displaying positive relative strength vs NIFTY 50.",
      ],
      bear_arguments: [
        "Overhead resistance at previous swing high ₹1,610.",
        "Global crude oil fluctuations may introduce short-term volatility.",
      ],
      invalidation_criteria: "Daily close below ₹1,485 or breach of swing low.",
    },
    indicators: {
      rsi_14: 52.4,
      adx_14: 26.8,
      supertrend: "BULLISH",
      delivery_pct: 58.2,
    },
    audit_hash: "a4f91b72e90c33d1b827e69f41a87c12",
    created_at: "2026-11-14T09:00:00",
  },
  {
    id: 102,
    symbol: "TCS.NS",
    horizon: "SWING",
    setup_tag: "VCP_Contraction",
    status: "OPEN",
    planned_entry_price: 4180.0,
    entry_price: 4180.0,
    stop_loss: 4095.0,
    target_price: 4365.0,
    quantity: 12,
    capital_required: 50160.0,
    total_risk_rupees: 1020.0,
    time_limit_days: 10,
    win_probability: 0.62,
    win_prob_lower: 0.55,
    win_prob_upper: 0.69,
    ev_r: 0.38,
    charges_rupees: 172.50,
    verdict: "APPROVED",
    llm_confidence: 82.0,
    reasoning: {
      bull_arguments: [
        "3-stage volatility contraction pattern with volume drying up on pullbacks.",
        "Tier-1 IT sector outperformance amid stabilizing global deal pipelines.",
        "Trading comfortably above ascending 50-day and 200-day moving averages.",
      ],
      bear_arguments: [
        "INR exchange rate fluctuations could influence near-term sentiment.",
      ],
      invalidation_criteria: "Breach of ₹4,095 swing support level.",
    },
    indicators: {
      rsi_14: 56.1,
      adx_14: 24.3,
      supertrend: "BULLISH",
      delivery_pct: 64.1,
    },
    audit_hash: "91b2c4e8f1708a329d714bc58231ea70",
    created_at: "2026-11-14T09:00:00",
  },
];

export const DEMO_REJECTED_CANDIDATES = [
  { symbol: "WIPRO.NS", reason: "Failed ML Expected Value Gate: Win Prob 41.2% (< 45%), EV_R 0.12R (< 0.20R)" },
  { symbol: "TATAMOTORS.NS", reason: "Anti-Chase Rule: Gap +2.4% above planned entry exceeds max 1.0% threshold" },
  { symbol: "VEDL.NS", reason: "Commodity volatility filter: Sector momentum negative vs NIFTY benchmark" },
];

export const DEMO_ACCURACY_TRACKER = {
  total_predictions: 42,
  open_trades_count: 2,
  total_graded: 40,
  true_predictions_count: 26,
  false_predictions_count: 12,
  neutral_expired_count: 2,
  true_prediction_rate_pct: 65.0,
  false_prediction_rate_pct: 30.0,
  avg_expectancy_r: 0.44,
  improvement_rate_pct: 7.8,
  has_sufficient_sample: true,
  status_summary: "26 True / 12 False (65.0% Accuracy)",
  history: [
    {
      id: 98,
      symbol: "LT.NS",
      entry_date: "2026-11-04",
      entry_price: 3620.0,
      exit_price: 3780.0,
      status: "TARGET_HIT",
      is_true_prediction: true,
      net_pnl_rupees: 4560.0,
      net_pnl_r: 1.95,
    },
    {
      id: 97,
      symbol: "HDFCBANK.NS",
      entry_date: "2026-11-03",
      entry_price: 1740.0,
      exit_price: 1810.0,
      status: "TARGET_HIT",
      is_true_prediction: true,
      net_pnl_rupees: 3820.0,
      net_pnl_r: 1.88,
    },
    {
      id: 96,
      symbol: "INFY.NS",
      entry_date: "2026-10-30",
      entry_price: 1860.0,
      exit_price: 1825.0,
      status: "STOP_LOSS_HIT",
      is_true_prediction: false,
      net_pnl_rupees: -1680.0,
      net_pnl_r: -1.02,
    },
    {
      id: 95,
      symbol: "BHARTIARTL.NS",
      entry_date: "2026-10-28",
      entry_price: 1610.0,
      exit_price: 1685.0,
      status: "TARGET_HIT",
      is_true_prediction: true,
      net_pnl_rupees: 3650.0,
      net_pnl_r: 1.82,
    },
  ],
};

export const DEMO_STRESS_METRICS = {
  total_trades: 40,
  is_sufficient_sample: true,
  win_rate_pct: 65.0,
  net_expectancy_r: 0.44,
  profit_factor: 2.18,
  max_drawdown_pct: 4.8,
  sharpe_ratio: 1.86,
  sortino_ratio: 2.74,
  cost_drag_pct: 6.8,
  equity_curve: [
    { day: 0, equity: 100000.0, drawdown_pct: 0.0 },
    { day: 5, equity: 103200.0, drawdown_pct: 0.0 },
    { day: 10, equity: 102400.0, drawdown_pct: 0.77 },
    { day: 15, equity: 106800.0, drawdown_pct: 0.0 },
    { day: 20, equity: 105900.0, drawdown_pct: 0.84 },
    { day: 25, equity: 110400.0, drawdown_pct: 0.0 },
    { day: 30, equity: 114250.0, drawdown_pct: 0.0 },
  ],
  scorecard: {
    is_ready: true,
    verdict: "INSTITUTIONAL GRADE READY: Positive R-expectancy (+0.44R) and robust drawdown control (< 5%).",
  },
};

export const DEMO_TELEGRAM_ALERTS = [
  {
    id: 1,
    timestamp: "2026-11-14 18:30:12 IST",
    channel: "TELEGRAM",
    message: "📋 AURA EOD Bhavcopy Reconciliation Complete\nDate: 2026-11-13\nStatus: 100% Price Match Verified\n0 drift flags detected across universe.",
  },
  {
    id: 2,
    timestamp: "2026-11-14 15:45:08 IST",
    channel: "TELEGRAM",
    message: "🏁 AURA 15:45 PM IST Post-Market Grading\nActive positions graded against daily closing prices.\nAll risk boundaries maintained.",
  },
  {
    id: 3,
    timestamp: "2026-11-14 09:00:15 IST",
    channel: "TELEGRAM",
    message: "🎯 AURA Pre-Market Signal Briefing\nRegime: GREEN | VIX: 14.8\nApproved Setups: RELIANCE.NS (1520), TCS.NS (4180)\nStrict stop loss and 1.8R+ profit targets active.",
  },
];

export const DEMO_VOICE_BRIEFING =
  "Good morning investor. AURA institutional pre-market scan is complete. Macro regime is evaluated at GREEN with benchmark NIFTY consolidating firmly above its 20-day exponential moving average and India VIX subdued at 14.8. Two high-conviction setups cleared all multi-persona LLM gates: Reliance Industries on a 20-EMA pullback and Tata Consultancy Services on a multi-week volatility contraction. Standard position sizing is approved. Manage stops diligently.";

export const DEMO_SECTOR_MATRIX = {
  benchmark: {
    ticker: "^NSEI",
    name: "NIFTY 50",
    close: 25144.60,
    change_1d_pct: 0.35,
    change_1m_pct: 1.75,
  },
  sectors_count: 8,
  sectors: [
    {
      sector: "Realty",
      ticker: "^CNXREALTY",
      change_1d_pct: 1.45,
      change_1m_pct: 5.10,
      relative_strength: 3.35,
      status: "LEADING",
      constituent_count: 4,
      constituents: ["DLF.NS", "GODREJPROP.NS", "LODHA.NS", "OBEROIRLTY.NS"],
    },
    {
      sector: "Banking",
      ticker: "^NSEBANK",
      change_1d_pct: 0.85,
      change_1m_pct: 4.20,
      relative_strength: 2.45,
      status: "LEADING",
      constituent_count: 8,
      constituents: ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    },
    {
      sector: "Auto",
      ticker: "^CNXAUTO",
      change_1d_pct: 1.12,
      change_1m_pct: 3.85,
      relative_strength: 2.10,
      status: "LEADING",
      constituent_count: 7,
      constituents: ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "BHARATFORG.NS"],
    },
    {
      sector: "IT",
      ticker: "^CNXIT",
      change_1d_pct: 0.45,
      change_1m_pct: 2.65,
      relative_strength: 0.90,
      status: "IMPROVING",
      constituent_count: 9,
      constituents: ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "LTIM.NS"],
    },
    {
      sector: "Energy",
      ticker: "^CNXENERGY",
      change_1d_pct: 0.30,
      change_1m_pct: 1.95,
      relative_strength: 0.20,
      status: "IMPROVING",
      constituent_count: 9,
      constituents: ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "TATAPOWER.NS"],
    },
    {
      sector: "Pharma",
      ticker: "^CNXPHARMA",
      change_1d_pct: -0.25,
      change_1m_pct: 1.40,
      relative_strength: -0.35,
      status: "WEAKENING",
      constituent_count: 9,
      constituents: ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS"],
    },
    {
      sector: "FMCG",
      ticker: "^CNXFMCG",
      change_1d_pct: -0.15,
      change_1m_pct: 0.85,
      relative_strength: -0.90,
      status: "WEAKENING",
      constituent_count: 10,
      constituents: ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"],
    },
    {
      sector: "Metals",
      ticker: "^CNXMETAL",
      change_1d_pct: -0.95,
      change_1m_pct: -0.80,
      relative_strength: -2.55,
      status: "LAGGING",
      constituent_count: 7,
      constituents: ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS"],
    },
  ],
  top_leading: ["Realty", "Banking", "Auto"],
  timestamp: "2026-11-14 18:30:00 IST",
};


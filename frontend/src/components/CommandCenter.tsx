import React, { useState } from "react";
import {
  TrendingUp,
  Shield,
  AlertTriangle,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Info,
  ChevronDown,
  ChevronUp,
  Bell,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Layers,
  Send,
  Copy,
  Check,
  Calculator,
  Search,
  Download,
  PieChart,
  Activity,
  Lock,
  Gem,
  Sparkles,
  Flame,
} from "lucide-react";

import { TradingViewChartModal } from "./TradingViewChartModal";
import { downloadKiteBasketJson } from "../utils/kiteBasket";

interface CommandCenterProps {
  predictions: any[];
  tier2Watchlist?: any[];
  rejectedCandidates?: any[];
  marketStatus: any;
  regime: any;
  fiiDii?: any;
  accuracyTracker?: any;
  telegramAlerts?: any[];
  sectorMatrix?: any;
  valuePicksData?: any;
  onRefreshScan: () => void;
  onRunValueScan?: (mode?: string) => void;
  isLoading: boolean;
  isLoadingValueScan?: boolean;
  onCopyTicket?: (ticket: string) => void;
  initialTab?: "value" | "approved" | "rejected" | "accuracy" | "alerts" | "sectors";
}

export const CommandCenter: React.FC<CommandCenterProps> = ({
  predictions,
  tier2Watchlist = [],
  rejectedCandidates = [],
  marketStatus,
  regime,
  fiiDii,
  accuracyTracker,
  telegramAlerts = [],
  sectorMatrix,
  valuePicksData,
  onRefreshScan,
  onRunValueScan,
  isLoading,
  isLoadingValueScan = false,
  initialTab = "value",
}) => {
  const [activeTab, setActiveTab] = useState<"approved" | "rejected" | "accuracy" | "alerts" | "sectors" | "value">(initialTab);

  React.useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [showFiiDiiModal, setShowFiiDiiModal] = useState<boolean>(false);
  const [showCalculatorModal, setShowCalculatorModal] = useState<boolean>(false);
  const [showSectorModal, setShowSectorModal] = useState<boolean>(false);
  const [selectedChartCandidate, setSelectedChartCandidate] = useState<any | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [copiedThesisSymbol, setCopiedThesisSymbol] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Position Sizing Calculator State
  const [calcCapital, setCalcCapital] = useState<number>(100000);
  const [calcRiskPct, setCalcRiskPct] = useState<number>(1.0);
  const [calcEntry, setCalcEntry] = useState<number>(1500);
  const [calcStop, setCalcStop] = useState<number>(1465);
  const [calcTarget, setCalcTarget] = useState<number>(1575);

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const isDemoOrPublic = predictions.some(
    (p: any) => p.is_demo === true || p.audit_hash?.startsWith("demo_") || (p.id >= 100 && p.id <= 105)
  );

  const handleCopyBrokerTicket = async (p: any) => {
    if (isDemoOrPublic) {
      alert("Order Ticket Locked: Trade tickets and one-click execution are disabled on public preview to comply with SEBI non-broadcast guidelines. Tickets are accessible exclusively on private authenticated single-user deployments.");
      return;
    }

    const isStatic = typeof window !== "undefined" && (
      window.location.hostname.includes("github.io") ||
      window.location.hostname.includes("pages.dev")
    );

    if (isStatic) {
      const ticket = [
        "AURA ORDER TICKET (Decision Support):",
        `BUY ${p.symbol} EQ`,
        `Quantity: ${p.quantity || 1} shares`,
        `Entry Limit: ₹${Number(p.entry_price || p.planned_entry_price || 0).toFixed(2)}`,
        `Stop Loss Trigger: ₹${Number(p.stop_loss || 0).toFixed(2)}`,
        `Target Limit: ₹${Number(p.target_price || 0).toFixed(2)}`,
        `Zerodha GTT Trigger: ₹${Number(p.stop_loss || 0).toFixed(2)}`,
        `Horizon: ${p.time_limit_days || 10} Days (Swing)`,
        `Note: Educational decision support only. Not financial advice.`,
      ].join("\n");
      try {
        await navigator.clipboard.writeText(ticket);
        setCopiedId(p.id);
        setTimeout(() => setCopiedId(null), 2500);
      } catch {
        alert("Clipboard permission denied.");
      }
      return;
    }

    try {
      const res = await fetch("/api/orders/generate-ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prediction_id: p.id }),
      });
      if (res.ok) {
        const data = await res.json();
        navigator.clipboard.writeText(data.ticket);
        setCopiedId(p.id);
        setTimeout(() => setCopiedId(null), 2500);
      } else {
        alert("Failed to generate order ticket from authenticated backend.");
      }
    } catch {
      alert("Backend unreachable. Cannot generate order ticket.");
    }
  };

  const fiiNet = fiiDii?.fii?.net_cr ?? 5736.55;
  const diiNet = fiiDii?.dii?.net_cr ?? -2253.58;
  const combinedNet = fiiDii?.combined_net_cr ?? (fiiNet + diiNet);
  const isNetPositive = combinedNet >= 0;

  // Filtered lists
  const filteredPredictions = predictions.filter((p) =>
    p.symbol.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const filteredRejected = rejectedCandidates.filter((r) =>
    r.symbol.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const valuePicksList: any[] = valuePicksData?.value_picks || valuePicksData?.picks || [];
  const filteredValuePicks = valuePicksList.filter((v: any) =>
    (v.symbol || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (v.sector || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCopyValueThesis = async (v: any) => {
    const f = v.fundamentals || {};
    const text = [
      `💎 AURA INSTITUTIONAL VALUE THESIS — ${v.symbol}`,
      `Sector: ${v.sector || "N/A"} | Horizon: 1 to 3+ Years`,
      `Current Market Price: ₹${Number(v.current_price).toFixed(2)}`,
      `Intrinsic Fair Worth (Mid): ₹${Number(v.fair_value_mid).toFixed(2)} (Range: ₹${Number(v.fair_value_min).toFixed(2)} - ₹${Number(v.fair_value_max).toFixed(2)})`,
      `Margin of Safety Discount: +${Number(v.margin_of_safety_pct).toFixed(1)}%`,
      `Quality Metrics: ROE: ${f.roe_pct}% | P/E: ${f.pe_ratio}x | Debt/Equity: ${f.debt_to_equity} | YoY Growth: ${f.earnings_growth_yoy_pct}%`,
      `Tranche Accumulation Plan:`,
      `  • Tranche 1 (40%): ₹${Number(v.tranche_plan?.tranche_1_initial?.price_target || v.current_price).toFixed(2)} (${v.tranche_plan?.tranche_1_initial?.trigger || "Immediate on approval"})`,
      `  • Tranche 2 (30%): ₹${Number(v.tranche_plan?.tranche_2_pullback?.price_target || 0).toFixed(2)} (${v.tranche_plan?.tranche_2_pullback?.trigger || "5% Dip"})`,
      `  • Tranche 3 (30%): ₹${Number(v.tranche_plan?.tranche_3_deep_value?.price_target || 0).toFixed(2)} (${v.tranche_plan?.tranche_3_deep_value?.trigger || "10% Dip"})`,
      `Quarterly Review Date: ${v.quarterly_review_date || "2027-02-15"}`,
      `Educational Decision Support only. Not investment advice.`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopiedThesisSymbol(v.symbol);
      setTimeout(() => setCopiedThesisSymbol(null), 2500);
    } catch {
      alert("Clipboard permission denied.");
    }
  };

  // Calculator computations
  const riskAmount = (calcCapital * calcRiskPct) / 100;
  const riskPerShare = Math.max(0.05, calcEntry - calcStop);
  const targetGainPerShare = Math.max(0.05, calcTarget - calcEntry);
  const calcShares = Math.max(1, Math.floor(riskAmount / riskPerShare));
  const calcTotalInvested = calcShares * calcEntry;
  const calcRR = (targetGainPerShare / riskPerShare).toFixed(2);
  const calcTotalPotentialProfit = calcShares * targetGainPerShare;

  return (
    <div className="space-y-6">
      {/* Top Status & Institutional Macro Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Market Status */}
        <div className="aura-card p-4 border border-gray-800/80 flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">NSE Session</div>
            <div className="text-base font-bold text-white mt-0.5 flex items-center gap-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  marketStatus?.status === "MARKET_OPEN" ? "bg-emerald-500 animate-ping" : "bg-amber-500"
                }`}
              />
              {marketStatus?.status?.replace(/_/g, " ") || "INITIALIZING"}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">IST: {marketStatus?.current_time_ist || "--:--"}</div>
          </div>
        </div>

        {/* NIFTY 50 */}
        <div className="aura-card p-4 border border-gray-800/80">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">NIFTY 50 Benchmark</div>
          <div className="text-lg font-bold text-white mt-0.5">
            ₹{regime?.nifty_close ? Number(regime.nifty_close).toLocaleString("en-IN") : "25,144"}
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5 flex gap-2">
            <span>20-EMA: ₹{regime?.nifty_20_ema ? Number(regime.nifty_20_ema).toLocaleString("en-IN") : "--"}</span>
            <span>50-EMA: ₹{regime?.nifty_50_ema ? Number(regime.nifty_50_ema).toLocaleString("en-IN") : "--"}</span>
          </div>
        </div>

        {/* India VIX */}
        <div className="aura-card p-4 border border-gray-800/80">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">India VIX Volatility</div>
          <div className="text-lg font-bold text-white mt-0.5 flex items-center gap-2">
            {regime?.india_vix || "14.8"}
            <span
              className={`text-xs px-2 py-0.5 rounded font-semibold ${
                Number(regime?.india_vix || 15) > 18
                  ? "bg-amber-950 text-amber-400 border border-amber-800"
                  : "bg-emerald-950 text-emerald-400 border border-emerald-800"
              }`}
            >
              {Number(regime?.india_vix || 15) > 18 ? "ELEVATED" : "SUBDUED"}
            </span>
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5">
            5-Day Shift: {regime?.vix_5d_change > 0 ? `+${regime.vix_5d_change}` : regime?.vix_5d_change || "0.0"}
          </div>
        </div>

        {/* FII / DII Daily Institutional Flow */}
        <div
          onClick={() => setShowFiiDiiModal(true)}
          className="aura-card p-4 border border-gray-800/80 cursor-pointer hover:border-cyan-500/50 transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">FII / DII Net Flow</div>
            <span className="text-[10px] text-cyan-400 group-hover:underline">Details &rarr;</span>
          </div>
          <div className="text-lg font-bold mt-0.5 flex items-center gap-2">
            <span className={isNetPositive ? "text-emerald-400" : "text-rose-400"}>
              {isNetPositive ? `+₹${combinedNet.toLocaleString("en-IN")} Cr` : `-₹${Math.abs(combinedNet).toLocaleString("en-IN")} Cr`}
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                isNetPositive
                  ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                  : "bg-rose-950 text-rose-400 border border-rose-800"
              }`}
            >
              {fiiDii?.institutional_sentiment?.replace(/_/g, " ") || (isNetPositive ? "BULLISH" : "BEARISH")}
            </span>
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5 truncate">
            FII: {fiiNet >= 0 ? `+${fiiNet}` : fiiNet} Cr | DII: {diiNet >= 0 ? `+${diiNet}` : diiNet} Cr
          </div>
        </div>

        {/* Leading Sectors & RS Matrix Trigger */}
        <div
          onClick={() => setShowSectorModal(true)}
          className="aura-card p-4 border border-gray-800/80 cursor-pointer hover:border-indigo-500/50 transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">NSE Sector RS</div>
            <span className="text-[10px] text-indigo-400 group-hover:underline">Heatmap &rarr;</span>
          </div>
          <div className="text-sm font-semibold text-cyan-400 mt-1 truncate">
            {sectorMatrix?.top_leading?.join(", ") || regime?.top_leading_sectors?.join(", ") || "Banking, IT, Auto"}
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5">Mansfield RS Leaders vs NIFTY</div>
        </div>
      </div>

      {/* Institutional Telemetry Strip: Macro Factors & F&O Derivatives */}
      <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1.5 text-cyan-400 font-semibold tracking-wide uppercase text-[10px]">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            Macro Transmission
          </div>
          <div className="flex items-center gap-3 text-gray-300 text-[11px]">
            <span>
              Brent: <strong className="text-white">${regime?.macro_factors?.factors?.brent_crude?.price ?? 74.2}</strong>
            </span>
            <span className="text-gray-600">|</span>
            <span>
              US 10Y: <strong className="text-white">{regime?.macro_factors?.factors?.us_10y_yield?.price ?? 4.42}%</strong>
            </span>
            <span className="text-gray-600">|</span>
            <span>
              USD/INR: <strong className="text-white">₹{regime?.macro_factors?.factors?.usdinr?.price ?? 84.45}</strong>
            </span>
            <span className="text-gray-600">|</span>
            <span className="flex items-center gap-1">
              MPI:{" "}
              <strong className={Number(regime?.macro_pressure_index || 40) >= 70 ? "text-amber-400" : "text-emerald-400"}>
                {regime?.macro_pressure_index ?? 38}/100
              </strong>
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1.5 text-indigo-400 font-semibold tracking-wide uppercase text-[10px]">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            F&O Derivatives
          </div>
          <div className="flex items-center gap-3 text-gray-300 text-[11px]">
            <span>
              NIFTY PCR: <strong className="text-emerald-400">{regime?.derivatives_telemetry?.pcr ?? 0.95}</strong>
            </span>
            <span className="text-gray-600">|</span>
            <span>
              Max Pain:{" "}
              <strong className="text-white">
                ₹{Number(regime?.derivatives_telemetry?.max_pain_strike || 24500).toLocaleString("en-IN")}
              </strong>
            </span>
            <span className="text-gray-600">|</span>
            <span>
              Put Wall:{" "}
              <strong className="text-emerald-400">
                ₹{Number(regime?.derivatives_telemetry?.put_support_wall || 24000).toLocaleString("en-IN")}
              </strong>
            </span>
            <span className="text-gray-600">|</span>
            <span>
              Call Wall:{" "}
              <strong className="text-rose-400">
                ₹{Number(regime?.derivatives_telemetry?.call_resistance_wall || 25000).toLocaleString("en-IN")}
              </strong>
            </span>
          </div>
        </div>
      </div>

      {/* Action Header & Tabs & Quick Tools */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setActiveTab("value")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "value"
                ? "bg-cyan-600 text-white shadow-sm"
                : "bg-gray-800/80 text-gray-400 hover:text-white"
            }`}
          >
            <Gem className="w-3.5 h-3.5 text-cyan-400" />
            Value Compounders ({valuePicksList.length})
          </button>
          <button
            onClick={() => setActiveTab("approved")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "approved"
                ? "bg-indigo-600 text-white shadow-sm"
                : "bg-gray-800/80 text-gray-400 hover:text-white"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5 text-indigo-400" />
            Swing Signals ({predictions.length})
            {tier2Watchlist.length > 0 && (
              <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-cyan-900/50 text-cyan-300 border border-cyan-800/40">
                +{tier2Watchlist.length} Watchlist
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("sectors")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "sectors"
                ? "bg-indigo-600 text-white shadow-sm"
                : "bg-gray-800/80 text-gray-400 hover:text-white"
            }`}
          >
            <PieChart className="w-3.5 h-3.5 text-indigo-400" />
            Sector Heatmap
          </button>
          <button
            onClick={() => setActiveTab("rejected")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "rejected"
                ? "bg-indigo-600 text-white shadow-sm"
                : "bg-gray-800/80 text-gray-400 hover:text-white"
            }`}
          >
            <Shield className="w-3.5 h-3.5 text-gray-400" />
            Screened Out ({rejectedCandidates.length})
          </button>
          <button
            onClick={() => setActiveTab("alerts")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "alerts"
                ? "bg-indigo-600 text-white shadow-sm"
                : "bg-gray-800/80 text-gray-400 hover:text-white"
            }`}
          >
            <Bell className="w-3.5 h-3.5 text-amber-400" />
            Telegram Stream ({telegramAlerts.length})
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
          {/* Quick Search */}
          <div className="relative flex-1 sm:w-44">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter ticker..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-900 border border-gray-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Export All Approved to Kite Basket JSON */}
          {predictions.length > 0 && (
            <button
              onClick={() => downloadKiteBasketJson(predictions)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-indigo-950/80 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 transition-all shadow-md"
              title="Download official Zerodha Kite Basket JSON file for 1-click import into Kite"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Export Kite Basket</span>
            </button>
          )}

          {/* Sizing Tool Modal Trigger */}
          <button
            onClick={() => setShowCalculatorModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-cyan-400 border border-cyan-800/40 transition-all"
            title="Open Position Sizing Calculator"
          >
            <Calculator className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Risk Calc</span>
          </button>

          {/* Undervalued Intrinsic Scan Trigger */}
          <button
            onClick={() => {
              setActiveTab("value");
              if (onRunValueScan) onRunValueScan();
            }}
            disabled={isLoadingValueScan}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold bg-cyan-700 hover:bg-cyan-600 text-white transition-all disabled:opacity-50 shadow-lg shadow-cyan-700/20"
            title="Scan NSE equities trading below their intrinsic fair worth with Margin of Safety & dispatch dedicated Telegram alert"
          >
            <Gem className={`w-3.5 h-3.5 ${isLoadingValueScan ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">{isLoadingValueScan ? "Valuing..." : "Scan Undervalued"}</span>
            <span className="sm:hidden">Value</span>
          </button>

          {/* Pre-Market Scan Trigger */}
          <button
            onClick={onRefreshScan}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all disabled:opacity-50 shadow-lg shadow-emerald-600/20"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            {isLoading ? "Running Screen..." : "Run 9:00 AM Scan"}
          </button>
        </div>
      </div>

      {/* Tab: Approved Predictions */}
      {activeTab === "approved" && (
        <div className="space-y-4">
          {filteredPredictions.length === 0 ? (
            <div className="aura-card p-6 border border-gray-800/80 bg-gray-900/40 rounded-xl">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-8 h-8 text-indigo-400 opacity-80 flex-shrink-0" />
                  <div>
                    <h3 className="text-sm font-bold text-white">Tier-1 Breakout Triggers: 0 Approved (Volume Expansion Dry)</h3>
                    <p className="text-xs text-gray-400 mt-0.5">
                      No immediate breakout setup passed all institutional risk-reward and volume explosion gates. Capital preservation active.
                    </p>
                  </div>
                </div>
                <button
                  onClick={onRefreshScan}
                  disabled={isLoading}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white flex-shrink-0"
                >
                  Refresh Scan
                </button>
              </div>
            </div>
          ) : (
            filteredPredictions.map((p) => {
              const isExpanded = expandedId === p.id;
              const isCopied = copiedId === p.id;
              const riskPerShare = Math.max(0.1, p.entry_price - p.stop_loss);
              const rewardPerShare = Math.max(0.1, p.target_price - p.entry_price);
              const rrRatio = (rewardPerShare / riskPerShare).toFixed(2);

              return (
                <div key={p.id} className="aura-card p-5 border border-gray-800/80 aura-card-hover transition-all">
                  <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                    {/* Symbol & Horizon */}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xl font-bold text-white tracking-wide">{p.symbol}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">
                          {p.horizon}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-gray-800 text-gray-300">
                          Setup: {p.setup_tag}
                        </span>
                        {p.is_demo && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-amber-950 text-amber-300 border border-amber-700 animate-pulse">
                            DEMO, NOT LIVE
                          </span>
                        )}
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            p.status === "OPEN"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : "bg-gray-800 text-gray-400"
                          }`}
                        >
                          {p.status}
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        Time Horizon: <strong>{p.time_limit_days} Trading Days</strong> | Quantity:{" "}
                        <strong className="text-white">{p.quantity} Shares</strong> | Capital:{" "}
                        <strong className="text-white">₹{p.capital_required?.toLocaleString("en-IN")}</strong>
                      </div>
                    </div>

                    {/* Trade Levels */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                      <div className="bg-gray-900/80 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-gray-400 uppercase font-semibold">Entry (Limit)</div>
                        <div className="text-sm font-bold text-white mt-0.5">₹{p.entry_price}</div>
                      </div>
                      <div className="bg-gray-900/80 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-rose-400 uppercase font-semibold">Stop Loss</div>
                        <div className="text-sm font-bold text-rose-400 mt-0.5">₹{p.stop_loss}</div>
                      </div>
                      <div className="bg-gray-900/80 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-emerald-400 uppercase font-semibold">Target (1.8R+)</div>
                        <div className="text-sm font-bold text-emerald-400 mt-0.5">₹{p.target_price}</div>
                      </div>
                      <div className="bg-gray-900/80 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-cyan-400 uppercase font-semibold">Win Prob (ML)</div>
                        <div className="text-sm font-bold text-cyan-400 mt-0.5">
                          {(p.win_probability * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons: Live Chart, Kite Export, Copy, Expand */}
                    <div className="flex flex-wrap items-center gap-2 self-end lg:self-center">
                      {/* Live TradingView Chart Modal Trigger */}
                      <button
                        onClick={() => setSelectedChartCandidate(p)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-950/80 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 flex items-center gap-1.5 transition-all shadow-sm"
                        title="Open interactive TradingView candlestick chart"
                      >
                        <Activity className="w-3.5 h-3.5 text-indigo-400" />
                        Live Chart
                      </button>

                      {/* Download Individual Kite Basket JSON */}
                      <button
                        onClick={() => downloadKiteBasketJson([p], `${p.symbol.replace(".NS","")}_kite_basket.json`)}
                        className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 flex items-center gap-1 transition-all"
                        title="Download Zerodha Kite Basket JSON for this stock"
                      >
                        <Download className="w-3.5 h-3.5 text-amber-400" />
                        Kite JSON
                      </button>

                      {/* Copy Order Ticket (Gated on Public Demo) */}
                      {isDemoOrPublic ? (
                        <span
                          className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-900 text-gray-500 border border-gray-800 flex items-center gap-1 cursor-not-allowed"
                          title="Trade ticket generation locked on public preview (SEBI Personal Use Compliance)"
                        >
                          <Lock className="w-3.5 h-3.5 text-gray-500" />
                          Private Lock
                        </span>
                      ) : (
                        <button
                          onClick={() => handleCopyBrokerTicket(p)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                            isCopied
                              ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/30"
                              : "bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700"
                          }`}
                          title="Copy pre-formatted order ticket for Zerodha Kite / Groww / Dhan"
                        >
                          {isCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                          {isCopied ? "Copied!" : "Copy GTT"}
                        </button>
                      )}

                      {/* Expand Bull/Bear Audit */}
                      <button
                        onClick={() => toggleExpand(p.id)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-300 flex items-center gap-1.5 transition-all"
                      >
                        {isExpanded ? "Hide Audit" : "Audit"}
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  {/* VISUAL RISK:REWARD GAUGE BAR */}
                  <div className="mt-4 pt-3 border-t border-gray-800/60">
                    <div className="flex items-center justify-between text-[11px] mb-1.5 text-gray-400">
                      <span className="flex items-center gap-1 text-rose-400 font-medium">
                        Stop: ₹{p.stop_loss} (-₹{riskPerShare.toFixed(1)} / -1.0R)
                      </span>
                      <span className="px-2 py-0.5 rounded bg-gray-900 border border-gray-700 text-cyan-300 font-bold">
                        R:R = 1 : {rrRatio}R
                      </span>
                      <span className="flex items-center gap-1 text-emerald-400 font-medium">
                        Target: ₹{p.target_price} (+₹{rewardPerShare.toFixed(1)} / +{rrRatio}R)
                      </span>
                    </div>

                    {/* Gradient Progress Bar */}
                    <div className="w-full h-2.5 rounded-full bg-gray-950 border border-gray-800 flex overflow-hidden">
                      <div className="h-full bg-rose-500/80 w-[30%]" title="Risk zone" />
                      <div className="h-full w-1.5 bg-sky-400 shadow-[0_0_8px_#38bdf8]" title="Entry Price" />
                      <div className="h-full bg-emerald-500/80 flex-1" title="Reward zone" />
                    </div>
                  </div>

                  {/* Expanded Institutional Audit Card */}
                  {isExpanded && (
                    <div className="mt-5 pt-5 border-t border-gray-800 space-y-4 text-xs animate-in fade-in">
                      {/* Bull / Bear Debate Arguments */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-900/40">
                          <div className="font-semibold text-emerald-400 mb-2 flex items-center gap-1.5">
                            <TrendingUp className="w-3.5 h-3.5" /> AURA Bull Catalysts
                          </div>
                          <ul className="space-y-1.5 text-gray-300 list-disc list-inside">
                            {p.reasoning?.bull_arguments?.map((arg: string, i: number) => (
                              <li key={i}>{arg}</li>
                            )) || <li>Technical momentum and volume confirmation above key moving averages.</li>}
                          </ul>
                        </div>

                        <div className="p-3.5 rounded-lg bg-rose-950/20 border border-rose-900/40">
                          <div className="font-semibold text-rose-400 mb-2 flex items-center gap-1.5">
                            <Shield className="w-3.5 h-3.5" /> Bear Risks & Red Flags
                          </div>
                          <ul className="space-y-1.5 text-gray-300 list-disc list-inside">
                            {p.reasoning?.bear_arguments?.map((arg: string, i: number) => (
                              <li key={i}>{arg}</li>
                            )) || <li>Overhead resistance near recent swing high; broader market sensitivity.</li>}
                          </ul>
                        </div>
                      </div>

                      {/* Itemized Indian Statutory Deductions */}
                      <div className="p-3.5 rounded-lg bg-gray-900/70 border border-gray-800">
                        <div className="font-semibold text-gray-300 mb-2 flex items-center gap-1.5">
                          <Info className="w-3.5 h-3.5 text-cyan-400" /> Statutory & Brokerage Deductions Breakdown
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-center text-[11px]">
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">Capital Req.</span>
                            <span className="font-bold text-white">₹{p.capital_required}</span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">Est. Charges</span>
                            <span className="font-bold text-amber-400">₹{p.charges_rupees || 244.5}</span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">STT (0.1%)</span>
                            <span className="font-bold text-gray-300">
                              ₹{((p.capital_required * 0.002) || 40).toFixed(1)}
                            </span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">Stamp Duty</span>
                            <span className="font-bold text-gray-300">0.015%</span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">DP Fee</span>
                            <span className="font-bold text-gray-300">₹15.93</span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">GST 18%</span>
                            <span className="font-bold text-gray-300">Applied</span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">Net R:R</span>
                            <span className="font-bold text-emerald-400">&gt; 1.80</span>
                          </div>
                        </div>
                      </div>

                      {/* Invalidation Trigger */}
                      <div className="text-[11px] text-gray-400 flex items-center gap-2">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                        <span>
                          <strong>Thesis Invalidation:</strong>{" "}
                          {p.reasoning?.invalidation_criteria || "Close below 20-EMA or breach of stop loss."}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}

          {/* Tier-2 Momentum Watchlist Section (Always visible if watchlist candidates exist) */}
          {tier2Watchlist && tier2Watchlist.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-gray-800/80">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Flame className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-white">
                    Tier-2 Momentum Watchlist — Setting Up ({tier2Watchlist.length} Leaders)
                  </h3>
                </div>
                <span className="text-[11px] text-gray-400 bg-gray-900/80 px-2.5 py-1 rounded border border-gray-800">
                  Uptrend + Institutional RS Alpha (Consolidating near Breakout)
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {tier2Watchlist.map((item: any, idx: number) => {
                  const cleanSym = String(item.symbol || "").replace(".NS", "");
                  return (
                    <div
                      key={item.symbol || idx}
                      className="aura-card p-4 border border-cyan-900/40 bg-gradient-to-br from-gray-900/90 to-gray-950/90 rounded-xl space-y-3 relative overflow-hidden"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-bold text-cyan-400">#{idx + 1}</span>
                            <span className="text-sm font-extrabold text-white">{cleanSym}</span>
                          </div>
                          <span className="text-[11px] text-gray-400">LTP: ₹{item.current_price?.toLocaleString("en-IN") || item.current_price}</span>
                        </div>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
                          RS: +{Number(item.rs_vs_nifty_20d || 0).toFixed(1)}% vs NIFTY
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] bg-gray-950/60 p-2.5 rounded-lg border border-gray-800/60">
                        <div>
                          <span className="text-gray-500 block text-[10px]">Breakout Trigger</span>
                          <span className="font-bold text-cyan-300">₹{item.watch_trigger}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 block text-[10px]">20-EMA Support</span>
                          <span className="font-bold text-gray-300">₹{item.ema_20}</span>
                        </div>
                      </div>

                      <p className="text-[11px] text-gray-400 italic line-clamp-2">
                        {item.tier_2_reason || "Consolidating near 20-day high with institutional accumulation"}
                      </p>

                      <div className="flex items-center justify-between text-[10px] text-gray-500 pt-1 border-t border-gray-900">
                        <span>RSI: {Number(item.rsi_14 || 50).toFixed(0)}</span>
                        <span>Vol Ratio: {Number(item.volume_ratio || 1).toFixed(2)}x</span>
                        <span className="text-cyan-400 font-semibold">Tier-2 Radar</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Sector Heatmap & Mansfield Relative Strength Matrix */}
      {activeTab === "sectors" && (
        <div className="space-y-5 animate-in fade-in">
          <div className="aura-card p-5 border border-gray-800 space-y-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-gray-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <PieChart className="w-4 h-4 text-indigo-400" />
                  NSE Sector Relative Strength Matrix vs NIFTY 50
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Mansfield Relative Strength isolates institutional capital rotation. Prefer longs exclusively in LEADING sectors.
                </p>
              </div>
              <div className="text-xs text-gray-400 bg-gray-900 px-3 py-1.5 rounded-lg border border-gray-800">
                NIFTY 50: <strong className="text-white">₹{sectorMatrix?.benchmark?.close ?? 25144}</strong> (1D: {sectorMatrix?.benchmark?.change_1d_pct ?? 0.35}%)
              </div>
            </div>

            {/* Sector Heatmap Tiles Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 pt-2">
              {(sectorMatrix?.sectors || []).map((sec: any) => {
                const isLeading = sec.status === "LEADING";
                const isImproving = sec.status === "IMPROVING";
                const isWeakening = sec.status === "WEAKENING";
                const isLagging = sec.status === "LAGGING";

                const cardBorder = isLeading
                  ? "border-emerald-700/60 bg-emerald-950/20"
                  : isImproving
                  ? "border-cyan-700/60 bg-cyan-950/20"
                  : isWeakening
                  ? "border-amber-700/60 bg-amber-950/20"
                  : "border-rose-700/60 bg-rose-950/20";

                const statusColor = isLeading
                  ? "text-emerald-400 bg-emerald-950 border-emerald-800"
                  : isImproving
                  ? "text-cyan-400 bg-cyan-950 border-cyan-800"
                  : isWeakening
                  ? "text-amber-400 bg-amber-950 border-amber-800"
                  : "text-rose-400 bg-rose-950 border-rose-800";

                return (
                  <div
                    key={sec.sector}
                    onClick={() => {
                      setSearchQuery(sec.constituents?.[0] || sec.sector);
                      setActiveTab("approved");
                    }}
                    className={`p-4 rounded-xl border ${cardBorder} hover:scale-[1.02] transition-all cursor-pointer space-y-2`}
                    title={`Click to filter stocks in ${sec.sector}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white text-sm">{sec.sector}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${statusColor}`}>
                        {sec.status}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between pt-1">
                      <div>
                        <div className="text-[10px] text-gray-400">1-Day Return</div>
                        <div className={`text-sm font-bold ${sec.change_1d_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {sec.change_1d_pct >= 0 ? `+${sec.change_1d_pct}%` : `${sec.change_1d_pct}%`}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] text-gray-400">Mansfield RS</div>
                        <div className="text-sm font-bold text-cyan-300">
                          {sec.relative_strength >= 0 ? `+${sec.relative_strength}` : `${sec.relative_strength}`}
                        </div>
                      </div>
                    </div>

                    <div className="text-[10px] text-gray-400 pt-1.5 border-t border-gray-800 truncate">
                      Top: {sec.constituents?.slice(0, 3).join(", ") || "Constituents mapped"}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Screened Out / Rejected Candidates */}
      {activeTab === "rejected" && (
        <div className="space-y-3">
          {filteredRejected.length === 0 ? (
            <div className="aura-card p-8 text-center border border-gray-800 text-xs text-gray-400">
              No screened candidates currently logged. Run the 9:00 AM scan to view full quantitative disqualification audits.
            </div>
          ) : (
            filteredRejected.map((r, i) => (
              <div key={i} className="aura-card p-3.5 border border-gray-800 flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  <XCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
                  <span className="font-bold text-white">{r.symbol}</span>
                </div>
                <div className="text-gray-400 text-right max-w-xl truncate">{r.reason}</div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab: Accuracy & Walk-Forward Improvement Tracker */}
      {activeTab === "accuracy" && (
        <div className="space-y-6">
          {/* Accuracy Scorecards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="aura-card p-4 border border-gray-800">
              <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">True Prediction Rate</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {accuracyTracker?.true_prediction_rate_pct ?? 0}%
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                {accuracyTracker?.true_predictions_count ?? 0} of {accuracyTracker?.total_graded ?? 0} Graded Trades (Target Hit)
              </div>
            </div>

            <div className="aura-card p-4 border border-gray-800">
              <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">False Prediction Rate</div>
              <div className="text-2xl font-bold text-rose-400 mt-1">
                {accuracyTracker?.false_prediction_rate_pct ?? 0}%
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                {accuracyTracker?.false_predictions_count ?? 0} Breached Stop Loss (Sent to Mistake Lab)
              </div>
            </div>

            <div className="aura-card p-4 border border-gray-800">
              <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">Expectancy per Trade</div>
              <div className="text-2xl font-bold text-cyan-400 mt-1">
                {accuracyTracker?.avg_expectancy_r > 0 ? `+${accuracyTracker?.avg_expectancy_r}R` : `${accuracyTracker?.avg_expectancy_r ?? 0}R`}
              </div>
              <div className="text-[11px] text-gray-400 mt-1">Average Return per Unit of Rupee Risked</div>
            </div>

            <div className="aura-card p-4 border border-gray-800">
              <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">Model Improvement Rate</div>
              <div className="text-2xl font-bold text-indigo-400 mt-1 flex items-center gap-1">
                {accuracyTracker?.improvement_rate_pct > 0 ? `+${accuracyTracker?.improvement_rate_pct}%` : `${accuracyTracker?.improvement_rate_pct ?? 0}%`}
                {accuracyTracker?.improvement_rate_pct >= 0 ? (
                  <ArrowUpRight className="w-5 h-5 text-emerald-400" />
                ) : (
                  <ArrowDownRight className="w-5 h-5 text-rose-400" />
                )}
              </div>
              <div className="text-[11px] text-gray-400 mt-1">Walk-Forward Accuracy Shift Post-Retraining</div>
            </div>
          </div>

          {/* Graded Trades Table */}
          <div className="aura-card p-5 border border-gray-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Target className="w-4 h-4 text-cyan-400" />
                  Entry & Exit Prediction Audit Ledger
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Tracks actual market exits against forecasted targets and stop losses to quantify model self-improvement.
                </p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded bg-gray-800 text-gray-300">
                {accuracyTracker?.total_graded ?? 0} Closed Positions
              </span>
            </div>

            {(!accuracyTracker?.history || accuracyTracker.history.length === 0) ? (
              <div className="p-8 text-center text-xs text-gray-400 border border-dashed border-gray-800 rounded-lg">
                No closed trades graded yet. Once trades hit Target, Stop Loss, or complete 10-day holding in live market sessions, their True/False outcome is cataloged here.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400 uppercase text-[10px]">
                      <th className="py-2 px-3">Symbol</th>
                      <th className="py-2 px-3">Date</th>
                      <th className="py-2 px-3">Entry Price</th>
                      <th className="py-2 px-3">Exit Price</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 px-3">Outcome</th>
                      <th className="py-2 px-3 text-right">Net P&L (₹)</th>
                      <th className="py-2 px-3 text-right">P&L (R)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800">
                    {accuracyTracker.history.map((row: any) => (
                      <tr key={row.id} className="hover:bg-gray-800/40 transition-colors">
                        <td className="py-2.5 px-3 font-bold text-white">{row.symbol}</td>
                        <td className="py-2.5 px-3 text-gray-400">{row.entry_date || "--"}</td>
                        <td className="py-2.5 px-3 text-gray-300">₹{row.entry_price}</td>
                        <td className="py-2.5 px-3 text-gray-300">₹{row.exit_price ?? "--"}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              row.status === "TARGET_HIT"
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : row.status === "STOP_LOSS_HIT"
                                ? "bg-rose-950 text-rose-400 border border-rose-800"
                                : "bg-gray-800 text-gray-400"
                            }`}
                          >
                            {row.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          {row.is_true_prediction ? (
                            <span className="text-emerald-400 font-semibold flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> TRUE
                            </span>
                          ) : (
                            <span className="text-rose-400 font-semibold flex items-center gap-1">
                              <XCircle className="w-3.5 h-3.5" /> FALSE
                            </span>
                          )}
                        </td>
                        <td
                          className={`py-2.5 px-3 text-right font-bold ${
                            (row.net_pnl_rupees || 0) >= 0 ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {(row.net_pnl_rupees || 0) >= 0 ? `+₹${row.net_pnl_rupees}` : `-₹${Math.abs(row.net_pnl_rupees)}`}
                        </td>
                        <td
                          className={`py-2.5 px-3 text-right font-bold ${
                            (row.net_pnl_r || 0) >= 0 ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {(row.net_pnl_r || 0) >= 0 ? `+${row.net_pnl_r}R` : `${row.net_pnl_r}R`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Telegram Live Alerts Stream */}
      {activeTab === "alerts" && (
        <div className="aura-card p-5 border border-gray-800 space-y-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-sky-500/20 text-sky-400 flex items-center justify-center">
                <Send className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Telegram Broadcast Stream</h3>
                <p className="text-xs text-gray-400">All alerts pushed to your private Telegram channel in real-time.</p>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded bg-sky-950 text-sky-400 text-xs font-semibold border border-sky-800">
              Live Feed
            </span>
          </div>

          {telegramAlerts.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-400 border border-dashed border-gray-800 rounded-lg">
              No Telegram alerts logged yet today. Scheduled market alerts trigger at 09:00 AM (Pre-Market), 09:15 AM (Open Check), 13:00 PM (Midday Stop), 15:45 PM (Post-Market), and 18:30 PM (EOD Recon).
            </div>
          ) : (
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {telegramAlerts.map((alt: any) => (
                <div key={alt.id} className="p-4 rounded-lg bg-gray-900/80 border border-gray-800 space-y-2">
                  <div className="flex items-center justify-between text-[11px] text-gray-400 border-b border-gray-800/60 pb-2">
                    <span className="flex items-center gap-1.5 font-semibold text-sky-400">
                      <Send className="w-3 h-3" /> Channel: {alt.channel || "TELEGRAM"}
                    </span>
                    <span>{alt.timestamp}</span>
                  </div>
                  <pre className="text-xs text-gray-200 font-sans whitespace-pre-wrap leading-relaxed">
                    {alt.message}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Undervalued Value Compounders */}
      {activeTab === "value" && (
        <div className="space-y-4">
          {/* Top Screener Banner */}
          <div className="aura-card p-5 border border-cyan-800/40 bg-gradient-to-r from-[#07131e] via-[#0d1a29] to-[#0a101d] space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cyan-900/30 pb-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
                  <Gem className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    Institutional Value & Intrinsic Worth Screener
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800">
                      Margin of Safety
                    </span>
                  </h3>
                  <p className="text-xs text-gray-400">
                    Finds companies trading at a discount to intrinsic fair value with fortress fundamentals (ROE ≥ 15%, D/E ≤ 0.8, Cap ≥ ₹2,000 Cr).
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onRunValueScan && onRunValueScan("diversified")}
                  disabled={isLoadingValueScan}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-cyan-300 border border-cyan-800/40 transition-all disabled:opacity-50"
                  title="Fast scan of sector-stratified bluechips"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingValueScan ? "animate-spin" : ""}`} />
                  Scan Bluechips
                </button>
                <button
                  onClick={() => onRunValueScan && onRunValueScan("all")}
                  disabled={isLoadingValueScan}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-all disabled:opacity-50 shadow-md"
                  title="Deep scan across all 2,760 listed NSE stocks"
                >
                  <Gem className={`w-3.5 h-3.5 ${isLoadingValueScan ? "animate-spin" : ""}`} />
                  {isLoadingValueScan ? "Scanning All Stocks..." : "Scan All Listed (2,760)"}
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-gray-300 pt-1">
              <div className="flex flex-wrap items-center gap-4">
                <span className="text-gray-400">
                  Screened: <strong className="text-white">{valuePicksData?.total_screened || 30} NSE Equities</strong>
                </span>
                <span className="text-gray-400">
                  Undervalued Found: <strong className="text-cyan-400">{valuePicksList.length} Compounders</strong>
                </span>
                <span className="text-gray-400">
                  Horizon: <strong className="text-emerald-400">1 to 3+ Years (Long-Term Compounding)</strong>
                </span>
                {valuePicksData?.scan_timestamp && (
                  <span className="text-gray-400">
                    As of: <span className="text-gray-300">{valuePicksData.scan_timestamp}</span>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-cyan-400/90 font-medium bg-cyan-950/40 px-2.5 py-1 rounded-md border border-cyan-800/40">
                <Send className="w-3 h-3" />
                <span>Dispatches dedicated alerts to Telegram independently from swing alerts</span>
              </div>
            </div>
          </div>

          {filteredValuePicks.length === 0 ? (
            <div className="aura-card p-12 text-center border border-gray-800/80 space-y-3">
              <Gem className="w-12 h-12 text-cyan-400 mx-auto opacity-60" />
              <h3 className="text-base font-bold text-white">No Undervalued Stocks Found</h3>
              <p className="text-xs text-gray-400 max-w-md mx-auto">
                No equities currently meet the strict institutional quality filters (ROE ≥ 15%, Debt/Equity ≤ 0.8) and offer a positive Margin of Safety discount.
              </p>
              <button
                onClick={onRunValueScan}
                disabled={isLoadingValueScan}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white"
              >
                Run Value Screener Now
              </button>
            </div>
          ) : (
            filteredValuePicks.map((v: any, idx: number) => {
              const f = v.fundamentals || {};
              const t1 = v.tranche_plan?.tranche_1_initial;
              const t2 = v.tranche_plan?.tranche_2_pullback;
              const t3 = v.tranche_plan?.tranche_3_deep_value;
              const isCopied = copiedThesisSymbol === v.symbol;
              const discountRupees = Math.max(0, (v.fair_value_mid || 0) - (v.current_price || 0));

              return (
                <div
                  key={v.symbol || idx}
                  className="aura-card p-5 border border-cyan-900/40 hover:border-cyan-500/50 transition-all space-y-4 bg-gray-900/60"
                >
                  {/* Card Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800/80 pb-3">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="text-lg font-bold text-white tracking-wide">{v.symbol}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800">
                        {v.sector || "EQUITY"}
                      </span>
                      {v.conviction_tier === "HIGH_CONVICTION" && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700 tracking-wider">
                          HIGH CONVICTION
                        </span>
                      )}
                      {v.conviction_tier === "QUALITY_COMPOUNDER" && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700 tracking-wider">
                          QUALITY COMPOUNDER
                        </span>
                      )}
                      {v.conviction_tier === "THIN_DISCOUNT" && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-800 text-zinc-300 border border-zinc-700 tracking-wider">
                          WATCHLIST
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-800">
                        1–3+ Years Horizon
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-800 text-gray-300 border border-gray-700">
                        Target Weight: {v.target_weight_pct || 5.0}%
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">Margin of Safety</div>
                        <div className="text-base font-bold text-emerald-400">
                          +{Number(v.margin_of_safety_pct || 0).toFixed(1)}% Discount
                        </div>
                      </div>
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400 animate-pulse" />
                    </div>
                  </div>

                  {/* Valuation vs Market Price Comparison Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-gray-950/70 border border-gray-800">
                    <div>
                      <span className="text-[10px] uppercase text-gray-400 block font-medium">Current Market Price</span>
                      <div className="text-base font-bold text-white mt-0.5">
                        ₹{Number(v.current_price || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <span className="text-[10px] text-gray-400">
                        200-SMA: ₹{Number(v.sma_200 || 0).toFixed(1)}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] uppercase text-cyan-400 block font-medium">Intrinsic Fair Worth (Mid)</span>
                      <div className="text-base font-bold text-cyan-400 mt-0.5">
                        ₹{Number(v.fair_value_mid || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <span className="text-[10px] text-gray-400">
                        Range: ₹{Number(v.fair_value_min || 0).toFixed(0)} - ₹{Number(v.fair_value_max || 0).toFixed(0)}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] uppercase text-emerald-400 block font-medium">Rupee Discount to Worth</span>
                      <div className="text-base font-bold text-emerald-400 mt-0.5">
                        +₹{discountRupees.toFixed(2)}
                      </div>
                      <span className="text-[10px] text-emerald-300">
                        Trading {(v.margin_of_safety_pct || 0).toFixed(1)}% below intrinsic
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] uppercase text-indigo-400 block font-medium">Market Capitalization</span>
                      <div className="text-base font-bold text-gray-200 mt-0.5">
                        ₹{Math.round(f.market_cap_cr || 0).toLocaleString("en-IN")} Cr
                      </div>
                      <span className="text-[10px] text-gray-400">
                        Source: {f.source || "yfinance_info"}
                      </span>
                    </div>
                  </div>

                  {/* Quality & Balance Sheet Fortress Audit */}
                  <div className="space-y-1.5">
                    <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold block">
                      Balance Sheet & Quality Fortress Gates:
                    </span>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                      <div className="p-2 rounded bg-gray-900 border border-gray-800">
                        <span className="text-gray-400 block text-[10px]">Return on Equity (ROE)</span>
                        <span className="font-bold text-emerald-400 flex items-center gap-1">
                          <Check className="w-3 h-3 text-emerald-400" />
                          {f.roe_pct !== undefined ? `${f.roe_pct}%` : "N/A"}
                        </span>
                        <span className="text-[9px] text-gray-500">Gate: ≥ 15%</span>
                      </div>

                      <div className="p-2 rounded bg-gray-900 border border-gray-800">
                        <span className="text-gray-400 block text-[10px]">Debt-to-Equity</span>
                        <span className="font-bold text-emerald-400 flex items-center gap-1">
                          <Check className="w-3 h-3 text-emerald-400" />
                          {f.debt_to_equity !== undefined ? f.debt_to_equity : "N/A"}
                        </span>
                        <span className="text-[9px] text-gray-500">Gate: ≤ 0.80</span>
                      </div>

                      <div className="p-2 rounded bg-gray-900 border border-gray-800">
                        <span className="text-gray-400 block text-[10px]">Trailing P/E Ratio</span>
                        <span className="font-bold text-cyan-300">
                          {f.pe_ratio !== undefined ? `${f.pe_ratio}x` : "N/A"}
                        </span>
                        <span className="text-[9px] text-gray-500">P/B: {f.pb_ratio ? `${f.pb_ratio}x` : "N/A"}</span>
                      </div>

                      <div className="p-2 rounded bg-gray-900 border border-gray-800">
                        <span className="text-gray-400 block text-[10px]">YoY Revenue Growth</span>
                        <span className={`font-bold ${(f.rev_growth_yoy_pct || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {(f.rev_growth_yoy_pct || 0) >= 0 ? `+${f.rev_growth_yoy_pct}%` : `${f.rev_growth_yoy_pct}%`}
                        </span>
                        <span className="text-[9px] text-gray-500">Gate: Positive</span>
                      </div>

                      <div className="p-2 rounded bg-gray-900 border border-gray-800">
                        <span className="text-gray-400 block text-[10px]">YoY Profit Growth</span>
                        <span className={`font-bold ${(f.earnings_growth_yoy_pct || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {(f.earnings_growth_yoy_pct || 0) >= 0 ? `+${f.earnings_growth_yoy_pct}%` : `${f.earnings_growth_yoy_pct}%`}
                        </span>
                        <span className="text-[9px] text-gray-500">Gate: Positive</span>
                      </div>
                    </div>
                  </div>

                  {/* 3-Tranche Accumulation Plan */}
                  <div className="space-y-1.5">
                    <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold block">
                      Institutional 3-Tranche Staggered Entry Plan:
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                      <div className="p-2.5 rounded-lg bg-gray-900/90 border border-indigo-900/50">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-indigo-300 mb-1">
                          <span>Tranche 1 ({t1?.pct || 40}%)</span>
                          <span className="text-white font-bold">₹{Number(t1?.price_target || v.current_price).toFixed(2)}</span>
                        </div>
                        <p className="text-[10px] text-gray-400 leading-tight">
                          Trigger: {t1?.trigger || "Immediate on approval"}
                        </p>
                      </div>

                      <div className="p-2.5 rounded-lg bg-gray-900/90 border border-cyan-900/50">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-cyan-300 mb-1">
                          <span>Tranche 2 ({t2?.pct || 30}%)</span>
                          <span className="text-white font-bold">₹{Number(t2?.price_target || 0).toFixed(2)}</span>
                        </div>
                        <p className="text-[10px] text-gray-400 leading-tight">
                          Trigger: {t2?.trigger || "5% dip or 50-EMA test"}
                        </p>
                      </div>

                      <div className="p-2.5 rounded-lg bg-gray-900/90 border border-emerald-900/50">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-emerald-300 mb-1">
                          <span>Tranche 3 ({t3?.pct || 30}%)</span>
                          <span className="text-white font-bold">₹{Number(t3?.price_target || 0).toFixed(2)}</span>
                        </div>
                        <p className="text-[10px] text-gray-400 leading-tight">
                          Trigger: {t3?.trigger || "10% dip or 200-SMA support"}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Institutional AI Moat & Multiple Audit */}
                  {v.gemini_audit && (
                    <div className="p-3 rounded-xl bg-zinc-950/90 border border-zinc-800 space-y-2 text-xs">
                      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-1.5">
                        <div className="flex items-center gap-1.5 font-bold text-white">
                          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                          <span>AI Moat & Quality Audit</span>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">
                          Conviction: {v.gemini_audit.ai_conviction_pct || 75}%
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-[11px] text-zinc-300">
                        <div className="space-y-0.5">
                          <span className="text-zinc-500 font-semibold uppercase text-[9px] block">Institutional Bull Thesis</span>
                          <p className="text-emerald-400/90 leading-relaxed">
                            {v.gemini_audit.bull_thesis || v.gemini_audit.moat_assessment}
                          </p>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-zinc-500 font-semibold uppercase text-[9px] block">Primary Risk & Thesis Invalidation</span>
                          <p className="text-amber-400/90 leading-relaxed">
                            {v.gemini_audit.bear_risk || "Margin compression > 300 bps or promoter pledge increase > 5%"}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Thesis Protection & Calendar Dates */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs border-t border-gray-800/80 pt-3">
                    <div className="flex flex-wrap items-center gap-4 text-gray-400 text-[11px]">
                      <span>
                        Quarterly Review: <strong className="text-gray-300">{v.quarterly_review_date || "2027-02-15"}</strong>
                      </span>
                      <span>
                        LTCG (12M Flag): <strong className="text-emerald-400">{v.tax_12m_flag_date || "2027-11-18"}</strong>
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          setSelectedChartCandidate({
                            symbol: v.symbol,
                            setup_tag: "INTRINSIC_VALUE",
                            entry_price: v.current_price,
                            stop_loss: v.sma_200,
                            target_price: v.fair_value_mid,
                            id: 9000 + idx,
                          })
                        }
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-cyan-400 border border-cyan-800/40 transition-all"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Live Chart
                      </button>

                      <button
                        onClick={() => handleCopyValueThesis(v)}
                        className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                          isCopied
                            ? "bg-emerald-600 text-white"
                            : "bg-cyan-700 hover:bg-cyan-600 text-white"
                        }`}
                      >
                        {isCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        {isCopied ? "Copied Thesis" : "Copy Value Thesis"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* TradingView Interactive Candlestick Chart Modal */}
      {selectedChartCandidate && (
        <TradingViewChartModal
          symbol={selectedChartCandidate.symbol}
          setupTag={selectedChartCandidate.setup_tag}
          entryPrice={selectedChartCandidate.entry_price}
          stopLoss={selectedChartCandidate.stop_loss}
          targetPrice={selectedChartCandidate.target_price}
          onClose={() => setSelectedChartCandidate(null)}
          onCopyTicket={() => handleCopyBrokerTicket(selectedChartCandidate)}
        />
      )}

      {/* FII / DII Institutional Breakdown Modal */}
      {showFiiDiiModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="aura-card max-w-xl w-full p-6 border border-gray-800 shadow-2xl relative space-y-5">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                  NSE Institutional Cash & Derivatives Flow
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Official reporting date: {fiiDii?.date || "13-Nov-2026"} | Source: {fiiDii?.source || "NSE Official"}
                </p>
              </div>
              <button
                onClick={() => setShowFiiDiiModal(false)}
                className="text-gray-400 hover:text-white p-1 rounded hover:bg-gray-800"
              >
                ✕
              </button>
            </div>

            {/* FII vs DII Cash Table */}
            <div className="grid grid-cols-2 gap-4">
              {/* FII Card */}
              <div className="p-4 rounded-lg bg-gray-900 border border-gray-800 space-y-2">
                <div className="text-xs uppercase tracking-wider text-gray-400 font-bold flex items-center justify-between">
                  <span>FII / FPI Cash</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                      fiiNet >= 0
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : "bg-rose-950 text-rose-400 border border-rose-800"
                    }`}
                  >
                    {fiiDii?.fii?.action || (fiiNet >= 0 ? "NET BUYER" : "NET SELLER")}
                  </span>
                </div>
                <div className="text-xl font-bold text-white">
                  {fiiNet >= 0 ? `+₹${fiiNet.toLocaleString("en-IN")} Cr` : `-₹${Math.abs(fiiNet).toLocaleString("en-IN")} Cr`}
                </div>
                <div className="text-[11px] text-gray-400 space-y-0.5 pt-1 border-t border-gray-800">
                  <div className="flex justify-between">
                    <span>Gross Buy:</span>
                    <span className="text-gray-300 font-medium">₹{fiiDii?.fii?.gross_buy_cr ?? 18339.57} Cr</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Gross Sell:</span>
                    <span className="text-gray-300 font-medium">₹{fiiDii?.fii?.gross_sell_cr ?? 12603.02} Cr</span>
                  </div>
                </div>
              </div>

              {/* DII Card */}
              <div className="p-4 rounded-lg bg-gray-900 border border-gray-800 space-y-2">
                <div className="text-xs uppercase tracking-wider text-gray-400 font-bold flex items-center justify-between">
                  <span>DII Domestic Cash</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                      diiNet >= 0
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : "bg-rose-950 text-rose-400 border border-rose-800"
                    }`}
                  >
                    {fiiDii?.dii?.action || (diiNet >= 0 ? "NET BUYER" : "NET SELLER")}
                  </span>
                </div>
                <div className="text-xl font-bold text-white">
                  {diiNet >= 0 ? `+₹${diiNet.toLocaleString("en-IN")} Cr` : `-₹${Math.abs(diiNet).toLocaleString("en-IN")} Cr`}
                </div>
                <div className="text-[11px] text-gray-400 space-y-0.5 pt-1 border-t border-gray-800">
                  <div className="flex justify-between">
                    <span>Gross Buy:</span>
                    <span className="text-gray-300 font-medium">₹{fiiDii?.dii?.gross_buy_cr ?? 11745.95} Cr</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Gross Sell:</span>
                    <span className="text-gray-300 font-medium">₹{fiiDii?.dii?.gross_sell_cr ?? 13999.53} Cr</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Derivatives & PCR Metrics */}
            <div className="p-3.5 rounded-lg bg-gray-900/60 border border-gray-800 space-y-2">
              <div className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" /> F&O Derivatives Sentiment & Options PCR
              </div>
              <div className="grid grid-cols-3 gap-3 text-center text-xs">
                <div className="p-2 bg-gray-950 rounded border border-gray-800">
                  <span className="text-gray-400 block text-[10px]">Index Long Ratio</span>
                  <span className="font-bold text-white">{fiiDii?.derivatives?.fii_index_long_ratio_pct ?? 48.5}%</span>
                </div>
                <div className="p-2 bg-gray-950 rounded border border-gray-800">
                  <span className="text-gray-400 block text-[10px]">Market PCR</span>
                  <span className="font-bold text-cyan-400">{fiiDii?.derivatives?.market_pcr ?? 1.08}</span>
                </div>
                <div className="p-2 bg-gray-950 rounded border border-gray-800">
                  <span className="text-gray-400 block text-[10px]">Combined Flow</span>
                  <span className={`font-bold ${isNetPositive ? "text-emerald-400" : "text-rose-400"}`}>
                    {isNetPositive ? `+₹${combinedNet} Cr` : `-₹${Math.abs(combinedNet)} Cr`}
                  </span>
                </div>
              </div>
            </div>

            {/* AURA Quantitative Interpretation */}
            <div className="p-3.5 rounded-lg bg-cyan-950/20 border border-cyan-900/40 text-xs text-gray-300">
              <span className="font-semibold text-cyan-400 block mb-1">AURA Institutional Flow Reading:</span>
              {fiiDii?.bias_narrative || "Aggressive institutional accumulation across Indian equities supporting swing continuation."}
            </div>

            <div className="text-right">
              <button
                onClick={() => setShowFiiDiiModal(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-white"
              >
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Position Sizing & Margin Simulator Modal */}
      {showCalculatorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="aura-card max-w-xl w-full p-6 border border-gray-800 shadow-2xl relative space-y-5">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Calculator className="w-4 h-4 text-cyan-400" />
                  Institutional Position Sizing Simulator
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Calculate exact share sizing, rupee risk, and statutory charges before entering any trade.
                </p>
              </div>
              <button
                onClick={() => setShowCalculatorModal(false)}
                className="text-gray-400 hover:text-white p-1 rounded hover:bg-gray-800"
              >
                ✕
              </button>
            </div>

            {/* Inputs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="text-gray-400 block mb-1 font-medium">Total Trading Capital (₹)</label>
                <input
                  type="number"
                  value={calcCapital}
                  onChange={(e) => setCalcCapital(Number(e.target.value))}
                  className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-white font-bold"
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1 font-medium">Max Risk per Trade (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={calcRiskPct}
                  onChange={(e) => setCalcRiskPct(Number(e.target.value))}
                  className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-white font-bold"
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1 font-medium">Entry Price (₹)</label>
                <input
                  type="number"
                  step="0.5"
                  value={calcEntry}
                  onChange={(e) => setCalcEntry(Number(e.target.value))}
                  className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-white font-bold"
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1 font-medium">Stop Loss Price (₹)</label>
                <input
                  type="number"
                  step="0.5"
                  value={calcStop}
                  onChange={(e) => setCalcStop(Number(e.target.value))}
                  className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-white font-bold"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="text-gray-400 block mb-1 font-medium">Target Price (₹)</label>
                <input
                  type="number"
                  step="0.5"
                  value={calcTarget}
                  onChange={(e) => setCalcTarget(Number(e.target.value))}
                  className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-white font-bold"
                />
              </div>
            </div>

            {/* Outputs */}
            <div className="p-4 rounded-lg bg-gray-950 border border-gray-800 space-y-3">
              <div className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
                Computed Sizing Metrics:
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="p-2.5 bg-gray-900 rounded border border-gray-800">
                  <span className="text-gray-400 block text-[10px]">Exact Shares</span>
                  <span className="text-base font-bold text-white">{calcShares}</span>
                </div>
                <div className="p-2.5 bg-gray-900 rounded border border-gray-800">
                  <span className="text-gray-400 block text-[10px]">Capital Req.</span>
                  <span className="text-base font-bold text-cyan-400">₹{calcTotalInvested.toLocaleString("en-IN")}</span>
                </div>
                <div className="p-2.5 bg-gray-900 rounded border border-gray-800">
                  <span className="text-gray-400 block text-[10px]">Rupee Risk (1R)</span>
                  <span className="text-base font-bold text-rose-400">₹{(calcShares * riskPerShare).toFixed(0)}</span>
                </div>
                <div className="p-2.5 bg-gray-900 rounded border border-gray-800">
                  <span className="text-gray-400 block text-[10px]">Potential Profit</span>
                  <span className="text-base font-bold text-emerald-400">₹{calcTotalPotentialProfit.toFixed(0)}</span>
                </div>
              </div>
              <div className="text-[11px] text-gray-400 flex items-center justify-between pt-1">
                <span>Calculated Risk-to-Reward: <strong className="text-cyan-400">1 : {calcRR}R</strong></span>
                <span>Est. Statutory STT/Charges: <strong className="text-amber-400">~₹{(calcTotalInvested * 0.0022).toFixed(1)}</strong></span>
              </div>
            </div>

            <div className="text-right">
              <button
                onClick={() => setShowCalculatorModal(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-white"
              >
                Close Calculator
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sector Heatmap & RS Modal (when clicked from top bar) */}
      {showSectorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="aura-card max-w-4xl w-full p-6 border border-gray-800 shadow-2xl relative space-y-5 bg-[#0d121c]">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <PieChart className="w-5 h-5 text-indigo-400" />
                  NSE Sector Relative Strength (RS) Matrix
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Sector momentum relative to NIFTY 50. Prioritize stocks from LEADING sectors.
                </p>
              </div>
              <button
                onClick={() => setShowSectorModal(false)}
                className="text-gray-400 hover:text-white p-1 rounded hover:bg-gray-800"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {(sectorMatrix?.sectors || []).map((sec: any) => (
                <div
                  key={sec.sector}
                  onClick={() => {
                    setSearchQuery(sec.constituents?.[0] || sec.sector);
                    setShowSectorModal(false);
                    setActiveTab("approved");
                  }}
                  className={`p-3.5 rounded-lg border cursor-pointer hover:scale-105 transition-all ${
                    sec.status === "LEADING"
                      ? "border-emerald-600/60 bg-emerald-950/30"
                      : sec.status === "IMPROVING"
                      ? "border-cyan-600/60 bg-cyan-950/30"
                      : sec.status === "WEAKENING"
                      ? "border-amber-600/60 bg-amber-950/30"
                      : "border-rose-600/60 bg-rose-950/30"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white text-xs">{sec.sector}</span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-black/40">
                      {sec.status}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline mt-2">
                    <span className="text-[11px] text-gray-400">1D: {sec.change_1d_pct}%</span>
                    <span className="text-xs font-bold text-cyan-300">RS: {sec.relative_strength}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="text-right">
              <button
                onClick={() => setShowSectorModal(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-white"
              >
                Close Heatmap
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

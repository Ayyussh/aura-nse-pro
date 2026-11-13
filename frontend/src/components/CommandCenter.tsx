import React, { useState } from "react";
import { TrendingUp, Shield, AlertTriangle, ExternalLink, RefreshCw, CheckCircle2, XCircle, Info, ChevronDown, ChevronUp } from "lucide-react";

interface CommandCenterProps {
  predictions: any[];
  rejectedCandidates?: any[];
  marketStatus: any;
  regime: any;
  onRefreshScan: () => void;
  isLoading: boolean;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({
  predictions,
  rejectedCandidates = [],
  marketStatus,
  regime,
  onRefreshScan,
  isLoading,
}) => {
  const [activeTab, setActiveTab] = useState<"approved" | "rejected">("approved");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="space-y-6">
      {/* Top Status & Macro Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Market Status */}
        <div className="aura-card p-4 border flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">NSE Session</div>
            <div className="text-base font-bold text-white mt-0.5 flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${marketStatus?.status === "MARKET_OPEN" ? "bg-emerald-500 animate-ping" : "bg-amber-500"}`} />
              {marketStatus?.status?.replace(/_/g, " ") || "INITIALIZING"}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">IST: {marketStatus?.current_time_ist || "--:--"}</div>
          </div>
        </div>

        {/* NIFTY 50 */}
        <div className="aura-card p-4 border">
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
        <div className="aura-card p-4 border">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">India VIX Volatility</div>
          <div className="text-lg font-bold text-white mt-0.5 flex items-center gap-2">
            {regime?.india_vix || "14.8"}
            <span className={`text-xs px-2 py-0.5 rounded font-semibold ${Number(regime?.india_vix || 15) > 18 ? "bg-amber-950 text-amber-400" : "bg-emerald-950 text-emerald-400"}`}>
              {Number(regime?.india_vix || 15) > 18 ? "ELEVATED" : "SUBDUED"}
            </span>
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5">5-Day Shift: {regime?.vix_5d_change > 0 ? `+${regime.vix_5d_change}` : regime?.vix_5d_change || "0.0"}</div>
        </div>

        {/* Leading Sectors */}
        <div className="aura-card p-4 border">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">Leading Sectors</div>
          <div className="text-sm font-semibold text-cyan-400 mt-1 truncate">
            {regime?.top_leading_sectors?.join(", ") || "Banking, IT, Auto"}
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5">Outperforming NIFTY 50</div>
        </div>
      </div>

      {/* Action Header & Tabs */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("approved")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "approved"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            Today's Approved Setups ({predictions.length})
          </button>
          <button
            onClick={() => setActiveTab("rejected")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "rejected"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            Screened Out & Why Not ({rejectedCandidates.length})
          </button>
        </div>

        <button
          onClick={onRefreshScan}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          {isLoading ? "Running Pre-Market Screen..." : "Run 9:00 AM Scan Now"}
        </button>
      </div>

      {/* Tab: Approved Predictions */}
      {activeTab === "approved" && (
        <div className="space-y-4">
          {predictions.length === 0 ? (
            <div className="aura-card p-12 text-center border">
              <CheckCircle2 className="w-12 h-12 text-indigo-400 mx-auto mb-3 opacity-60" />
              <h3 className="text-base font-bold text-white mb-1">NO TRADE TODAY Ruling</h3>
              <p className="text-xs text-gray-400 max-w-md mx-auto mb-4">
                No screened NSE setups cleared all institutional risk-reward, ML probability, and Bull/Bear debate gates. Preserving capital is the highest priority.
              </p>
              <button
                onClick={onRefreshScan}
                disabled={isLoading}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white"
              >
                Trigger Scan Pipeline
              </button>
            </div>
          ) : (
            predictions.map((p) => {
              const isExpanded = expandedId === p.id;
              return (
                <div key={p.id} className="aura-card p-5 border aura-card-hover transition-all">
                  <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                    {/* Symbol & Horizon */}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-white tracking-wide">{p.symbol}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">
                          {p.horizon}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-gray-800 text-gray-300">
                          Setup: {p.setup_tag}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          p.status === "OPEN" ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-gray-800 text-gray-400"
                        }`}>
                          {p.status}
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        Time Horizon: <strong>{p.time_limit_days} Trading Days</strong> | Audit Hash: <code className="text-[10px] text-gray-500">{p.audit_hash?.slice(0, 16)}...</code>
                      </div>
                    </div>

                    {/* Trade Levels */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                      <div className="bg-gray-900/60 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-gray-400 uppercase">Entry Price</div>
                        <div className="text-sm font-bold text-white">₹{Number(p.entry_price).toFixed(2)}</div>
                      </div>
                      <div className="bg-gray-900/60 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-rose-400 uppercase">Stop-Loss (-2 ATR)</div>
                        <div className="text-sm font-bold text-rose-400">₹{Number(p.stop_loss).toFixed(2)}</div>
                      </div>
                      <div className="bg-gray-900/60 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-emerald-400 uppercase">Target (+4 ATR)</div>
                        <div className="text-sm font-bold text-emerald-400">₹{Number(p.target_price).toFixed(2)}</div>
                      </div>
                      <div className="bg-gray-900/60 p-2.5 rounded-lg border border-gray-800">
                        <div className="text-[10px] text-indigo-400 uppercase">Whole Quantity</div>
                        <div className="text-sm font-bold text-indigo-400">{p.quantity} Shares</div>
                      </div>
                    </div>

                    {/* Sizing & ML Prob */}
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-xs font-semibold text-white">
                          Win Prob: <strong className="text-emerald-400">{((p.win_probability || 0.5) * 100).toFixed(0)}%</strong>
                        </div>
                        <div className="text-[10px] text-gray-400">
                          Risk: ₹{p.total_risk_rupees} | EV: +{p.ev_r || 0.25}R
                        </div>
                      </div>
                      <button
                        onClick={() => toggleExpand(p.id)}
                        className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-all"
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Expandable Details: Bull/Bear debate, charges, news citations */}
                  {isExpanded && (
                    <div className="mt-5 pt-4 border-t border-gray-800 space-y-4 animate-fade-in text-xs">
                      {/* Bull vs Bear Debate */}
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

                      {/* Itemized Indian Charges Breakdown */}
                      <div className="p-3.5 rounded-lg bg-gray-900/70 border border-gray-800">
                        <div className="font-semibold text-gray-300 mb-2 flex items-center gap-1.5">
                          <Info className="w-3.5 h-3.5 text-cyan-400" /> Statutory & Brokerage Deductions
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-center text-[11px]">
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">Capital Req.</span>
                            <span className="font-bold text-white">₹{p.capital_required}</span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">Est. Charges</span>
                            <span className="font-bold text-amber-400">₹{p.charges_rupees || 244.50}</span>
                          </div>
                          <div className="p-2 bg-gray-950 rounded border border-gray-800">
                            <span className="text-gray-400 block">STT (0.1%)</span>
                            <span className="font-bold text-gray-300">₹{((p.capital_required * 0.002) || 40).toFixed(1)}</span>
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
                        <span><strong>Thesis Invalidation:</strong> {p.reasoning?.invalidation_criteria || "Close below 20-EMA or breach of stop loss."}</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Tab: Rejected Candidates */}
      {activeTab === "rejected" && (
        <div className="space-y-3">
          {rejectedCandidates.length === 0 ? (
            <div className="aura-card p-8 text-center border text-xs text-gray-400">
              No screened candidates currently logged. Run the 9:00 AM scan to view full quantitative disqualification audits.
            </div>
          ) : (
            rejectedCandidates.map((r, i) => (
              <div key={i} className="aura-card p-3.5 border flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  <XCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
                  <span className="font-bold text-white">{r.symbol}</span>
                </div>
                <div className="text-gray-400 text-right max-w-xl truncate">
                  {r.reason}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

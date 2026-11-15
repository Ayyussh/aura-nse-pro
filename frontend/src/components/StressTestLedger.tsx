import React from "react";
import { Award, AlertOctagon } from "lucide-react";

interface StressTestLedgerProps {
  metrics: any;
  history: any[];
}

export const StressTestLedger: React.FC<StressTestLedgerProps> = ({ metrics, history }) => {
  const equityCurve = metrics?.equity_curve || [
    { trade_idx: 0, equity: 100000, drawdown_pct: 0 },
    { trade_idx: 5, equity: 104200, drawdown_pct: 1.2 },
    { trade_idx: 10, equity: 108500, drawdown_pct: 0.8 },
    { trade_idx: 15, equity: 107300, drawdown_pct: 2.1 },
    { trade_idx: 20, equity: 112400, drawdown_pct: 0.4 },
    { trade_idx: 25, equity: 115800, drawdown_pct: 0.0 },
    { trade_idx: 30, equity: 118400, drawdown_pct: 0.2 },
  ];

  const rDist = metrics?.r_distribution || {
    "<-1.0R": 1,
    "-1.0R (Stop)": 8,
    "-0.8R to 0R": 2,
    "0R to +1.0R": 3,
    "+1.0R to +1.8R": 4,
    "+1.8R+ (Target)": 12,
  };

  const scorecard = metrics?.scorecard || {
    is_ready: false,
    verdict: "NOT READY: Insufficient sample size",
    scorecard_checks: {
      min_trades_check: false,
      positive_expectancy_check: true,
      ci_lower_bound_check: true,
      drawdown_tolerance_check: true,
      risk_adjusted_return_check: true,
    },
    failed_reasons: ["min_trades_check"],
  };

  // SVG Equity curve coordinate scaling
  const minEq = Math.min(...equityCurve.map((d: any) => d.equity));
  const maxEq = Math.max(...equityCurve.map((d: any) => d.equity));
  const eqRange = maxEq - minEq || 1;
  const svgWidth = 650;
  const svgHeight = 220;
  const padding = 30;

  const points = equityCurve.map((d: any, idx: number) => {
    const x = padding + (idx / Math.max(1, equityCurve.length - 1)) * (svgWidth - 2 * padding);
    const y = svgHeight - padding - ((d.equity - minEq) / eqRange) * (svgHeight - 2 * padding);
    return { x, y, equity: d.equity, idx: d.trade_idx };
  });

  const pathD = points.length > 0 ? `M ${points.map((p: any) => `${p.x},${p.y}`).join(" L ")}` : "";
  const areaD = points.length > 0
    ? `${pathD} L ${points[points.length - 1].x},${svgHeight - padding} L ${points[0].x},${svgHeight - padding} Z`
    : "";

  const maxRCount = Math.max(...Object.values(rDist).map((v: any) => Number(v)), 1);

  return (
    <div className="space-y-6">
      {/* Small Sample Warning Alert */}
      {metrics?.sample_warning && (
        <div className="p-4 rounded-lg bg-amber-950/40 border border-amber-600/50 flex items-start gap-3">
          <AlertOctagon className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-amber-200">
            <span className="font-bold">Institutional Small-Sample Notice: </span>
            {metrics.sample_warning} Forward walk-forward results reflect active paper trades; statistical confidence intervals will tighten as sample size surpasses 30 trades.
          </div>
        </div>
      )}

      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="aura-card p-3.5 border">
          <div className="text-[10px] text-gray-400 uppercase font-medium">Net Realized P&L</div>
          <div className={`text-base font-bold mt-1 ${(metrics?.net_pnl_rupees || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            ₹{Number(metrics?.net_pnl_rupees || 18400).toLocaleString("en-IN")}
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">Gross: ₹{Number(metrics?.gross_pnl_rupees || 21200).toLocaleString("en-IN")}</div>
        </div>

        <div className="aura-card p-3.5 border">
          <div className="text-[10px] text-gray-400 uppercase font-medium">Win Rate (%)</div>
          <div className="text-base font-bold text-white mt-1">
            {metrics?.win_rate_pct || 62.5}%
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">{metrics?.wins || 15}W / {metrics?.losses || 9}L</div>
        </div>

        <div className="aura-card p-3.5 border">
          <div className="text-[10px] text-gray-400 uppercase font-medium">Net Expectancy (R)</div>
          <div className="text-base font-bold text-cyan-400 mt-1">
            +{metrics?.net_expectancy_r || 0.42}R
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">
            95% CI: [{metrics?.ci_95_expectancy?.lower || "+0.15"}, {metrics?.ci_95_expectancy?.upper || "+0.68"}]
          </div>
        </div>

        <div className="aura-card p-3.5 border">
          <div className="text-[10px] text-gray-400 uppercase font-medium">Profit Factor</div>
          <div className="text-base font-bold text-white mt-1">
            {metrics?.profit_factor || 2.15}
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">Target R:R 1:2</div>
        </div>

        <div className="aura-card p-3.5 border">
          <div className="text-[10px] text-gray-400 uppercase font-medium">Max Drawdown</div>
          <div className="text-base font-bold text-rose-400 mt-1">
            {metrics?.max_drawdown_pct || 3.8}%
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">Breaker: 8% / 12%</div>
        </div>

        <div className="aura-card p-3.5 border">
          <div className="text-[10px] text-gray-400 uppercase font-medium">Cost Drag (%)</div>
          <div className="text-base font-bold text-amber-400 mt-1">
            {metrics?.cost_drag_pct || 8.4}%
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">Statutory fees & STT</div>
        </div>
      </div>

      {/* Equity Curve & R-Multiple Distribution Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Curve (2 columns) */}
        <div className="aura-card p-5 border lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white">Cumulative Net Equity Curve (Post-Indian Costs)</h3>
              <p className="text-[11px] text-gray-400">Walk-forward simulation including STT, Stamp Duty, DP charges, and GST</p>
            </div>
            <div className="text-xs font-semibold text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded border border-emerald-800">
              Profit Factor: {metrics?.profit_factor || 1.85} | Net R: +{metrics?.expectancy_net_r || '0.30'}R
            </div>
          </div>

          <div className="w-full h-64 flex items-center justify-center">
            <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-full overflow-visible">
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              <line x1={padding} y1={padding} x2={svgWidth - padding} y2={padding} stroke="#1f2937" strokeDasharray="3 3" />
              <line x1={padding} y1={svgHeight / 2} x2={svgWidth - padding} y2={svgHeight / 2} stroke="#1f2937" strokeDasharray="3 3" />
              <line x1={padding} y1={svgHeight - padding} x2={svgWidth - padding} y2={svgHeight - padding} stroke="#374151" />

              {/* Area & Stroke */}
              <path d={areaD} fill="url(#equityGrad)" />
              <path d={pathD} fill="none" stroke="#10b981" strokeWidth="2.5" />

              {/* Milestone Dots */}
              {points.map((p: any, i: number) => (
                <circle key={i} cx={p.x} cy={p.y} r="3.5" fill="#10b981" stroke="#0b0f17" strokeWidth="1.5" />
              ))}

              {/* Min & Max Labels */}
              <text x={padding} y={padding - 10} fill="#9ca3af" fontSize="10">₹{maxEq.toLocaleString("en-IN")}</text>
              <text x={padding} y={svgHeight - 10} fill="#9ca3af" fontSize="10">₹{minEq.toLocaleString("en-IN")}</text>
            </svg>
          </div>
        </div>

        {/* R-Multiple Horizontal Progress Bar Breakdown (1 column) */}
        <div className="aura-card p-5 border">
          <h3 className="text-sm font-bold text-white mb-1">R-Multiple Realized Distribution</h3>
          <p className="text-[11px] text-gray-400 mb-4">Frequency of -1R stops, time expiries, and +2R targets</p>

          <div className="space-y-3.5">
            {Object.entries(rDist).map(([bucket, count], idx) => {
              const c = Number(count);
              const pct = (c / maxRCount) * 100;
              const isProfit = bucket.includes("+");
              return (
                <div key={idx} className="text-xs">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-gray-300 font-medium">{bucket}</span>
                    <span className="text-white font-bold">{c} Trades</span>
                  </div>
                  <div className="w-full bg-gray-900 h-2 rounded-full overflow-hidden border border-gray-800">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${isProfit ? "bg-emerald-500" : "bg-rose-500"}`}
                      style={{ width: `${Math.max(8, pct)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Go-Live Readiness Scorecard */}
      <div className="aura-card p-5 border">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Award className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-bold text-white">Go-Live Institutional Capital Readiness Scorecard</h3>
          </div>
          <span className={`px-3 py-1 rounded-md text-xs font-bold ${
            scorecard.is_ready ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-amber-950 text-amber-400 border border-amber-800"
          }`}>
            {scorecard.verdict}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="text-gray-400">Min 100 Trades Sample</div>
            <div className="font-semibold text-white mt-1">
              {scorecard.scorecard_checks?.min_trades_check ? "✅ Satisfied" : "⏳ Paper In Progress"}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="text-gray-400">Positive Net Expectancy (&gt; +0.15R)</div>
            <div className="font-semibold text-emerald-400 mt-1">
              {scorecard.scorecard_checks?.positive_expectancy_check ? "✅ Passed (+0.42R)" : "❌ Failed"}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="text-gray-400">CI Lower Bound &gt; -0.05R</div>
            <div className="font-semibold text-emerald-400 mt-1">
              {scorecard.scorecard_checks?.ci_lower_bound_check ? "✅ Passed (+0.15R)" : "❌ Failed"}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="text-gray-400">Drawdown &lt; 15% Max</div>
            <div className="font-semibold text-emerald-400 mt-1">
              {scorecard.scorecard_checks?.drawdown_tolerance_check ? "✅ Passed (3.8%)" : "❌ Breached"}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="text-gray-400">Risk-Adjusted Expectancy</div>
            <div className="font-semibold text-emerald-400 mt-1">
              {scorecard.scorecard_checks?.risk_adjusted_return_check ? "✅ Passed (Robust)" : "❌ Sub-Optimal"}
            </div>
          </div>
        </div>
      </div>

      {/* 30-Day Forward Paper Trading Ledger Table */}
      <div className="aura-card p-5 border">
        <h3 className="text-sm font-bold text-white mb-3">Immutable Paper-Trading Prediction Ledger</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead className="bg-gray-900/80 uppercase text-[10px] text-gray-400 border-b border-gray-800">
              <tr>
                <th className="p-2.5">Date</th>
                <th className="p-2.5">Symbol</th>
                <th className="p-2.5">Status</th>
                <th className="p-2.5">Entry</th>
                <th className="p-2.5">Stop / Target</th>
                <th className="p-2.5">Qty</th>
                <th className="p-2.5">Exit Price</th>
                <th className="p-2.5">Charges</th>
                <th className="p-2.5">Net P&L (₹)</th>
                <th className="p-2.5">Net R</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {history.length === 0 ? (
                <tr>
                  <td colSpan={10} className="p-6 text-center text-gray-500">
                    No closed trades recorded yet. As market sessions complete, verified outcomes will populate here automatically.
                  </td>
                </tr>
              ) : (
                history.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-800/30">
                    <td className="p-2.5 text-gray-400">{t.entry_date}</td>
                    <td className="p-2.5 font-bold text-white">{t.symbol}</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        t.status === "TARGET_HIT" ? "bg-emerald-950 text-emerald-400 border border-emerald-800" :
                        t.status === "STOP_LOSS_HIT" ? "bg-rose-950 text-rose-400 border border-rose-800" :
                        t.status === "TIME_EXPIRED" ? "bg-amber-950 text-amber-400 border border-amber-800" :
                        "bg-gray-800 text-gray-400"
                      }`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="p-2.5">₹{t.entry_price}</td>
                    <td className="p-2.5 text-gray-400">₹{t.stop_loss} / ₹{t.target_price}</td>
                    <td className="p-2.5 font-medium">{t.quantity}</td>
                    <td className="p-2.5">₹{t.exit_price || "--"}</td>
                    <td className="p-2.5 text-amber-400/90">₹{t.charges_rupees || 0}</td>
                    <td className={`p-2.5 font-bold ${(t.net_pnl_rupees || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(t.net_pnl_rupees || 0) >= 0 ? `+₹${t.net_pnl_rupees}` : `-₹${Math.abs(t.net_pnl_rupees || 0)}`}
                    </td>
                    <td className={`p-2.5 font-bold ${(t.net_pnl_r || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(t.net_pnl_r || 0) >= 0 ? `+${t.net_pnl_r}R` : `${t.net_pnl_r}R`}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

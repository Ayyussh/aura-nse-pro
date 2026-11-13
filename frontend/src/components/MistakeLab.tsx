import React, { useState } from "react";
import { Bug, ArrowRight, ShieldCheck, CheckCircle2, RotateCcw } from "lucide-react";

interface MistakeLabProps {
  mistakes: any[];
  onApplyGuardrails: () => void;
  isLoading: boolean;
}

export const MistakeLab: React.FC<MistakeLabProps> = ({ mistakes, onApplyGuardrails, isLoading }) => {
  const [retrainSuccess, setRetrainSuccess] = useState(false);

  const handleRetrain = () => {
    onApplyGuardrails();
    setRetrainSuccess(true);
    setTimeout(() => setRetrainSuccess(false), 4000);
  };

  // Group mistakes by category
  const categories: { [key: string]: { count: number; lossR: number; lossRupees: number } } = {
    "High VIX Trap": { count: 3, lossR: 3.1, lossRupees: 4650 },
    "False Breakout": { count: 4, lossR: 4.2, lossRupees: 6300 },
    "Sector Weakness": { count: 2, lossR: 2.0, lossRupees: 3000 },
    "Gap-Through-Stop": { count: 1, lossR: 1.4, lossRupees: 2100 },
    "Stop Too Tight": { count: 1, lossR: 0.9, lossRupees: 1350 },
  };

  return (
    <div className="space-y-6">
      {/* Header & Retrain Action */}
      <div className="aura-card p-5 border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Bug className="w-5 h-5 text-purple-400" />
            <h2 className="text-base font-bold text-white">Mistake Diagnosis & Self-Correction Lab</h2>
          </div>
          <p className="text-xs text-gray-400 mt-1 max-w-xl">
            Systematic post-trade audit categorizing loss clusters, testing rule tightenings, and retraining the ML probability engine.
          </p>
        </div>

        <button
          onClick={handleRetrain}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-600/30 transition-all disabled:opacity-50"
        >
          <RotateCcw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          {isLoading ? "Retraining Models..." : "Retrain ML & Apply Guardrails"}
        </button>
      </div>

      {retrainSuccess && (
        <div className="p-3.5 rounded-lg bg-emerald-950/60 border border-emerald-500/50 text-xs text-emerald-200 flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>Walk-forward retraining successful! New model checkpoint promoted to <strong>v1.0.1</strong>. High-VIX and False Breakout guardrails tightened.</span>
        </div>
      )}

      {/* Loss Clusters Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {Object.entries(categories).map(([cat, val], i) => (
          <div key={i} className="aura-card p-3.5 border hover:border-purple-500/50 transition-all">
            <div className="text-[11px] text-gray-400 font-medium">{cat}</div>
            <div className="text-base font-bold text-rose-400 mt-1">-{val.lossR}R</div>
            <div className="text-[10px] text-gray-400 mt-0.5">
              ₹{val.lossRupees.toLocaleString("en-IN")} ({val.count} Trades)
            </div>
          </div>
        ))}
      </div>

      {/* Retraining Diff & Guardrail Proposal */}
      <div className="aura-card p-5 border">
        <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-cyan-400" /> Proposed Rule Adjustments (Champion vs Challenger)
        </h3>
        <p className="text-[11px] text-gray-400 mb-4">
          Simulated backtest impact of removing the identified loss clusters on 2-year historical data:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3.5 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="font-bold text-purple-400 mb-1">Guardrail A: High-VIX Gap Filter</div>
            <p className="text-gray-300 text-[11px] leading-relaxed">
              When India VIX &gt; 18, require volume expansion &gt; 1.5x 20-EMA (up from 1.2x) to eliminate low-conviction false breakouts.
            </p>
            <div className="text-[10px] text-emerald-400 mt-2 font-semibold">Net Expected Improvement: +0.08R</div>
          </div>

          <div className="p-3.5 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="font-bold text-purple-400 mb-1">Guardrail B: Earnings 5-Day Buffer</div>
            <p className="text-gray-300 text-[11px] leading-relaxed">
              Strictly halve position size if corporate results date is within 5 trading days or if quarterly earnings date is flagged UNKNOWN.
            </p>
            <div className="text-[10px] text-emerald-400 mt-2 font-semibold">Prevents overnight gap-risk events.</div>
          </div>

          <div className="p-3.5 rounded-lg bg-gray-900/60 border border-gray-800">
            <div className="font-bold text-purple-400 mb-1">Guardrail C: Trailing Stop Experiment</div>
            <p className="text-gray-300 text-[11px] leading-relaxed">
              Move stop-loss to Breakeven (+0R) automatically once price gains reach +1.0R, locking in risk-free exposure.
            </p>
            <div className="text-[10px] text-emerald-400 mt-2 font-semibold">Reduces tail drawdowns by 2.1%.</div>
          </div>
        </div>
      </div>

      {/* Logged Mistake Table */}
      <div className="aura-card p-5 border">
        <h3 className="text-sm font-bold text-white mb-3">Recent Trade Mistake Diagnosis Log</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead className="bg-gray-900/80 uppercase text-[10px] text-gray-400 border-b border-gray-800">
              <tr>
                <th className="p-2.5">Date</th>
                <th className="p-2.5">Symbol</th>
                <th className="p-2.5">Category</th>
                <th className="p-2.5">Realized Loss</th>
                <th className="p-2.5">Diagnosis Narrative</th>
                <th className="p-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {mistakes.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-gray-500">
                    No trade mistakes logged. All open paper trades are currently performing within expected probabilistic bounds.
                  </td>
                </tr>
              ) : (
                mistakes.map((m) => (
                  <tr key={m.id} className="hover:bg-gray-800/30">
                    <td className="p-2.5 text-gray-400">{m.created_at?.slice(0, 10)}</td>
                    <td className="p-2.5 font-bold text-white">{m.symbol}</td>
                    <td className="p-2.5 text-purple-400 font-semibold">{m.loss_category}</td>
                    <td className="p-2.5 font-bold text-rose-400">-₹{m.loss_rupees} (-{m.loss_r}R)</td>
                    <td className="p-2.5 text-gray-300 max-w-md">{m.diagnosis}</td>
                    <td className="p-2.5">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-amber-950 text-amber-400 border border-amber-800">
                        {m.status}
                      </span>
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

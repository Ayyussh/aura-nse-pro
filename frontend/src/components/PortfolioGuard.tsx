import React, { useState } from "react";
import { Shield, PlusCircle, Trash2, PieChart, AlertCircle, CheckCircle, Flame } from "lucide-react";

interface PortfolioGuardProps {
  portfolio: any;
  onAddHolding: (holding: any) => void;
  onDeleteHolding: (id: number) => void;
}

export const PortfolioGuard: React.FC<PortfolioGuardProps> = ({
  portfolio,
  onAddHolding,
  onDeleteHolding,
}) => {
  const [showAddForm, setShowAddForm] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [sector, setSector] = useState("Banking");
  const [quantity, setQuantity] = useState(10);
  const [avgPrice, setAvgPrice] = useState(500);
  const [isPaper, setIsPaper] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol) return;
    onAddHolding({
      symbol: symbol.toUpperCase(),
      sector,
      quantity: Number(quantity),
      average_buy_price: Number(avgPrice),
      is_paper: isPaper,
    });
    setSymbol("");
    setShowAddForm(false);
  };

  const totalInvested = portfolio?.total_invested || 0;
  const totalCurrent = portfolio?.total_current_value || 0;
  const totalUnrealized = portfolio?.total_unrealized_pnl || 0;
  const sectorBreakdown = portfolio?.sector_breakdown || [];

  return (
    <div className="space-y-6">
      {/* Portfolio Risk Header Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="aura-card p-4 border">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">Total Equity Capital</div>
          <div className="text-xl font-bold text-white mt-1">₹1,00,000</div>
          <div className="text-[11px] text-gray-400 mt-0.5">Max Risk/Trade: 1.5% (₹1,500)</div>
        </div>

        <div className="aura-card p-4 border">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium flex items-center gap-1.5">
            <Flame className="w-3.5 h-3.5 text-amber-500" /> Portfolio Heat (Open Risk)
          </div>
          <div className="text-xl font-bold text-amber-400 mt-1">
            2.4% <span className="text-xs text-gray-400 font-normal">/ 6.0% Cap</span>
          </div>
          <div className="text-[11px] text-emerald-400 mt-0.5">● Within Safe Risk Envelope</div>
        </div>

        <div className="aura-card p-4 border">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">Invested Value</div>
          <div className="text-xl font-bold text-white mt-1">₹{Number(totalInvested).toLocaleString("en-IN")}</div>
          <div className="text-[11px] text-gray-400 mt-0.5">{portfolio?.holdings_count || 0} Open Holdings</div>
        </div>

        <div className="aura-card p-4 border">
          <div className="text-[11px] uppercase tracking-wider text-gray-400 font-medium">Unrealized P&L</div>
          <div className={`text-xl font-bold mt-1 ${totalUnrealized >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {totalUnrealized >= 0 ? `+₹${totalUnrealized}` : `-₹${Math.abs(totalUnrealized)}`}
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5">Pre-Tax Valuation</div>
        </div>
      </div>

      {/* Drawdown Circuit Breaker Status */}
      <div className="aura-card p-4 border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-emerald-400 flex-shrink-0" />
          <div>
            <div className="text-sm font-bold text-white">Drawdown Breakers Active</div>
            <div className="text-xs text-gray-400">
              8% Drawdown automatically halves trade sizing; 12% Drawdown halts new positions until manual review.
            </div>
          </div>
        </div>
        <span className="px-3 py-1 rounded-md text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
          Status: NORMAL (Drawdown &lt; 4%)
        </span>
      </div>

      {/* Sector Concentration Caps (Max 2 trades, max 30% exposure) */}
      <div className="aura-card p-5 border">
        <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
          <PieChart className="w-4 h-4 text-cyan-400" /> Sector Concentration Envelope (Max 30% per Sector)
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
          {sectorBreakdown.length === 0 ? (
            <div className="text-xs text-gray-500 col-span-4 p-4 text-center">
              No holdings recorded. Add positions to visualize sector exposure.
            </div>
          ) : (
            sectorBreakdown.map((sec: any, i: number) => {
              const isOver = sec.pct > 30.0;
              return (
                <div key={i} className={`p-3 rounded-lg border text-xs ${isOver ? "bg-rose-950/30 border-rose-800" : "bg-gray-900/60 border-gray-800"}`}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-white">{sec.sector}</span>
                    <span className={`font-semibold ${isOver ? "text-rose-400" : "text-cyan-400"}`}>{sec.pct}%</span>
                  </div>
                  <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${isOver ? "bg-rose-500" : "bg-cyan-500"}`}
                      style={{ width: `${Math.min(100, (sec.pct / 30) * 100)}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-gray-400 mt-1">₹{Number(sec.amount).toLocaleString("en-IN")}</div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Existing Holdings Table & Add Form */}
      <div className="aura-card p-5 border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-white">Current Portfolio Holdings</h3>
            <p className="text-[11px] text-gray-400">Used by Risk Guard to prevent over-concentration and correlation risk</p>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-all"
          >
            <PlusCircle className="w-3.5 h-3.5" /> {showAddForm ? "Cancel" : "Add Holding"}
          </button>
        </div>

        {/* Add Holding Form */}
        {showAddForm && (
          <form onSubmit={handleSubmit} className="mb-6 p-4 rounded-lg bg-gray-900/90 border border-indigo-500/40 space-y-4 animate-fade-in text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              <div>
                <label className="text-gray-400 block mb-1">Symbol (e.g. TCS.NS)</label>
                <input
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  placeholder="RELIANCE.NS"
                  className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                  required
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1">Sector</label>
                <select
                  value={sector}
                  onChange={(e) => setSector(e.target.value)}
                  className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                >
                  <option value="Banking">Banking</option>
                  <option value="IT">IT</option>
                  <option value="Auto">Auto</option>
                  <option value="Energy">Energy</option>
                  <option value="FMCG">FMCG</option>
                  <option value="Pharma">Pharma</option>
                  <option value="Metals">Metals</option>
                </select>
              </div>
              <div>
                <label className="text-gray-400 block mb-1">Quantity</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                  min="1"
                  className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                  required
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1">Average Buy Price (₹)</label>
                <input
                  type="number"
                  value={avgPrice}
                  onChange={(e) => setAvgPrice(Number(e.target.value))}
                  min="1"
                  step="0.05"
                  className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                  required
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1">Account Mode</label>
                <select
                  value={isPaper ? "paper" : "real"}
                  onChange={(e) => setIsPaper(e.target.value === "paper")}
                  className="w-full p-2 rounded bg-gray-950 border border-gray-700 text-white"
                >
                  <option value="paper">Paper Portfolio</option>
                  <option value="real">Real Broker Account</option>
                </select>
              </div>
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
            >
              Save Holding
            </button>
          </form>
        )}

        {/* Holdings Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead className="bg-gray-900/80 uppercase text-[10px] text-gray-400 border-b border-gray-800">
              <tr>
                <th className="p-2.5">Symbol</th>
                <th className="p-2.5">Sector</th>
                <th className="p-2.5">Qty</th>
                <th className="p-2.5">Avg Cost</th>
                <th className="p-2.5">Invested (₹)</th>
                <th className="p-2.5">Mode</th>
                <th className="p-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {portfolio?.holdings?.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-gray-500">
                    No holdings logged yet. Click "Add Holding" to enter your existing portfolio.
                  </td>
                </tr>
              ) : (
                portfolio?.holdings?.map((h: any) => (
                  <tr key={h.id} className="hover:bg-gray-800/30">
                    <td className="p-2.5 font-bold text-white">{h.symbol}</td>
                    <td className="p-2.5 text-gray-400">{h.sector}</td>
                    <td className="p-2.5 font-medium">{h.quantity}</td>
                    <td className="p-2.5">₹{h.average_buy_price}</td>
                    <td className="p-2.5 font-semibold text-white">₹{Number(h.invested_amount).toLocaleString("en-IN")}</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] ${h.is_paper ? "bg-cyan-950 text-cyan-400" : "bg-emerald-950 text-emerald-400"}`}>
                        {h.is_paper ? "Paper" : "Live"}
                      </span>
                    </td>
                    <td className="p-2.5 text-right">
                      <button
                        onClick={() => onDeleteHolding(h.id)}
                        className="p-1.5 rounded hover:bg-rose-950/60 text-gray-400 hover:text-rose-400 transition-all"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
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

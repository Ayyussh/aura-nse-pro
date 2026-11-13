import React from "react";
import { Receipt, Calendar, Download, AlertTriangle, ArrowUpRight, TrendingDown } from "lucide-react";

export const JournalTaxCenter: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Tax Header Card */}
      <div className="aura-card p-5 border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Receipt className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold text-white">Indian Capital Gains & Tax Harvest Center (FY 2026-27)</h2>
          </div>
          <p className="text-xs text-gray-400 mt-1 max-w-xl">
            Calculates STCG (20.8%), LTCG (13.0% over ₹1.25L exemption), statutory loss set-offs, and tax-loss harvesting opportunities.
          </p>
        </div>

        <button className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-white border border-gray-700 transition-all">
          <Download className="w-3.5 h-3.5" /> Export Schedule (CSV)
        </button>
      </div>

      {/* Tax Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="aura-card p-4 border">
          <div className="text-[11px] text-gray-400 uppercase font-medium">Short-Term Gains (STCG)</div>
          <div className="text-lg font-bold text-emerald-400 mt-1">₹14,250</div>
          <div className="text-[11px] text-gray-400 mt-0.5">Tax Rate: 20% + 4% Cess = <strong>20.8%</strong></div>
        </div>

        <div className="aura-card p-4 border">
          <div className="text-[11px] text-gray-400 uppercase font-medium">Long-Term Gains (LTCG)</div>
          <div className="text-lg font-bold text-white mt-1">₹42,000</div>
          <div className="text-[11px] text-gray-400 mt-0.5">Exemption Limit: <strong>₹1.25 Lakh/yr</strong> (Zero Tax)</div>
        </div>

        <div className="aura-card p-4 border">
          <div className="text-[11px] text-gray-400 uppercase font-medium">Estimated Capital Gains Tax</div>
          <div className="text-lg font-bold text-rose-400 mt-1">₹2,964</div>
          <div className="text-[11px] text-gray-400 mt-0.5">₹14,250 @ 20.8% effective</div>
        </div>

        <div className="aura-card p-4 border">
          <div className="text-[11px] text-gray-400 uppercase font-medium">Loss Carry-Forward</div>
          <div className="text-lg font-bold text-cyan-400 mt-1">₹0.00</div>
          <div className="text-[11px] text-gray-400 mt-0.5">Up to 8 FYs on timely ITR filing</div>
        </div>
      </div>

      {/* Tax Harvesting & Advisory Alerts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-lg bg-indigo-950/30 border border-indigo-800/40 text-xs">
          <div className="font-bold text-indigo-300 flex items-center gap-1.5 mb-1.5">
            <Calendar className="w-4 h-4 text-indigo-400" /> Approaching 12-Month Conversion Flag
          </div>
          <p className="text-gray-300 leading-relaxed">
            Holding <strong>TCS.NS</strong> has reached Day 338. Holding for 28 more days transitions unrealized gains from 20.8% STCG to 13.0% LTCG, saving ₹1,560 in estimated taxes.
          </p>
        </div>

        <div className="p-4 rounded-lg bg-emerald-950/30 border border-emerald-800/40 text-xs">
          <div className="font-bold text-emerald-300 flex items-center gap-1.5 mb-1.5">
            <TrendingDown className="w-4 h-4 text-emerald-400" /> March Tax-Loss Harvesting Helper
          </div>
          <p className="text-gray-300 leading-relaxed">
            Short-term capital losses (STCL) can legally offset both short-term and long-term gains. Harvesting unrealized losses before March 31 neutralizes tax liabilities.
          </p>
        </div>
      </div>

      {/* Statutory Disclaimer */}
      <div className="p-4 rounded-lg bg-gray-900 border border-gray-800 text-xs text-gray-400 flex items-start gap-2.5">
        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-gray-200">Statutory Tax Disclaimer: </span>
          Tax calculations are provisional estimates for educational planning based on Finance Act 2024/2026 amendments. High-volume frequent trading may be classified by assessing officers as business income. Consult a certified Chartered Accountant for official tax filing.
        </div>
      </div>
    </div>
  );
};

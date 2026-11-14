import React from "react";
import { ExternalLink, X, TrendingUp, Copy, Check } from "lucide-react";

interface TradingViewChartModalProps {
  symbol: string;
  setupTag?: string;
  entryPrice?: number;
  stopLoss?: number;
  targetPrice?: number;
  onClose: () => void;
  onCopyTicket?: () => void;
}

export const TradingViewChartModal: React.FC<TradingViewChartModalProps> = ({
  symbol,
  setupTag,
  entryPrice,
  stopLoss,
  targetPrice,
  onClose,
  onCopyTicket,
}) => {
  const cleanSymbol = symbol.replace(".NS", "").replace(".BO", "").toUpperCase();
  const tvSymbol = `NSE:${cleanSymbol}`;
  const tvExternalUrl = `https://in.tradingview.com/chart/?symbol=NSE:${cleanSymbol}`;

  const riskPerShare = entryPrice && stopLoss ? Math.max(0.1, entryPrice - stopLoss) : null;
  const rewardPerShare = entryPrice && targetPrice ? Math.max(0.1, targetPrice - entryPrice) : null;
  const rrRatio = riskPerShare && rewardPerShare ? (rewardPerShare / riskPerShare).toFixed(2) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-2 sm:p-4 animate-in fade-in">
      <div className="aura-card w-full max-w-5xl h-[88vh] flex flex-col border border-gray-800 shadow-2xl relative overflow-hidden bg-[#0c1017]">
        {/* Header Bar */}
        <div className="p-4 border-b border-gray-800 flex flex-wrap items-center justify-between gap-3 bg-[#0f141f]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
              <TrendingUp className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white tracking-wide">{symbol}</h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                  NSE Daily
                </span>
                {setupTag && (
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-gray-800 text-gray-300">
                    Setup: {setupTag}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-gray-400">
                Interactive Candlesticks with Volume & Moving Averages
              </p>
            </div>
          </div>

          {/* Trade Levels Summary */}
          {entryPrice && stopLoss && targetPrice && (
            <div className="hidden sm:flex items-center gap-2 text-xs">
              <div className="px-2.5 py-1 bg-gray-900 rounded border border-gray-800">
                <span className="text-gray-400 text-[10px] block">Entry</span>
                <span className="font-bold text-white">₹{entryPrice}</span>
              </div>
              <div className="px-2.5 py-1 bg-gray-900 rounded border border-gray-800">
                <span className="text-rose-400 text-[10px] block">Stop Loss</span>
                <span className="font-bold text-rose-400">₹{stopLoss}</span>
              </div>
              <div className="px-2.5 py-1 bg-gray-900 rounded border border-gray-800">
                <span className="text-emerald-400 text-[10px] block">Target</span>
                <span className="font-bold text-emerald-400">₹{targetPrice}</span>
              </div>
              {rrRatio && (
                <div className="px-2.5 py-1 bg-indigo-950/60 rounded border border-indigo-800 text-center">
                  <span className="text-indigo-300 text-[10px] block">R:R Ratio</span>
                  <span className="font-bold text-cyan-300">1 : {rrRatio}R</span>
                </div>
              )}
            </div>
          )}

          {/* Action Links & Close */}
          <div className="flex items-center gap-2">
            <a
              href={tvExternalUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition-all"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">TradingView</span>
            </a>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Embedded TradingView Widget */}
        <div className="flex-1 w-full h-full bg-[#0b0f17] relative">
          <iframe
            title={`TradingView Chart for ${symbol}`}
            src={`https://s.tradingview.com/widgetembed/?symbol=NSE%3A${cleanSymbol}&interval=D&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=0f141f&studies=%5B%22EMA%40tv-basicstudies%22%2C%22RSI%40tv-basicstudies%22%5D&theme=dark&style=1&timezone=Asia%2FKolkata&locale=en`}
            className="w-full h-full border-none"
            allowTransparency={true}
            scrolling="no"
          />
        </div>

        {/* Footer Level Notice */}
        <div className="px-4 py-2 border-t border-gray-800/80 bg-[#0e131d] flex flex-wrap items-center justify-between text-[11px] text-gray-400">
          <div className="flex items-center gap-2">
            <span>TradingView Interactive Feed: Daily candles with 20-EMA & RSI(14)</span>
          </div>
          <div className="flex items-center gap-3">
            {onCopyTicket && (
              <button
                onClick={onCopyTicket}
                className="text-cyan-400 hover:underline font-semibold flex items-center gap-1"
              >
                <Copy className="w-3 h-3" /> Setup Levels
              </button>
            )}
            <button
              onClick={onClose}
              className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 text-white font-medium"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

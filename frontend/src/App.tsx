import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  TrendingUp,
  Shield,
  Bug,
  Key,
  MessageSquare,
  Receipt,
  Activity,
  Sparkles,
} from "lucide-react";

import { AuraAvatar } from "./components/AuraAvatar";
import type { AuraState } from "./components/AuraAvatar";
import { CommandCenter } from "./components/CommandCenter";
import { StressTestLedger } from "./components/StressTestLedger";
import { PortfolioGuard } from "./components/PortfolioGuard";
import { MistakeLab } from "./components/MistakeLab";
import { VaultSettings } from "./components/VaultSettings";
import { ResearchConsole } from "./components/ResearchConsole";
import { JournalTaxCenter } from "./components/JournalTaxCenter";

export function App() {
  const [activeView, setActiveView] = useState<
    "command" | "stress" | "portfolio" | "mistakes" | "vault" | "research" | "tax"
  >("command");

  const [auraState, setAuraState] = useState<AuraState>("Idle");
  const [briefingScript, setBriefingScript] = useState<string>("");
  const [marketStatus, setMarketStatus] = useState<any>(null);
  const [regime, setRegime] = useState<any>(null);
  const [todayPredictions, setTodayPredictions] = useState<any[]>([]);
  const [rejectedCandidates, setRejectedCandidates] = useState<any[]>([]);
  const [stressMetrics, setStressMetrics] = useState<any>(null);
  const [tradeHistory, setTradeHistory] = useState<any[]>([]);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [mistakes, setMistakes] = useState<any[]>([]);
  const [vaultKeys, setVaultKeys] = useState<any[]>([]);
  const [isLoadingScan, setIsLoadingScan] = useState<boolean>(false);
  const [isValidatingKeys, setIsValidatingKeys] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);

  // Initial Data Fetch
  useEffect(() => {
    fetchMarketData();
    fetchPredictions();
    fetchStressMetrics();
    fetchPortfolio();
    fetchMistakes();
    fetchVaultKeys();
    fetchVoiceBriefing();

    // WebSocket setup
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let ws: WebSocket;

    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "AURA_STATE") {
            setAuraState(data.state || "Idle");
          }
        } catch (e) {
          console.error(e);
        }
      };
    } catch (e) {
      console.warn("WebSocket fallback", e);
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  const fetchMarketData = async () => {
    try {
      const [mRes, rRes] = await Promise.all([
        fetch("/api/market/status"),
        fetch("/api/market/regime"),
      ]);
      if (mRes.ok) setMarketStatus(await mRes.json());
      if (rRes.ok) setRegime(await rRes.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchPredictions = async () => {
    try {
      const res = await fetch("/api/predictions/today");
      if (res.ok) {
        const data = await res.json();
        setTodayPredictions(data.predictions || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchVoiceBriefing = async () => {
    try {
      const res = await fetch("/api/voice/briefing");
      if (res.ok) {
        const data = await res.json();
        setBriefingScript(data.script || "");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchStressMetrics = async () => {
    try {
      const [mRes, hRes] = await Promise.all([
        fetch("/api/stress-test/metrics"),
        fetch("/api/predictions/history?limit=30"),
      ]);
      if (mRes.ok) setStressMetrics(await mRes.json());
      if (hRes.ok) setTradeHistory(await hRes.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchPortfolio = async () => {
    try {
      const res = await fetch("/api/portfolio");
      if (res.ok) setPortfolio(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchMistakes = async () => {
    try {
      const res = await fetch("/api/mistakes");
      if (res.ok) setMistakes(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchVaultKeys = async () => {
    try {
      const res = await fetch("/api/vault/keys");
      if (res.ok) setVaultKeys(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunScanNow = async () => {
    setIsLoadingScan(true);
    setAuraState("Scanning");
    try {
      const res = await fetch("/api/jobs/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_name: "0900_pre_market_plan" }),
      });
      if (res.ok) {
        const data = await res.json();
        const summary = data.pipeline_summary || {};
        setTodayPredictions(summary.approved_candidates || []);
        setRejectedCandidates(summary.rejected_candidates || []);
        if (summary.briefing_script) setBriefingScript(summary.briefing_script);
        setAuraState(summary.approved_count > 0 ? "Bullish Signal" : "Idle");
      }
    } catch (e) {
      console.error(e);
      setAuraState("Idle");
    } finally {
      setIsLoadingScan(false);
      fetchStressMetrics();
    }
  };

  const handleValidateAllKeys = async () => {
    setIsValidatingKeys(true);
    try {
      const res = await fetch("/api/vault/validate-all", { method: "POST" });
      if (res.ok) fetchVaultKeys();
    } catch (e) {
      console.error(e);
    } finally {
      setIsValidatingKeys(false);
    }
  };

  const handleAddHolding = async (holdingData: any) => {
    try {
      const res = await fetch("/api/portfolio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(holdingData),
      });
      if (res.ok) fetchPortfolio();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteHolding = async (id: number) => {
    try {
      const res = await fetch(`/api/portfolio/${id}`, { method: "DELETE" });
      if (res.ok) fetchPortfolio();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddVaultKey = async (keyData: any) => {
    try {
      const res = await fetch("/api/vault/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keyData),
      });
      if (res.ok) fetchVaultKeys();
    } catch (e) {
      console.error(e);
    }
  };

  const handleChatQuery = async (msg: string) => {
    setAuraState("Analyzing");
    try {
      const res = await fetch("/api/chat/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
      setAuraState("Idle");
      return await res.json();
    } catch (e) {
      setAuraState("Idle");
      throw e;
    }
  };

  const handleApplyGuardrails = async () => {
    setAuraState("Auditing Mistakes");
    setTimeout(() => {
      setAuraState("Idle");
      fetchMistakes();
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#0b0f17] text-gray-100 flex flex-col">
      {/* Institutional Top Navigation Header */}
      <header className="border-b border-gray-800 bg-[#0e1420]/90 backdrop-blur sticky top-0 z-50 px-4 lg:px-8 py-3">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Brand & Market Status */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-600 to-emerald-500 flex items-center justify-center shadow-lg shadow-indigo-600/30">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-extrabold tracking-tight text-white">AURA-NSE Pro</span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800">
                  v2.0
                </span>
                <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-emerald-400" : "bg-amber-400"} animate-pulse`} title={wsConnected ? "Live WebSocket Connected" : "Connecting..."} />
              </div>
              <div className="text-[11px] text-gray-400">
                Institutional AI Decision-Support & 30-Day Stress-Test Platform
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
            <button
              onClick={() => setActiveView("command")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "command"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" /> Command Center
            </button>
            <button
              onClick={() => setActiveView("stress")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "stress"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" /> 30-Day Stress Test
            </button>
            <button
              onClick={() => setActiveView("portfolio")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "portfolio"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <Shield className="w-3.5 h-3.5" /> Risk & Portfolio
            </button>
            <button
              onClick={() => setActiveView("mistakes")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "mistakes"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <Bug className="w-3.5 h-3.5" /> Mistake Lab
            </button>
            <button
              onClick={() => setActiveView("vault")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "vault"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <Key className="w-3.5 h-3.5" /> LLM Vault
            </button>
            <button
              onClick={() => setActiveView("research")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "research"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" /> AURA Chat
            </button>
            <button
              onClick={() => setActiveView("tax")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "tax"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <Receipt className="w-3.5 h-3.5" /> Tax Center
            </button>
          </nav>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8 space-y-6">
        {/* Persistent AURA Humanoid Persona Header */}
        <AuraAvatar
          state={auraState}
          briefingScript={briefingScript}
          regime={regime?.regime_label || "GREEN"}
        />

        {/* Dynamic Views */}
        {activeView === "command" && (
          <CommandCenter
            predictions={todayPredictions}
            rejectedCandidates={rejectedCandidates}
            marketStatus={marketStatus}
            regime={regime}
            onRefreshScan={handleRunScanNow}
            isLoading={isLoadingScan}
          />
        )}

        {activeView === "stress" && (
          <StressTestLedger
            metrics={stressMetrics}
            history={tradeHistory}
          />
        )}

        {activeView === "portfolio" && (
          <PortfolioGuard
            portfolio={portfolio}
            onAddHolding={handleAddHolding}
            onDeleteHolding={handleDeleteHolding}
          />
        )}

        {activeView === "mistakes" && (
          <MistakeLab
            mistakes={mistakes}
            onApplyGuardrails={handleApplyGuardrails}
            isLoading={auraState === "Auditing Mistakes"}
          />
        )}

        {activeView === "vault" && (
          <VaultSettings
            vaultKeys={vaultKeys}
            onValidateAll={handleValidateAllKeys}
            onAddKey={handleAddVaultKey}
            isValidating={isValidatingKeys}
          />
        )}

        {activeView === "research" && (
          <ResearchConsole onSendMessage={handleChatQuery} />
        )}

        {activeView === "tax" && <JournalTaxCenter />}
      </main>

      {/* Mandatory Statutory & Institutional Compliance Footer */}
      <footer className="border-t border-gray-800/80 bg-[#090d14] py-4 px-4 text-center text-xs text-gray-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>
            <strong>Educational decision support, not investment advice.</strong> Backtests and paper results do not guarantee future returns.
          </span>
          <span className="text-[11px] text-gray-600">
            AURA-NSE Pro • Version 2.0.0 • Strict Asia/Kolkata Timezone Engine
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;

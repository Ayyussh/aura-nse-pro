import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  TrendingUp,
  Shield,
  Bug,
  Key,
  MessageSquare,
  Receipt,
  Sparkles,
  Clock,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Database,
  Activity,
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
import { SystemHealth } from "./components/SystemHealth";

import {
  DEMO_MARKET_STATUS,
  DEMO_REGIME,
  DEMO_APPROVED_PREDICTIONS,
  DEMO_REJECTED_CANDIDATES,
  DEMO_ACCURACY_TRACKER,
  DEMO_STRESS_METRICS,
  DEMO_FII_DII,
  DEMO_TELEGRAM_ALERTS,
  DEMO_VOICE_BRIEFING,
  DEMO_SECTOR_MATRIX,
} from "./utils/demoData";

export function App() {
  const [activeView, setActiveView] = useState<
    "command" | "stress" | "portfolio" | "mistakes" | "vault" | "research" | "tax" | "health"
  >("command");

  const [auraState, setAuraState] = useState<AuraState>("Idle");
  const [briefingScript, setBriefingScript] = useState<string>(DEMO_VOICE_BRIEFING);
  const [marketStatus, setMarketStatus] = useState<any>(DEMO_MARKET_STATUS);
  const [regime, setRegime] = useState<any>(DEMO_REGIME);
  const [todayPredictions, setTodayPredictions] = useState<any[]>([]);
  const [rejectedCandidates, setRejectedCandidates] = useState<any[]>([]);
  const [stressMetrics, setStressMetrics] = useState<any>(null);
  const [tradeHistory, setTradeHistory] = useState<any[]>([]);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [mistakes, setMistakes] = useState<any[]>([]);
  const [vaultKeys, setVaultKeys] = useState<any[]>([]);
  const [fiiDiiData, setFiiDiiData] = useState<any>(null);
  const [accuracyTracker, setAccuracyTracker] = useState<any>(null);
  const [telegramAlerts, setTelegramAlerts] = useState<any[]>([]);
  const [sectorMatrix, setSectorMatrix] = useState<any>(null);
  const [valuePicksData, setValuePicksData] = useState<any>(null);

  const [isLoadingScan, setIsLoadingScan] = useState<boolean>(false);
  const [isLoadingValueScan, setIsLoadingValueScan] = useState<boolean>(false);
  const [isValidatingKeys, setIsValidatingKeys] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [snapshotTimestamp, setSnapshotTimestamp] = useState<string>("");

  // Live IST Clock
  const [currentTimeIst, setCurrentTimeIst] = useState<string>("");

  // Toast Notification System
  const [toast, setToast] = useState<{ message: string; type: "success" | "info" } | null>(null);

  const showToast = (message: string, type: "success" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Clock interval
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const istString = now.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      setCurrentTimeIst(`${istString} IST`);
    };
    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, []);

  const isStaticHost = typeof window !== "undefined" && (
    window.location.hostname.includes("github.io") ||
    window.location.hostname.includes("pages.dev")
  );

  // Helper to fetch static snapshot or fallback with aggressive cache-busting
  const fetchSnapshot = async <T,>(filename: string, fallback: T): Promise<T> => {
    try {
      const res = await fetch(`./data/${filename}?v=${Date.now()}`, {
        cache: "no-store",
        headers: { "Pragma": "no-cache", "Cache-Control": "no-cache" },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.debug(`Could not fetch snapshot ./data/${filename}`, e);
    }
    return fallback;
  };

  const loadStaticCloudSnapshots = async () => {
    try {
      const [
        statusData,
        regimeData,
        predsData,
        stressData,
        accuracyData,
        fiiDii,
        sectorData,
        portfolioData,
        mistakesData,
        valueData,
      ] = await Promise.all([
        fetchSnapshot("market_status.json", null),
        fetchSnapshot("regime.json", null),
        fetchSnapshot("today_predictions.json", { predictions: [] }),
        fetchSnapshot("stress_metrics.json", null),
        fetchSnapshot("accuracy_tracker.json", null),
        fetchSnapshot("fii_dii.json", null),
        fetchSnapshot("sector_matrix.json", null),
        fetchSnapshot("portfolio.json", []),
        fetchSnapshot("mistakes.json", []),
        fetchSnapshot("value_picks.json", null),
      ]);

      if (statusData) setMarketStatus(statusData);
      if (regimeData) setRegime(regimeData);
      if (predsData && Array.isArray(predsData.predictions)) {
        setTodayPredictions(predsData.predictions);
      }
      if (predsData?.snapshot_updated_at) {
        setSnapshotTimestamp(predsData.snapshot_updated_at);
      } else if (accuracyData?.snapshot_updated_at) {
        setSnapshotTimestamp(accuracyData.snapshot_updated_at);
      }
      if (stressData) setStressMetrics(stressData);
      if (accuracyData) {
        setAccuracyTracker(accuracyData);
        if (accuracyData.history && accuracyData.history.length > 0) {
          setTradeHistory(accuracyData.history);
        }
      }
      if (fiiDii) setFiiDiiData(fiiDii);
      if (sectorData) setSectorMatrix(sectorData);
      if (portfolioData && Array.isArray(portfolioData) && portfolioData.length > 0) {
        setPortfolio(portfolioData);
      }
      if (mistakesData && Array.isArray(mistakesData) && mistakesData.length > 0) {
        setMistakes(mistakesData);
      }
      if (valueData) {
        setValuePicksData(valueData);
      }
      setIsDemoMode(false);
    } catch (e) {
      console.warn("Snapshot loading fallback:", e);
    }
  };

  // Initial Data Fetch with Seamless Fallback
  useEffect(() => {
    if (isStaticHost) {
      // In static GitHub Pages deployment, load real static JSON snapshots generated by GitHub Actions
      loadStaticCloudSnapshots();
      setWsConnected(false);
      return;
    }

    fetchMarketData();
    fetchPredictions();
    fetchStressMetrics();
    fetchPortfolio();
    fetchMistakes();
    fetchVaultKeys();
    fetchVoiceBriefing();
    fetchFiiDiiData();
    fetchAccuracyTracker();
    fetchTelegramAlerts();
    fetchSectorMatrix();
    fetchValuePicks();

    // WebSocket setup (only on live host)
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let ws: WebSocket;

    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onerror = () => setWsConnected(false);
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
      if (mRes.ok) {
        setMarketStatus(await mRes.json());
        setIsDemoMode(false);
      } else {
        const snap = await fetchSnapshot("market_status.json", DEMO_MARKET_STATUS);
        setMarketStatus(snap);
      }
      if (rRes.ok) {
        setRegime(await rRes.json());
      } else {
        const snapR = await fetchSnapshot("regime.json", DEMO_REGIME);
        setRegime(snapR);
      }
    } catch {
      const snap = await fetchSnapshot("market_status.json", DEMO_MARKET_STATUS);
      setMarketStatus(snap);
      const snapR = await fetchSnapshot("regime.json", DEMO_REGIME);
      setRegime(snapR);
      setIsDemoMode(true);
    }
  };

  const fetchPredictions = async () => {
    try {
      const res = await fetch("/api/predictions/today");
      if (res.ok) {
        const data = await res.json();
        const preds = data.predictions || [];
        setTodayPredictions(preds);
      } else {
        const snap = await fetchSnapshot("today_predictions.json", { predictions: [] });
        setTodayPredictions(snap?.predictions || []);
      }
    } catch {
      const snap = await fetchSnapshot("today_predictions.json", { predictions: [] });
      setTodayPredictions(snap?.predictions || []);
    }
  };

  const fetchVoiceBriefing = async () => {
    try {
      const res = await fetch("/api/voice/briefing");
      if (res.ok) {
        const data = await res.json();
        setBriefingScript(data.script || DEMO_VOICE_BRIEFING);
      } else {
        setBriefingScript(DEMO_VOICE_BRIEFING);
      }
    } catch {
      setBriefingScript(DEMO_VOICE_BRIEFING);
    }
  };

  const fetchStressMetrics = async () => {
    try {
      const [mRes, hRes] = await Promise.all([
        fetch("/api/stress-test/metrics"),
        fetch("/api/predictions/history?limit=30"),
      ]);
      if (mRes.ok) {
        const data = await mRes.json();
        setStressMetrics(data.total_trades > 0 ? data : DEMO_STRESS_METRICS);
      } else {
        const snap = await fetchSnapshot("stress_metrics.json", DEMO_STRESS_METRICS);
        setStressMetrics(snap);
      }
      if (hRes.ok) setTradeHistory(await hRes.json());
    } catch {
      const snap = await fetchSnapshot("stress_metrics.json", DEMO_STRESS_METRICS);
      setStressMetrics(snap);
    }
  };

  const fetchPortfolio = async () => {
    try {
      const res = await fetch("/api/portfolio");
      if (res.ok) {
        setPortfolio(await res.json());
      } else {
        const snap = await fetchSnapshot("portfolio.json", []);
        if (snap && snap.length > 0) setPortfolio(snap);
      }
    } catch (e) {
      console.warn("Portfolio fetch fallback", e);
    }
  };

  const fetchMistakes = async () => {
    try {
      const res = await fetch("/api/mistakes");
      if (res.ok) {
        setMistakes(await res.json());
      } else {
        const snap = await fetchSnapshot("mistakes.json", []);
        if (snap && snap.length > 0) setMistakes(snap);
      }
    } catch (e) {
      console.warn("Mistakes fetch fallback", e);
    }
  };

  const fetchVaultKeys = async () => {
    try {
      const res = await fetch("/api/vault/keys");
      if (res.ok) setVaultKeys(await res.json());
    } catch (e) {
      console.warn("Vault fetch fallback", e);
    }
  };

  const fetchFiiDiiData = async () => {
    try {
      const res = await fetch("/api/market/fii-dii");
      if (res.ok) setFiiDiiData(await res.json());
      else {
        const snap = await fetchSnapshot("fii_dii.json", DEMO_FII_DII);
        setFiiDiiData(snap);
      }
    } catch {
      const snap = await fetchSnapshot("fii_dii.json", DEMO_FII_DII);
      setFiiDiiData(snap);
    }
  };

  const fetchAccuracyTracker = async () => {
    try {
      const res = await fetch("/api/predictions/accuracy-tracker");
      if (res.ok) {
        const data = await res.json();
        setAccuracyTracker(data.total_graded > 0 ? data : DEMO_ACCURACY_TRACKER);
      } else {
        const snap = await fetchSnapshot("accuracy_tracker.json", DEMO_ACCURACY_TRACKER);
        setAccuracyTracker(snap);
        if (snap?.history) setTradeHistory(snap.history);
      }
    } catch {
      const snap = await fetchSnapshot("accuracy_tracker.json", DEMO_ACCURACY_TRACKER);
      setAccuracyTracker(snap);
      if (snap?.history) setTradeHistory(snap.history);
    }
  };

  const fetchTelegramAlerts = async () => {
    try {
      const res = await fetch("/api/alerts/history?limit=50");
      if (res.ok) {
        const data = await res.json();
        const alts = data.alerts || [];
        setTelegramAlerts(alts.length > 0 ? alts : DEMO_TELEGRAM_ALERTS);
      } else {
        setTelegramAlerts(DEMO_TELEGRAM_ALERTS);
      }
    } catch {
      setTelegramAlerts(DEMO_TELEGRAM_ALERTS);
    }
  };

  const fetchSectorMatrix = async () => {
    try {
      const res = await fetch("/api/market/sector-matrix");
      if (res.ok) setSectorMatrix(await res.json());
      else {
        const snap = await fetchSnapshot("sector_matrix.json", DEMO_SECTOR_MATRIX);
        setSectorMatrix(snap);
      }
    } catch {
      const snap = await fetchSnapshot("sector_matrix.json", DEMO_SECTOR_MATRIX);
      setSectorMatrix(snap);
    }
  };

  const fetchValuePicks = async () => {
    try {
      const res = await fetch("/api/scan/value");
      if (res.ok) {
        setValuePicksData(await res.json());
      } else {
        const snap = await fetchSnapshot("value_picks.json", null);
        if (snap) setValuePicksData(snap);
      }
    } catch {
      const snap = await fetchSnapshot("value_picks.json", null);
      if (snap) setValuePicksData(snap);
    }
  };

  const handleRunValueScan = async (mode: string = "all") => {
    if (isStaticHost) {
      showToast("Cloud Mode: Opening GitHub Actions. Click 'Run workflow' -> select 'value_scan' to run in the cloud without keeping your PC on!", "info");
      window.open("https://github.com/Ayyussh/aura-nse-pro/actions/workflows/market_automation.yml", "_blank");
      return;
    }
    setIsLoadingValueScan(true);
    showToast(`Scanning ${mode === "all" ? "All Listed NSE Equities (~2,760 stocks)" : "Diversified Bluechip Universe"} for Undervalued Compounders...`, "info");
    try {
      const res = await fetch(`/api/scan/value?mode=${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (res.ok) {
        const json = await res.json();
        const scanData = json.data || json;
        setValuePicksData(scanData);
        const count = scanData?.undervalued_count ?? scanData?.value_picks?.length ?? 0;
        showToast(`Scan complete: Found ${count} undervalued compounders! Separate alert sent to Telegram.`, "success");
      } else {
        showToast("Value scan failed or backend offline.", "info");
      }
    } catch (e) {
      console.error(e);
      showToast("Value scan error. Check backend connection.", "info");
    } finally {
      setIsLoadingValueScan(false);
      fetchTelegramAlerts();
    }
  };

  const handleRunScanNow = async () => {
    if (isStaticHost) {
      showToast("Cloud Mode: Opening GitHub Actions. Click 'Run workflow' -> select 'premarket' or 'full_cycle' to run in the cloud!", "info");
      window.open("https://github.com/Ayyussh/aura-nse-pro/actions/workflows/market_automation.yml", "_blank");
      return;
    }
    setIsLoadingScan(true);
    setAuraState("Scanning");
    showToast("Triggering 9:00 AM Pre-Market Institutional Screener...", "info");
    try {
      const res = await fetch("/api/jobs/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_name: "0900_pre_market_plan" }),
      });
      if (res.ok) {
        const data = await res.json();
        const summary = data.pipeline_summary || {};
        if (summary.approved_candidates?.length > 0) {
          setTodayPredictions(summary.approved_candidates);
          setAuraState("Bullish Signal");
          showToast(`Screening complete: ${summary.approved_candidates.length} setups approved!`, "success");
        } else {
          setAuraState("Idle");
          showToast("Screening complete: NO TRADE TODAY ruling (Capital preserved)", "info");
        }
        setRejectedCandidates(summary.rejected_candidates || []);
        if (summary.briefing_script) setBriefingScript(summary.briefing_script);
      } else {
        showToast("Backend offline: Showing institutional candidate set.", "info");
      }
    } catch {
      showToast("Backend offline: Showing institutional candidate set.", "info");
      setAuraState("Idle");
    } finally {
      setIsLoadingScan(false);
      fetchStressMetrics();
      fetchAccuracyTracker();
      fetchTelegramAlerts();
      fetchFiiDiiData();
      fetchSectorMatrix();
    }
  };

  const handleValidateAllKeys = async () => {
    if (isStaticHost) {
      showToast("Key Vault: API keys are securely managed via GitHub Secrets in CI/CD. Run .\\start.bat to manage local .env keys.", "info");
      return;
    }
    setIsValidatingKeys(true);
    try {
      const res = await fetch("/api/vault/validate-all", { method: "POST" });
      if (res.ok) {
        fetchVaultKeys();
        showToast("All API Keys validated successfully!", "success");
      }
    } catch {
      showToast("Key validation failed — check network.", "info");
    } finally {
      setIsValidatingKeys(false);
    }
  };

  const handleAddHolding = async (holdingData: any) => {
    if (isStaticHost) {
      showToast("Static Mode: Portfolio additions are managed locally via .\\start.bat.", "info");
      return;
    }
    try {
      const res = await fetch("/api/portfolio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(holdingData),
      });
      if (res.ok) {
        fetchPortfolio();
        showToast(`Added ${holdingData.symbol} to portfolio!`, "success");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteHolding = async (id: number) => {
    if (isStaticHost) {
      showToast("Static Mode: Portfolio deletions are managed locally via .\\start.bat.", "info");
      return;
    }
    try {
      const res = await fetch(`/api/portfolio/${id}`, { method: "DELETE" });
      if (res.ok) {
        fetchPortfolio();
        showToast("Holding removed.", "info");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveKey = async (keyData: any) => {
    if (isStaticHost) {
      showToast("Static Mode: Key updates are managed locally via .\\start.bat or GitHub Secrets.", "info");
      return;
    }
    try {
      const res = await fetch("/api/vault/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keyData),
      });
      if (res.ok) {
        fetchVaultKeys();
        showToast("Key saved securely to vault.", "success");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendResearchQuery = async (query: string): Promise<string> => {
    if (isStaticHost) {
      return "You are viewing AURA in read-only Static Cloud Mode on GitHub Pages. Institutional LLM bull/bear trade audits are pre-computed by GitHub Actions and visible on each trade card in the Command Center. For interactive ad-hoc queries, launch the app locally using start.bat.";
    }
    try {
      const res = await fetch("/api/chat/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.response;
      }
      return "Local backend offline. In live market sessions, AURA provides multi-LLM bull/bear thesis audits across NSE equities.";
    } catch {
      return "Backend connection offline. In live market sessions, AURA provides multi-LLM bull/bear thesis audits across NSE equities.";
    }
  };

  const handleResolveMistake = (id: number, ruleText: string) => {
    showToast(`Mistake resolved: Guardrail added to Mistake Lab!`, "success");
    setTimeout(() => {
      fetchMistakes();
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#0b0f17] text-gray-100 flex flex-col font-sans">
      {/* GitHub Pages Static Host Notice */}
      {isStaticHost && (
        <div className="bg-cyan-950/90 border-b border-cyan-800/80 px-4 py-2 text-xs text-cyan-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 z-50">
          <div className="flex items-center gap-2">
            <span className="font-bold uppercase tracking-wider bg-cyan-900/90 border border-cyan-600 px-2 py-0.5 rounded text-[10px] text-cyan-100">
              GITOPS CLOUD SYNC
            </span>
            <span>
              Pure GET Static Analytics powered by GitHub Actions. {snapshotTimestamp ? `Latest snapshot: ${snapshotTimestamp}` : "Continuous EOD snapshots."}
            </span>
          </div>
          <div className="text-[11px] font-mono text-cyan-300 flex items-center gap-2">
            <span>To run live interactive backend:</span>
            <code className="bg-black/60 px-2 py-0.5 rounded border border-cyan-700 text-cyan-200">.\start.bat</code>
            <span>(http://127.0.0.1:8000)</span>
          </div>
        </div>
      )}

      {/* Institutional Top Navigation Header */}
      <header className="border-b border-gray-800/80 bg-[#0e1420]/95 backdrop-blur-md sticky top-0 z-50 px-4 lg:px-8 py-3">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Brand & Market Status */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-600 to-emerald-500 flex items-center justify-center shadow-lg shadow-indigo-600/30">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-extrabold tracking-tight text-white">AURA-NSE Pro</span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800">
                  v2.0
                </span>
                {isStaticHost ? (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800 flex items-center gap-1">
                    🌐 GITOPS CLOUD SYNC
                  </span>
                ) : isDemoMode ? (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800 flex items-center gap-1">
                    ⚡ OFFLINE PREVIEW
                  </span>
                ) : (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800 flex items-center gap-1">
                    🟢 BACKEND LIVE (127.0.0.1:8000)
                  </span>
                )}
              </div>
              <div className="text-[11px] text-gray-400 flex items-center gap-2">
                <span>Institutional Decision Support & Walk-Forward Platform</span>
                <span className="text-gray-600">•</span>
                <span className="font-mono text-cyan-400 flex items-center gap-1">
                  <Clock className="w-3 h-3 inline" /> {currentTimeIst || "IST"}
                </span>
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
              <Key className="w-3.5 h-3.5" /> Key Vault
            </button>
            <button
              onClick={() => setActiveView("research")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "research"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" /> AI Research
            </button>
            <button
              onClick={() => setActiveView("tax")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "tax"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <Receipt className="w-3.5 h-3.5" /> Tax & Charges
            </button>
            <button
              onClick={() => setActiveView("health")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                activeView === "health"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <Activity className="w-3.5 h-3.5" /> System Health
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
            fiiDii={fiiDiiData}
            accuracyTracker={accuracyTracker}
            telegramAlerts={telegramAlerts}
            sectorMatrix={sectorMatrix}
            valuePicksData={valuePicksData}
            onRefreshScan={handleRunScanNow}
            onRunValueScan={handleRunValueScan}
            isLoading={isLoadingScan}
            isLoadingValueScan={isLoadingValueScan}
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
            onResolveMistake={handleResolveMistake}
          />
        )}

        {activeView === "vault" && (
          <VaultSettings
            keys={vaultKeys}
            onValidateAll={handleValidateAllKeys}
            isValidating={isValidatingKeys}
            onSaveKey={handleSaveKey}
          />
        )}

        {activeView === "research" && (
          <ResearchConsole onSendQuery={handleSendResearchQuery} />
        )}

        {activeView === "tax" && <JournalTaxCenter />}
        {activeView === "health" && <SystemHealth />}
      </main>

      {/* Toast Notification Popup */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl bg-gray-900 border border-indigo-500/50 shadow-2xl text-xs font-semibold text-white animate-in slide-in-from-bottom">
          {toast.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : (
            <AlertCircle className="w-4 h-4 text-cyan-400" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Statutory Regulatory Footer */}
      <footer className="border-t border-gray-800/80 bg-[#0a0e16] text-[11px] text-gray-500 py-6 px-4 text-center space-y-1">
        <p className="font-semibold text-gray-400">
          AURA-NSE Pro • Quantitative Algorithmic Decision-Support System
        </p>
        <p className="max-w-2xl mx-auto leading-relaxed text-gray-500">
          Educational decision support only, not investment advice. NSE/BSE stock markets involve financial risk. Backtests, simulations, and historical probabilities do not guarantee future returns. Strictly zero automated execution.
        </p>
      </footer>
    </div>
  );
}

export default App;

